"""Stage 3 — 3DGS 학습: 정제 ply + 정렬 포즈 → COLMAP 데이터셋 → 학습 → .splat.

입력 (Stage 1·2 산출물):
    clean_ply       point_cloud_clean.ply       (월드 XYZ+RGB, 지면정렬)
    aligned_poses   camera_poses_aligned.json   (c2w 4x4 + intrinsics)
    images_dir      Stage1/images/              (포즈에 대응하는 RGB)

처리:
    1) COLMAP 텍스트 모델 작성 (cameras/images/points3D + images 링크)
    2) gaussian-splatting train.py 서브프로세스 학습
    3) 결과 point_cloud.ply → output.splat 변환

출력:
    <out_dir>/colmap/                COLMAP 데이터셋
    <out_dir>/model/                 3DGS 학습 결과
    <out_dir>/output.splat           웹 뷰어용 splat

실행 환경: conda env `3dgs_pipeline` (gaussian-splatting 의존성 포함).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))
from common import logio  # noqa: E402

logger = logging.getLogger(__name__)

SH_C0 = 0.28209479177387814  # SH degree-0 계수


# ---------------------------------------------------------------------------
# 회전 → 쿼터니언 (COLMAP: w2c, qw qx qy qz)
# ---------------------------------------------------------------------------
def _rotmat_to_qvec(R: np.ndarray) -> np.ndarray:
    """3x3 회전 → 쿼터니언 (w,x,y,z). COLMAP read_write_model 와 동일 규약."""
    Rxx, Ryx, Rzx, Rxy, Ryy, Rzy, Rxz, Ryz, Rzz = R.flat
    K = np.array([
        [Rxx - Ryy - Rzz, 0, 0, 0],
        [Ryx + Rxy, Ryy - Rxx - Rzz, 0, 0],
        [Rzx + Rxz, Rzy + Ryz, Rzz - Rxx - Ryy, 0],
        [Ryz - Rzy, Rzx - Rxz, Rxy - Ryx, Rxx + Ryy + Rzz],
    ]) / 3.0
    vals, vecs = np.linalg.eigh(K)
    qvec = vecs[[3, 0, 1, 2], np.argmax(vals)]
    if qvec[0] < 0:
        qvec = -qvec
    return qvec


# ---------------------------------------------------------------------------
# 1) COLMAP 데이터셋 작성
# ---------------------------------------------------------------------------
def write_colmap_dataset(
    clean_ply: Path, poses_json: Path, images_src: Path,
    dataset_dir: Path, image_stride: int = 1,
) -> Path:
    """3DGS 가 읽는 COLMAP 텍스트 모델 + images/ 생성."""
    import open3d as o3d

    dataset_dir = Path(dataset_dir)
    sparse = dataset_dir / "sparse" / "0"
    img_out = dataset_dir / "images"
    sparse.mkdir(parents=True, exist_ok=True)
    img_out.mkdir(parents=True, exist_ok=True)

    poses_c2w, intr, names = logio.read_poses_json(poses_json)
    if not intr:
        raise RuntimeError("intrinsics 가 비어 있음 — Stage 1 camera_poses.json 확인")
    W, H = int(intr["width"]), int(intr["height"])
    fx, fy, cx, cy = intr["fx"], intr["fy"], intr["cx"], intr["cy"]

    # --- cameras.txt (단일 PINHOLE 공유) ---
    with open(sparse / "cameras.txt", "w") as f:
        f.write("# Camera list\n# CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n")
        f.write(f"1 PINHOLE {W} {H} {fx} {fy} {cx} {cy}\n")

    # --- images.txt (w2c) ---
    sel = list(range(0, len(poses_c2w), max(1, image_stride)))
    n_written = 0
    with open(sparse / "images.txt", "w") as f:
        f.write("# Image list\n# IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n")
        for img_id, i in enumerate(sel, start=1):
            c2w = poses_c2w[i]
            R_c2w = c2w[:3, :3]
            C = c2w[:3, 3]
            R_w2c = R_c2w.T
            t_w2c = -R_w2c @ C
            q = _rotmat_to_qvec(R_w2c)
            name = names[i] if i < len(names) else f"{i:06d}.jpg"
            src = images_src / name
            if not src.exists():  # 확장자 보정
                alt = images_src / f"{Path(name).stem}.jpg"
                src = alt if alt.exists() else src
            if not src.exists():
                logger.warning("이미지 없음, 스킵: %s", src)
                continue
            dst = img_out / Path(name).name
            if not dst.exists():
                try:
                    os.symlink(src.resolve(), dst)
                except OSError:
                    shutil.copy2(src, dst)
            f.write(
                f"{img_id} {q[0]} {q[1]} {q[2]} {q[3]} "
                f"{t_w2c[0]} {t_w2c[1]} {t_w2c[2]} 1 {Path(name).name}\n\n"
            )
            n_written += 1
    logger.info("COLMAP images.txt: %d개 (stride %d)", n_written, image_stride)

    # --- points3D.txt (정제 ply → 초기 가우시안) ---
    pcd = logio.read_ply(clean_ply)
    pts = np.asarray(pcd.points)
    cols = np.asarray(pcd.colors)
    if len(cols) != len(pts):
        cols = np.full((len(pts), 3), 0.5)
    with open(sparse / "points3D.txt", "w") as f:
        f.write("# 3D point list\n# POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[]\n")
        rgb = np.clip(cols * 255, 0, 255).astype(int)
        for pid, (xyz, c) in enumerate(zip(pts, rgb), start=1):
            f.write(f"{pid} {xyz[0]} {xyz[1]} {xyz[2]} {c[0]} {c[1]} {c[2]} 0\n")
    logger.info("COLMAP points3D.txt: %d pts", len(pts))
    return dataset_dir


# ---------------------------------------------------------------------------
# 2) 3DGS 학습
# ---------------------------------------------------------------------------
def run_3dgs_training(dataset_dir: Path, model_dir: Path, gs_repo: Path, cfg: dict) -> Path:
    train_py = Path(gs_repo) / "train.py"
    if not train_py.exists():
        raise FileNotFoundError(f"gaussian-splatting train.py 없음: {train_py}")
    model_dir.mkdir(parents=True, exist_ok=True)
    save_iters = cfg.get("save_iterations", [7000, cfg.get("iterations", 30000)])
    cmd = [
        sys.executable, str(train_py),
        "-s", str(dataset_dir),
        "-m", str(model_dir),
        "--iterations", str(cfg.get("iterations", 30000)),
        "--sh_degree", str(cfg.get("sh_degree", 3)),
        "--resolution", str(cfg.get("resolution", 1)),
        "--data_device", cfg.get("data_device", "cuda"),
        "--densify_until_iter", str(cfg.get("densify_until_iter", 15000)),
        "--save_iterations", *[str(s) for s in save_iters],
        "--eval",
    ]
    env = os.environ.copy()
    # CUDA 기본 정렬(FASTEST_FIRST)이면 인덱스가 nvidia-smi 와 달라짐 → PCI 순서 고정.
    env.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
    # 호출자가 이미 CUDA_VISIBLE_DEVICES 를 지정했으면 존중, 아니면 config 의 gpu 사용.
    if "CUDA_VISIBLE_DEVICES" not in os.environ:
        env["CUDA_VISIBLE_DEVICES"] = str(cfg.get("gpu", 0))
    logger.info("3DGS 학습 시작 (CUDA_VISIBLE_DEVICES=%s, PCI 순서): %s",
                env.get("CUDA_VISIBLE_DEVICES", "기본"), " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(gs_repo), env=env)

    # 최종 iteration ply 경로
    iters = max(save_iters)
    out_ply = model_dir / "point_cloud" / f"iteration_{iters}" / "point_cloud.ply"
    if not out_ply.exists():  # 가장 큰 iteration 폴더 자동 탐색
        pcdir = model_dir / "point_cloud"
        cand = sorted(pcdir.glob("iteration_*"), key=lambda d: int(d.name.split("_")[1]))
        if cand:
            out_ply = cand[-1] / "point_cloud.ply"
    if not out_ply.exists():
        raise FileNotFoundError(f"학습 결과 ply 없음: {out_ply}")
    return out_ply


# ---------------------------------------------------------------------------
# 3) 3DGS ply → .splat (antimatter15 포맷)
# ---------------------------------------------------------------------------
def pointcloud_to_splat(input_ply: Path, out_splat: Path, point_radius: float = 0.03) -> Path:
    """학습 없이 포인트클라우드(XYZ+RGB) → .splat 직접 변환.

    각 점을 작은 등방(isotropic) 가우시안으로: LingBot 데모처럼 점을 그대로 렌더.
    point_radius: 가우시안 반경(m). 보통 voxel_size 의 0.5~1배.
    """
    pcd = logio.read_ply(input_ply)
    xyz = np.asarray(pcd.points, dtype=np.float32)
    cols = np.asarray(pcd.colors, dtype=np.float32)
    n = len(xyz)
    if len(cols) != n:
        cols = np.full((n, 3), 0.6, dtype=np.float32)
    rgba = np.concatenate([np.clip(cols, 0, 1), np.ones((n, 1), np.float32)], axis=1)
    rgba_u8 = (rgba * 255).astype(np.uint8)
    scales = np.full((n, 3), point_radius, dtype=np.float32)
    # 단위 쿼터니언 (w,x,y,z)=(1,0,0,0) → uint8 (255,128,128,128)
    rot_u8 = np.tile(np.array([255, 128, 128, 128], np.uint8), (n, 1))

    buf = np.zeros(n, dtype=[
        ("pos", "<f4", (3,)), ("scale", "<f4", (3,)),
        ("rgba", "u1", (4,)), ("rot", "u1", (4,)),
    ])
    buf["pos"], buf["scale"], buf["rgba"], buf["rot"] = xyz, scales, rgba_u8, rot_u8
    out_splat = Path(out_splat)
    out_splat.parent.mkdir(parents=True, exist_ok=True)
    out_splat.write_bytes(buf.tobytes())
    logger.info("직접 splat(학습X): %d pts, r=%.3f, %.1f MB → %s",
                n, point_radius, out_splat.stat().st_size / 1e6, out_splat)
    return out_splat


def export_splat(input_ply: Path, out_splat: Path, sort: bool = True) -> Path:
    """3DGS point_cloud.ply → .splat (32 bytes/gaussian).

    레이아웃: pos(3f) scale(3f exp) rgba(4u8) rot(4u8 normalized*128+128).
    """
    from plyfile import PlyData

    ply = PlyData.read(str(input_ply))
    v = ply["vertex"]
    xyz = np.stack([v["x"], v["y"], v["z"]], axis=1).astype(np.float32)
    scales = np.stack([v["scale_0"], v["scale_1"], v["scale_2"]], axis=1).astype(np.float32)
    rots = np.stack([v["rot_0"], v["rot_1"], v["rot_2"], v["rot_3"]], axis=1).astype(np.float32)
    dc = np.stack([v["f_dc_0"], v["f_dc_1"], v["f_dc_2"]], axis=1).astype(np.float32)
    opacity = np.asarray(v["opacity"], dtype=np.float32)

    n = len(xyz)
    scales = np.exp(scales)                                   # log → linear
    color = np.clip(0.5 + SH_C0 * dc, 0.0, 1.0)              # SH DC → RGB
    alpha = 1.0 / (1.0 + np.exp(-opacity))                   # sigmoid
    rgba = np.concatenate([color, alpha[:, None]], axis=1)
    rgba_u8 = np.clip(rgba * 255, 0, 255).astype(np.uint8)
    rnorm = rots / (np.linalg.norm(rots, axis=1, keepdims=True) + 1e-9)
    rot_u8 = np.clip(rnorm * 128 + 128, 0, 255).astype(np.uint8)

    if sort:  # 중요도(부피×불투명도) 내림차순 → 점진적 로딩에 유리
        importance = alpha * scales.prod(axis=1)
        order = np.argsort(-importance)
        xyz, scales, rgba_u8, rot_u8 = xyz[order], scales[order], rgba_u8[order], rot_u8[order]

    buf = np.zeros(n, dtype=[
        ("pos", "<f4", (3,)), ("scale", "<f4", (3,)),
        ("rgba", "u1", (4,)), ("rot", "u1", (4,)),
    ])
    buf["pos"], buf["scale"], buf["rgba"], buf["rot"] = xyz, scales, rgba_u8, rot_u8

    out_splat = Path(out_splat)
    out_splat.parent.mkdir(parents=True, exist_ok=True)
    out_splat.write_bytes(buf.tobytes())
    logger.info("splat 저장: %d gaussians, %.1f MB → %s",
                n, out_splat.stat().st_size / 1e6, out_splat)
    return out_splat


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
def run(clean_ply, poses_json, images_dir, out_dir, gs_repo, cfg, skip_train=False) -> dict:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    # 직접 렌더 모드: 학습 없이 포인트클라우드를 바로 splat 으로 (LingBot 데모처럼)
    if cfg.get("mode", "train") == "pointcloud":
        out_splat = pointcloud_to_splat(
            Path(clean_ply), out_dir / "output.splat",
            point_radius=cfg.get("point_radius", 0.03),
        )
        return {"splat": str(out_splat), "mode": "pointcloud"}

    dataset = write_colmap_dataset(
        Path(clean_ply), Path(poses_json), Path(images_dir),
        out_dir / "colmap", image_stride=cfg.get("image_stride", 1),
    )
    result = {"colmap": str(dataset)}
    if skip_train:
        logger.info("skip_train=True → COLMAP 데이터셋만 생성")
        return result

    model_dir = out_dir / "model"
    trained_ply = run_3dgs_training(dataset, model_dir, Path(gs_repo), cfg)
    out_splat = export_splat(trained_ply, out_dir / "output.splat")
    result.update({
        "model": str(model_dir),
        "trained_ply": str(trained_ply),
        "splat": str(out_splat),
    })
    return result


def main():
    ap = argparse.ArgumentParser(description="Stage 3: 3DGS 학습 + splat 변환")
    ap.add_argument("--clean_ply", required=True)
    ap.add_argument("--poses", required=True)
    ap.add_argument("--images_dir", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--skip_train", action="store_true", help="COLMAP 데이터셋만 생성")
    ap.add_argument("--export_only", default=None, help="기존 ply 를 splat 으로만 변환")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    logio.setup_logging(out_dir, name="stage3")

    if args.export_only:
        export_splat(Path(args.export_only), out_dir / "output.splat")
        return

    full = logio.load_config(args.config)
    cfg = full["stage3_train"]
    gs_repo = logio.resolve_path(full["paths"]["gaussian_splatting"])
    result = run(args.clean_ply, args.poses, args.images_dir, out_dir, gs_repo,
                 cfg, skip_train=args.skip_train)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
