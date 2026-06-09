"""Stage 4 — 웹 뷰어 자산 조립.

web/ 템플릿(HTML/JS/CSS)을 <out_dir>/viewer/ 로 복사하고,
output.splat + camera_poses_aligned.json + config.json 을 넣는다.
정적 서버로 열면 splat 렌더 + 차량 경로 애니메이션이 동작.

실행 환경: 무관 (stdlib 만).
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))
from common import logio  # noqa: E402

logger = logging.getLogger(__name__)
_WEB_TEMPLATE = _PKG_ROOT / "web"


def run(splat_path, poses_path, out_dir, cfg) -> dict:
    out_dir = Path(out_dir)
    viewer = out_dir / "viewer"
    viewer.mkdir(parents=True, exist_ok=True)

    # 템플릿 복사
    for name in ("index.html", "main.js", "style.css"):
        shutil.copy2(_WEB_TEMPLATE / name, viewer / name)

    # 자산 복사
    splat_path = Path(splat_path)
    if splat_path.exists():
        shutil.copy2(splat_path, viewer / "output.splat")
    else:
        logger.warning("splat 없음(뷰어는 경로만 표시): %s", splat_path)

    poses_path = Path(poses_path)
    if poses_path.exists():
        shutil.copy2(poses_path, viewer / "camera_poses.json")
    else:
        logger.warning("poses 없음: %s", poses_path)

    # 뷰어 설정
    viewer_cfg = {
        "splat_url": "./output.splat",
        "poses_url": "./camera_poses.json",
        "camera_fps": cfg.get("camera_fps", 30),
        "vehicle_model": cfg.get("vehicle_model", "cone"),
        "background": cfg.get("background", "#0b0e14"),
        "point_size": cfg.get("point_size", 1.0),
        "splat_rotation": cfg.get("splat_rotation", [0, 0, 0]),
    }
    with open(viewer / "config.json", "w", encoding="utf-8") as f:
        json.dump(viewer_cfg, f, indent=2, ensure_ascii=False)

    logger.info("Stage 4 완료 → %s", viewer)
    logger.info("실행: cd %s && python -m http.server 8000  →  http://localhost:8000", viewer)
    return {"viewer_dir": str(viewer), "serve_cmd": f"cd {viewer} && python -m http.server 8000"}


def main():
    ap = argparse.ArgumentParser(description="Stage 4: 웹 뷰어 조립")
    ap.add_argument("--splat", required=True)
    ap.add_argument("--poses", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    logio.setup_logging(out_dir, name="stage4")
    cfg = logio.load_config(args.config)["stage4_viewer"]
    result = run(args.splat, args.poses, out_dir, cfg)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
