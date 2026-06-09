"""pipeline2 오케스트레이터: MOV → LingBot-Map → 전처리 → 3DGS → 웹.

스테이지별 고정 출력 디렉토리(컨벤션)로 중간 결과를 저장하므로,
일부 스테이지만 재실행해도 이전 산출물을 자동으로 이어받는다.

실행 환경: conda env `3dgs_pipeline` (recon). Stage 1 만 `lingbot-map` env 로
교차 호출(subprocess)한다.

예)
    conda run -n 3dgs_pipeline python run.py \
        --video "/data/AI 공학관 주차장.MOV" --stages 1,2,3,4
    # 일부만:  --stages 2,3   (Stage1 산출물 재사용)
    # 학습 빼고 데이터셋만:  --stages 3 --skip_train
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))
from common import logio  # noqa: E402

logger = logging.getLogger("run")

# 스테이지별 출력 서브디렉토리 (컨벤션)
SUBDIR = {1: "01_mapping", 2: "02_preprocess", 3: "03_3dgs", 4: "04_viewer"}


# ---------------------------------------------------------------------------
# 아티팩트 경로(컨벤션) — 재실행 시 이전 산출물 복구
# ---------------------------------------------------------------------------
def artifacts(out_root: Path) -> dict:
    s1, s2, s3 = (out_root / SUBDIR[i] for i in (1, 2, 3))
    return {
        "point_cloud": s1 / "point_cloud.ply",
        "camera_poses": s1 / "camera_poses.json",
        "images_dir": s1 / "images",
        "clean_ply": s2 / "point_cloud_clean.ply",
        "aligned_poses": s2 / "camera_poses_aligned.json",
        "splat": s3 / "output.splat",
    }


def _conda_exe() -> str:
    exe = shutil.which("conda")
    if exe:
        return exe
    for c in (Path.home() / "anaconda3/bin/conda", Path.home() / "miniconda3/bin/conda"):
        if c.exists():
            return str(c)
    raise RuntimeError("conda 실행파일을 찾을 수 없습니다.")


# ---------------------------------------------------------------------------
# Stage 1 (cross-env subprocess)
# ---------------------------------------------------------------------------
def run_stage1(video, image_dir, out_root, full_cfg, ckpt,
               max_frames=None, fps=None, crop_top=None, crop_bottom=None):
    a = artifacts(out_root)
    s1_dir = out_root / SUBDIR[1]
    s1_dir.mkdir(parents=True, exist_ok=True)

    if image_dir:
        if not Path(image_dir).is_dir():
            raise FileNotFoundError(f"입력 이미지 폴더가 없습니다: {image_dir!r}")
    elif not video or not Path(video).exists():
        raise FileNotFoundError(f"입력 영상/이미지 폴더가 없습니다: video={video!r} image_dir={image_dir!r}")
    if not ckpt or not Path(ckpt).exists():
        raise FileNotFoundError(
            f"LingBot-Map 체크포인트 없음: {ckpt!r}\n"
            "  huggingface 'robbyant/lingbot-map' 에서 lingbot-map-long.pt 다운로드 후 "
            "config.yaml paths.lingbot_ckpt 또는 --ckpt 로 지정."
        )

    params = dict(full_cfg["stage1_mapping"])
    if max_frames is not None:
        params["max_frames"] = max_frames
        logger.info("Stage 1 max_frames 오버라이드: %d (스모크)", max_frames)
    if fps is not None:
        params["fps"] = fps
        logger.info("Stage 1 fps 오버라이드: %d", fps)
    if crop_top is not None:
        params["crop_top"] = crop_top
        logger.info("Stage 1 crop_top 오버라이드: %.3f", crop_top)
    if crop_bottom is not None:
        params["crop_bottom"] = crop_bottom
        logger.info("Stage 1 crop_bottom 오버라이드: %.3f", crop_bottom)
    params.update({
        "video_path": (str(Path(video).resolve()) if video else None),
        "image_dir": (str(Path(image_dir).resolve()) if image_dir else None),
        "out_dir": str(s1_dir),
        "lingbot_repo": str(logio.resolve_path(full_cfg["paths"]["lingbot_repo"])),
        "ckpt": str(Path(ckpt).resolve()),
    })
    pj = s1_dir / "params.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2, ensure_ascii=False)

    env_name = full_cfg["envs"]["lingbot"]
    cmd = [_conda_exe(), "run", "--no-capture-output", "-n", env_name,
           "python", str(_ROOT / "stages" / "stage1_infer.py"), "--params", str(pj)]
    logger.info("Stage 1 (env=%s) 실행: %s", env_name, " ".join(cmd))
    subprocess.run(cmd, check=True)
    if not a["point_cloud"].exists():
        raise RuntimeError("Stage 1 후 point_cloud.ply 가 생성되지 않음")
    logger.info("Stage 1 완료: %s", a["point_cloud"])


# ---------------------------------------------------------------------------
# Stage 2/3/4 (in-process, recon env)
# ---------------------------------------------------------------------------
def run_stage2(out_root, full_cfg):
    from stages import stage2_preprocess as s2
    a = artifacts(out_root)
    if not a["point_cloud"].exists():
        raise FileNotFoundError(f"Stage 2 입력(ply) 없음 — 먼저 Stage 1 실행: {a['point_cloud']}")
    return s2.run(a["point_cloud"],
                  a["camera_poses"] if a["camera_poses"].exists() else None,
                  out_root / SUBDIR[2], full_cfg["stage2_preprocess"])


def run_stage3(out_root, full_cfg, skip_train):
    from stages import stage3_train as s3
    a = artifacts(out_root)
    clean = a["clean_ply"] if a["clean_ply"].exists() else a["point_cloud"]
    poses = a["aligned_poses"] if a["aligned_poses"].exists() else a["camera_poses"]
    if not clean.exists():
        raise FileNotFoundError(f"Stage 3 입력(ply) 없음: {clean}")
    # images 는 학습(train) 모드에서만 필요. pointcloud 모드는 ply 만으로 splat 생성.
    is_train = full_cfg["stage3_train"].get("mode", "pointcloud") == "train" and not skip_train
    if is_train and not a["images_dir"].exists():
        raise FileNotFoundError(f"Stage 3 학습 입력(images) 없음 — Stage 1 산출물 필요: {a['images_dir']}")
    gs_repo = logio.resolve_path(full_cfg["paths"]["gaussian_splatting"])
    return s3.run(clean, poses, a["images_dir"], out_root / SUBDIR[3], gs_repo,
                  full_cfg["stage3_train"], skip_train=skip_train)


def run_stage4(out_root, full_cfg):
    from stages import stage4_viewer as s4
    a = artifacts(out_root)
    poses = a["aligned_poses"] if a["aligned_poses"].exists() else a["camera_poses"]
    return s4.run(a["splat"], poses, out_root / SUBDIR[4], full_cfg["stage4_viewer"])


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="pipeline2: MOV → LingBot-Map → 3DGS → Web")
    ap.add_argument("--video", default=None, help="입력 MOV/MP4 (Stage 1)")
    ap.add_argument("--image_dir", default=None,
                    help="입력 이미지 폴더 (Stage 1, --video 대신). 프레임 jpg/png 들")
    ap.add_argument("--crop_top", type=float, default=None,
                    help="상단 크롭 비율 (image_dir 입력, config 보다 우선)")
    ap.add_argument("--crop_bottom", type=float, default=None,
                    help="하단 차체 크롭 비율 (image_dir 입력, 대시캠 권장 0.27, config 보다 우선)")
    ap.add_argument("--out_root", default=None, help="출력 루트 (기본: outputs/p2_run_<ts>)")
    ap.add_argument("--stages", default="1,2,3,4", help="실행할 스테이지 (예: 1,2,3,4)")
    ap.add_argument("--config", default=str(_ROOT / "config.yaml"))
    ap.add_argument("--ckpt", default=None, help="LingBot-Map .pt (config 보다 우선)")
    ap.add_argument("--max_frames", type=int, default=None,
                    help="Stage 1 프레임 수 제한(스모크 테스트용, config 보다 우선)")
    ap.add_argument("--fps", type=int, default=None, help="Stage 1 샘플링 fps (config 보다 우선)")
    ap.add_argument("--skip_train", action="store_true", help="Stage 3 학습 생략(COLMAP만)")
    args = ap.parse_args()

    full_cfg = logio.load_config(args.config)
    stages = [int(s) for s in args.stages.split(",") if s.strip()]

    if args.out_root:
        out_root = Path(args.out_root).expanduser().resolve()
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_root = logio.resolve_path("ai-pipeline/outputs") / f"p2_run_{ts}"
    out_root.mkdir(parents=True, exist_ok=True)
    logio.setup_logging(out_root / "logs", name="pipeline2")

    ckpt = args.ckpt or full_cfg.get("paths", {}).get("lingbot_ckpt", "")

    logger.info("=== pipeline2 ===")
    logger.info("video=%s  image_dir=%s", args.video, args.image_dir)
    logger.info("out_root=%s", out_root)
    logger.info("stages=%s  skip_train=%s", stages, args.skip_train)

    results = {}
    if 1 in stages:
        run_stage1(args.video, args.image_dir, out_root, full_cfg, ckpt,
                   max_frames=args.max_frames, fps=args.fps,
                   crop_top=args.crop_top, crop_bottom=args.crop_bottom)
    if 2 in stages:
        results["stage2"] = run_stage2(out_root, full_cfg)
    if 3 in stages:
        results["stage3"] = run_stage3(out_root, full_cfg, args.skip_train)
    if 4 in stages:
        results["stage4"] = run_stage4(out_root, full_cfg)

    logger.info("=== 완료 ===\n%s", json.dumps(results, indent=2, ensure_ascii=False))
    print(json.dumps({"out_root": str(out_root), **results}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
