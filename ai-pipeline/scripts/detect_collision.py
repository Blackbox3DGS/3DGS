#!/usr/bin/env python3
"""Frame-evidence collision detection CLI (Stage 03c).

    python3 ai-pipeline/scripts/detect_collision.py \
        --images <run>/02_ingest/images_colmap \
        --bbox <run>/03_seg/bbox_sequence.json \
        --out <run>/03c_collision/collision.json

CPU-only, runs in seconds. Output: collision moment (frame/time), type
(ego=당사자 / observed=목격자), confidence, involved track ids.
"""

import argparse
import logging
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--images", required=True, help="frames directory (Stage 02)")
    ap.add_argument("--bbox", required=True, help="bbox_sequence.json (Stage 03)")
    ap.add_argument("--out", required=True, help="collision.json output path")
    ap.add_argument("--fps", type=float, default=10.0)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    import importlib
    step = importlib.import_module("03c_collision.collision_step")
    result = step.run_detection(args.images, args.bbox, args.out, fps=args.fps)

    col = result["collision"]
    if col:
        role = {"ego": "당사자(ego 관여)", "observed": "목격자(제3자 충돌)"}[col["type"]]
        print(f"\n충돌 검출: 프레임 {col['frame_idx']} (t={col['time_s']}s) — {role}, "
              f"신뢰도 {col['confidence']}, 트랙 {col['track_ids']}")
    else:
        print("\n충돌 미검출 — 일반 주행 장면으로 판단")


if __name__ == "__main__":
    main()
