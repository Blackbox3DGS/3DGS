"""Stage 1 — LingBot-Map inference: 영상 → 포인트클라우드 + 카메라 포즈.

third_party/lingbot-map 의 demo.py 헬퍼(load_images/load_model/postprocess)를
재사용해 추론하고, predictions 를 표준 산출물로 변환한다.

산출물:
    <out_dir>/point_cloud.ply        (월드좌표 XYZ + RGB)
    <out_dir>/camera_poses.json      (c2w 4x4 + intrinsics)
    <out_dir>/meta.json              (프레임수/해상도/파라미터)

실행 환경: conda env `lingbot-map` (torch 2.8 + cu128).
오케스트레이터가 params.json 을 만들어 넘긴다 (pyyaml 의존 제거).
    python stages/stage1_infer.py --params /path/params.json

params.json 스키마:
    {"video_path","out_dir","lingbot_repo","ckpt", <stage1_mapping cfg ...>}
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import types
from pathlib import Path

import numpy as np

logger = logging.getLogger("stage1")

# common 은 numpy 만 사용하는 ply 헬퍼만 쓴다 (open3d/yaml lazy)
_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))
from common import logio  # noqa: E402


def _build_args(p: dict) -> types.SimpleNamespace:
    """demo.load_model 가 기대하는 args 네임스페이스."""
    return types.SimpleNamespace(
        mode=p.get("mode", "windowed"),
        image_size=p.get("image_size", 518),
        patch_size=p.get("patch_size", 14),
        enable_3d_rope=True,
        max_frame_num=p.get("max_frame_num", 1024),
        kv_cache_sliding_window=p.get("kv_cache_sliding_window", 64),
        num_scale_frames=p.get("num_scale_frames", 8),
        use_sdpa=p.get("use_sdpa", True),   # flashinfer 미설치 대비 기본 SDPA
        camera_num_iterations=p.get("camera_num_iterations", 4),
        model_path=p["ckpt"],
    )


def _to_numpy(x):
    import torch
    if isinstance(x, torch.Tensor):
        return x.detach().cpu().float().numpy()
    return np.asarray(x)


def _squeeze_lead(a: np.ndarray, keep: int) -> np.ndarray:
    """앞쪽 size-1 배치 차원을 ndim==keep 이 될 때까지 제거.

    모델이 (B=1, S, ...) 처럼 배치 차원을 남기는 경우 정규화.
    """
    a = np.asarray(a)
    while a.ndim > keep and a.shape[0] == 1:
        a = a[0]
    return a


def _unproject_depth_frame(d: np.ndarray, K: np.ndarray, c2w: np.ndarray) -> np.ndarray:
    """프레임 1장 depth → 월드 포인트. d(H,W), K(3,3), c2w(3x4/4x4) → (H,W,3).

    OpenCV 핀홀: x=(u-cx)/fx·d, y=(v-cy)/fy·d, z=d → 카메라좌표 → c2w 로 월드.
    """
    H, W = d.shape
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    uu, vv = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    x = (uu - cx) / fx * d
    y = (vv - cy) / fy * d
    cam = np.stack([x, y, d], axis=-1)            # (H,W,3) 카메라좌표
    R, t = c2w[:3, :3], c2w[:3, 3]
    return cam @ R.T + t                          # (H,W,3) 월드좌표


def _extract_pointcloud(predictions, images, p: dict):
    """predictions → (points (M,3), colors (M,3) 0~1) with stride/conf/cap.

    windowed 모델은 world_points 를 안 줄 수 있음 → depth+intrinsic+extrinsic(c2w)
    로 직접 unproject. 메모리 절약 위해 선택 프레임만 프레임별로 계산.
    """
    has_wp = "world_points" in predictions
    if has_wp:
        wp_all = _squeeze_lead(_to_numpy(predictions["world_points"]), 4)   # (S,H,W,3)
        S, H, W = wp_all.shape[:3]
        conf_all = (_squeeze_lead(_to_numpy(predictions["world_points_conf"]), 3)
                    if "world_points_conf" in predictions else np.ones((S, H, W), np.float32))
        logger.info("world_points 사용: wp%s conf%s", wp_all.shape, conf_all.shape)
    else:
        logger.warning("world_points 없음 → depth unproject 폴백 사용")
        depth = _squeeze_lead(_to_numpy(predictions["depth"]), 3)           # (S,H,W[,1])
        if depth.ndim == 4 and depth.shape[-1] == 1:
            depth = depth[..., 0]
        S, H, W = depth.shape[:3]
        K_all = _squeeze_lead(_to_numpy(predictions["intrinsic"]), 3)       # (S,3,3)
        ext_all = _squeeze_lead(_to_numpy(predictions["extrinsic"]), 3)     # (S,3,4) c2w
        conf_all = (_squeeze_lead(_to_numpy(predictions["depth_conf"]), 3)
                    if "depth_conf" in predictions else np.ones((S, H, W), np.float32))
        logger.info("depth 폴백: depth%s K%s ext%s conf%s",
                    depth.shape, K_all.shape, ext_all.shape, conf_all.shape)

    imgs = _squeeze_lead(_to_numpy(images), 4)   # → (S,3,H,W) 또는 (S,H,W,3)
    if imgs.ndim == 4 and imgs.shape[1] == 3:
        imgs = np.transpose(imgs, (0, 2, 3, 1))   # → (S,H,W,3)
    logger.info("images shape: %s, frames S=%d", imgs.shape, S)

    fs = max(1, int(p.get("points_frame_stride", 5)))
    ps = max(1, int(p.get("points_pixel_stride", 2)))

    sel = slice(None, None, ps)
    pts_list, col_list, conf_list = [], [], []
    for s in range(0, S, fs):
        if has_wp:
            fp = wp_all[s, sel, sel, :].reshape(-1, 3)
        else:
            world = _unproject_depth_frame(depth[s], K_all[s], ext_all[s])  # (H,W,3)
            fp = world[sel, sel, :].reshape(-1, 3)
        fc = conf_all[s, sel, sel].reshape(-1)
        col = imgs[s, sel, sel, :].reshape(-1, 3)
        pts_list.append(fp); conf_list.append(fc); col_list.append(col)
    pts = np.concatenate(pts_list, 0)
    cols = np.concatenate(col_list, 0)
    cfa = np.concatenate(conf_list, 0)

    # 임계 조정을 재추론 없이 하도록 raw 저장 (points/colors/conf)
    raw_npz = p.get("_raw_npz")
    if raw_npz:
        np.savez_compressed(raw_npz, points=pts.astype(np.float32),
                            colors=cols.astype(np.float32), conf=cfa.astype(np.float32))
        logger.info("raw 포인트(임계 전) 저장 → %s (%d pts)", raw_npz, len(pts))

    # conf 백분위 필터
    mask = cfa > 1e-5
    perc = float(p.get("conf_percentile", 10))
    if perc > 0:
        thr = np.percentile(cfa[mask] if mask.any() else cfa, perc)
        mask &= cfa >= thr
        logger.info("conf 백분위 %.0f%% → 임계 %.4f", perc, thr)
    # 유한값만
    mask &= np.isfinite(pts).all(axis=1)
    # sky 마스크: 밝고 채도 낮은(흰/회색 하늘) 점 제거 — depth starburst 노이즈 컷.
    # (config mask_sky 의 실제 구현. 모델 입력은 손대지 않고 추출 단계에서만 거른다.)
    if p.get("mask_sky", False):
        c01 = cols / 255.0 if cols.max() > 1.0 + 1e-6 else cols
        cmax = c01.max(axis=1); cmin = c01.min(axis=1)
        sat = (cmax - cmin) / (cmax + 1e-6)
        sb, ss = float(p.get("sky_bright", 0.55)), float(p.get("sky_sat", 0.15))
        sky = (cmax > sb) & (sat < ss)
        mask &= ~sky
        logger.info("sky 마스크(bright>%.2f & sat<%.2f): %d 제거", sb, ss, int(sky.sum()))
    pts, cols = pts[mask], cols[mask]
    logger.info("포인트 추출: 프레임 %d/%d (stride %d), 픽셀 stride %d → %d pts",
                len(range(0, S, fs)), S, fs, ps, len(pts))

    # 최종 랜덤 캡
    cap = int(p.get("max_points", 12_000_000))
    if cap > 0 and len(pts) > cap:
        idx = np.random.default_rng(0).choice(len(pts), cap, replace=False)
        pts, cols = pts[idx], cols[idx]
        logger.info("max_points 캡 적용 → %d pts", len(pts))

    if cols.max() > 1.0 + 1e-6:
        cols = cols / 255.0
    return pts, cols


def _extract_poses(predictions, images):
    """extrinsic(c2w 3x4) → (S,4,4) c2w, intrinsics dict."""
    ext = _squeeze_lead(_to_numpy(predictions["extrinsic"]), 3)   # (S,3,4) c2w
    S = ext.shape[0]
    poses = np.tile(np.eye(4), (S, 1, 1))
    poses[:, :3, :4] = ext[:, :3, :4]

    intr = _squeeze_lead(_to_numpy(predictions["intrinsic"]), 3)  # (S,3,3)
    K = np.median(intr, axis=0)
    imgs = _squeeze_lead(_to_numpy(images), 4)
    if imgs.ndim == 4 and imgs.shape[1] == 3:
        H, W = imgs.shape[2], imgs.shape[3]
    else:
        H, W = imgs.shape[1], imgs.shape[2]
    intrinsics = {
        "fx": float(K[0, 0]), "fy": float(K[1, 1]),
        "cx": float(K[0, 2]), "cy": float(K[1, 2]),
        "width": int(W), "height": int(H),
    }
    return poses, intrinsics


def _prepare_image_folder(src: Path, cache: Path, crop_top: float, crop_bottom: float) -> Path:
    """이미지 폴더 입력을 ASCII 경로 캐시로 정규화하고 그 경로를 반환한다.

    - 프레임은 src 직하위 또는 src/img 하위에서 모은다(iterdir → NFD 한글 경로 안전).
    - 블랙박스 차체 크롭(상/하단 비율)>0 이면 잘라 저장, 0이면 심볼릭 링크.
    - 출력은 정렬 순서대로 {i:06d}.jpg (포즈 프레임명과 일치). 다운스트림 load_images
      는 ASCII 캐시만 글롭하므로 한글/NFD 글롭 빗나감을 원천 차단.
    """
    import cv2

    exts = {".jpg", ".jpeg", ".png"}
    files: list[Path] = []
    for base in (src, src / "img"):
        if base.is_dir():
            files = sorted(p for p in base.iterdir()
                           if p.is_file() and p.suffix.lower() in exts)
        if files:
            break
    if not files:
        raise FileNotFoundError(f"이미지 폴더에 프레임이 없습니다: {src} (또는 {src/'img'})")
    if crop_top + crop_bottom >= 0.95:
        raise ValueError(f"크롭 비율이 과도합니다: top={crop_top} bottom={crop_bottom}")

    if cache.exists():
        shutil.rmtree(cache)
    cache.mkdir(parents=True, exist_ok=True)

    do_crop = crop_top > 0 or crop_bottom > 0
    n = 0
    for src_p in files:
        dst = cache / f"{n:06d}.jpg"
        if do_crop:
            im = cv2.imread(str(src_p))
            if im is None:
                logger.warning("이미지 읽기 실패, 건너뜀: %s", src_p)
                continue
            h = im.shape[0]
            y0 = int(round(h * crop_top))
            y1 = int(round(h * (1.0 - crop_bottom)))
            cv2.imwrite(str(dst), im[y0:y1])
        else:
            dst.symlink_to(src_p.resolve())
        n += 1
    logger.info("이미지 폴더 준비: %d장 (crop top %.2f / bottom %.2f) → %s",
                n, crop_top, crop_bottom, cache)
    return cache


def _save_pose_images(images, img_dir: Path, n_poses: int) -> int:
    """images (S,3,H,W) or (S,H,W,3), 0~1 → img_dir/{i:06d}.jpg (포즈 수만큼)."""
    import cv2
    imgs = _squeeze_lead(_to_numpy(images), 4)
    if imgs.ndim == 4 and imgs.shape[1] == 3:
        imgs = np.transpose(imgs, (0, 2, 3, 1))   # → (S,H,W,3)
    n = min(len(imgs), n_poses)
    if len(imgs) != n_poses:
        logger.warning("이미지 수(%d) != 포즈 수(%d) → min 사용", len(imgs), n_poses)
    for i in range(n):
        rgb = np.clip(imgs[i] * 255.0, 0, 255).astype(np.uint8)
        cv2.imwrite(str(img_dir / f"{i:06d}.jpg"), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return n


def run(p: dict) -> dict:
    import torch

    repo = Path(p["lingbot_repo"]).resolve()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    # demo.py 헬퍼 재사용
    import demo  # noqa: E402  (lingbot-map/demo.py)

    out_dir = Path(p["out_dir"]); out_dir.mkdir(parents=True, exist_ok=True)
    ckpt = p.get("ckpt")
    if not ckpt or not Path(ckpt).exists():
        raise FileNotFoundError(
            f"LingBot-Map 체크포인트가 없습니다: {ckpt!r}\n"
            f"  → huggingface 'robbyant/lingbot-map' 에서 lingbot-map-long.pt 다운로드 후 "
            f"config.yaml 의 paths.lingbot_ckpt 에 지정하세요."
        )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    args = _build_args(p)

    # --- 프레임 로드 ---
    # image_dir(이미지 폴더) 우선, 없으면 video_path(MOV/MP4).
    first_k = (p["max_frames"] if p.get("max_frames", 0) else None)
    image_dir = p.get("image_dir")
    if image_dir:
        src_folder = _prepare_image_folder(
            Path(image_dir), out_dir / "_input",
            crop_top=float(p.get("crop_top", 0.0)),
            crop_bottom=float(p.get("crop_bottom", 0.0)),
        )
        images, paths, _ = demo.load_images(
            image_folder=str(src_folder), first_k=first_k,
            image_size=args.image_size, patch_size=args.patch_size,
        )
    else:
        images, paths, _ = demo.load_images(
            video_path=p["video_path"], fps=int(p.get("fps", 10)),
            first_k=first_k,
            image_size=args.image_size, patch_size=args.patch_size,
        )
    model = demo.load_model(args, device)

    dtype = (torch.bfloat16 if (torch.cuda.is_available()
             and torch.cuda.get_device_capability()[0] >= 8) else torch.float16)
    if not torch.cuda.is_available():
        dtype = torch.float32
    if dtype != torch.float32 and getattr(model, "aggregator", None) is not None:
        model.aggregator = model.aggregator.to(dtype=dtype)

    images = images.to(device)
    num_frames = images.shape[0]
    logger.info("프레임 %d, 모드 %s, dtype %s", num_frames, args.mode, dtype)

    kfi = p.get("keyframe_interval") or (1 if num_frames <= 320 else (num_frames + 319) // 320)

    with torch.no_grad(), torch.amp.autocast("cuda", dtype=dtype, enabled=torch.cuda.is_available()):
        if args.mode == "windowed":
            predictions = model.inference_windowed(
                images,
                window_size=p.get("window_size", 128),
                overlap_size=p.get("overlap_size", 16),
                overlap_keyframes=p.get("overlap_keyframes", 16),
                num_scale_frames=args.num_scale_frames,
                keyframe_interval=kfi,
                output_device=torch.device("cpu"),
            )
        else:
            predictions = model.inference_streaming(
                images,
                num_scale_frames=args.num_scale_frames,
                keyframe_interval=kfi,
                output_device=torch.device("cpu"),
            )

    images_for_post = predictions.get("images", images)
    predictions, images_cpu = demo.postprocess(predictions, images_for_post)

    # --- (선택) TSDF 융합용 depth 맵 저장 ---
    if p.get("save_depth_maps") and "depth" in predictions:
        depth = _squeeze_lead(_to_numpy(predictions["depth"]), 3)
        if depth.ndim == 4 and depth.shape[-1] == 1:
            depth = depth[..., 0]
        dconf = (_squeeze_lead(_to_numpy(predictions["depth_conf"]), 3)
                 if "depth_conf" in predictions else np.ones_like(depth))
        K = _squeeze_lead(_to_numpy(predictions["intrinsic"]), 3)
        ext_c2w = _squeeze_lead(_to_numpy(predictions["extrinsic"]), 3)  # (S,3,4)
        np.savez_compressed(
            out_dir / "depth_maps.npz",
            depth=depth.astype(np.float16), conf=dconf.astype(np.float16),
            intrinsic=K.astype(np.float32), extrinsic_c2w=ext_c2w.astype(np.float32),
        )
        logger.info("depth 맵 저장(TSDF용): depth%s → depth_maps.npz", depth.shape)

    # --- 변환 & 저장 ---
    p["_raw_npz"] = str(out_dir / "raw_points.npz")   # 임계 조정용 raw 덤프
    pts, cols = _extract_pointcloud(predictions, images_cpu, p)
    poses, intrinsics = _extract_poses(predictions, images_cpu)

    out_ply = out_dir / "point_cloud.ply"
    out_poses = out_dir / "camera_poses.json"
    logio.write_ply_numpy(out_ply, pts, cols)
    # 포즈와 정확히 정렬된 프레임 이름 (3DGS 가 이미지-포즈를 매칭)
    frame_names = [f"{i:06d}.jpg" for i in range(len(poses))]
    logio.write_poses_json(out_poses, poses, intrinsics, frame_names)

    # 포즈에 대응하는 전처리 이미지 저장 (Stage 3 COLMAP 데이터셋용)
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    n_img = _save_pose_images(images_cpu, img_dir, len(poses))
    logger.info("포즈 이미지 %d장 저장 → %s", n_img, img_dir)

    meta = {
        "num_frames_input": int(num_frames),
        "num_frames_used": int(len(poses)),
        "num_points": int(len(pts)),
        "intrinsics": intrinsics,
        "fps": int(p.get("fps", 10)),
        "mode": args.mode,
        "keyframe_interval": int(kfi),
    }
    with open(out_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    logger.info("Stage 1 완료: %d pts, %d poses → %s", len(pts), len(poses), out_dir)
    return {"point_cloud": str(out_ply), "camera_poses": str(out_poses),
            "images_dir": str(img_dir), **meta}


def main():
    ap = argparse.ArgumentParser(description="Stage 1: LingBot-Map inference")
    ap.add_argument("--params", required=True, help="params.json 경로")
    args = ap.parse_args()
    with open(args.params, "r", encoding="utf-8") as f:
        p = json.load(f)

    out_dir = Path(p["out_dir"]); out_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(out_dir / "stage1.log")],
    )
    result = run(p)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
