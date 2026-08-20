#!/usr/bin/env python3
"""Patch existing demo vehicles.json files with metric-scale metadata.

The pipeline exporter (04g_lingbot/trajectory_export.py) now writes
`meters_per_unit` / `camera_height_prior_m` / `fps` into vehicles.json, but the
already-exported demo assets predate that. This tool injects the same fields
using the identical formula: meters_per_unit = camera_height_prior_m /
median(ego_y) (the exporter recenters the road plane to y=0, so ego_y IS the
camera height in scene units).

Priors: Waymo FRONT camera ~2.115 m, dashcam ~1.4 m.

Usage:
    python3 tools/add_scale_to_vehicles.py \
        --waymo frontend/public/sample3_vehicles.json \
        --dashcam "frontend/public/clips/*_vehicles.json"

Idempotent — re-running overwrites the same fields.
"""

import argparse
import glob
import json
import statistics
import sys

WAYMO_PRIOR_M = 2.115
DASHCAM_PRIOR_M = 1.4
DEFAULT_FPS = 10.0


def patch(path: str, prior_m: float, fps: float) -> bool:
    with open(path) as f:
        data = json.load(f)
    vehicles = data.get("vehicles", [])
    ego = next((v for v in vehicles if v.get("class") == "ego"), None)
    if not ego or len(ego.get("points", [])) < 3:
        print(f"  SKIP {path}: no ego track")
        return False

    ego_y = statistics.median(p[1] for p in ego["points"])
    if ego_y <= 1e-9:
        print(f"  SKIP {path}: ego height ~0 (not ground-aligned?)")
        return False

    mpu = prior_m / ego_y

    # 신뢰성 검사: 이 스케일로 환산한 ego 중앙값 속도가 비현실적이면(정렬 실패
    # 징후 — 예: crash8은 ego_y≈0.003 → 498 m/unit) 필드를 쓰지 않는다. 뷰어는
    # 필드가 없으면 자체 prior fallback을 쓰고 "≈" 근사 표기를 유지한다.
    pts = ego["points"]
    fps = data.get("fps") or DEFAULT_FPS
    speeds = []
    for a, b in zip(pts[:-2], pts[2:]):
        df = (b[3] - a[3]) or 1
        d = ((b[0] - a[0]) ** 2 + (b[2] - a[2]) ** 2) ** 0.5
        speeds.append(d * mpu / (df / fps) * 3.6)   # km/h
    med_kmh = statistics.median(speeds) if speeds else 0.0
    if not (1.0 <= med_kmh <= 150.0):
        print(f"  SKIP {path}: implausible ego speed {med_kmh:.0f} km/h at "
              f"{mpu:.1f} m/unit (ground alignment suspect)")
        return False

    data["meters_per_unit"] = mpu
    data["camera_height_prior_m"] = prior_m
    data["fps"] = fps

    # 키 순서 유지: 메타 → vehicles
    ordered = {k: data[k] for k in data if k != "vehicles"}
    ordered["vehicles"] = vehicles
    with open(path, "w") as f:
        json.dump(ordered, f)

    print(f"  OK   {path}: ego_y={ego_y:.4f} -> {data['meters_per_unit']:.2f} m/unit "
          f"(prior {prior_m} m)")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--waymo", nargs="*", default=[],
                    help="vehicles.json paths/globs with Waymo camera height prior")
    ap.add_argument("--dashcam", nargs="*", default=[],
                    help="vehicles.json paths/globs with dashcam camera height prior")
    ap.add_argument("--fps", type=float, default=DEFAULT_FPS)
    args = ap.parse_args()

    n = 0
    for prior, patterns in ((WAYMO_PRIOR_M, args.waymo), (DASHCAM_PRIOR_M, args.dashcam)):
        for pattern in patterns:
            paths = sorted(glob.glob(pattern)) or [pattern]
            for p in paths:
                try:
                    n += patch(p, prior, args.fps)
                except (OSError, json.JSONDecodeError) as e:
                    print(f"  FAIL {p}: {e}", file=sys.stderr)
    print(f"Patched {n} file(s).")


if __name__ == "__main__":
    main()
