#!/usr/bin/env python3
"""Merge Stage-03c collision.json results into existing demo vehicles.json.

Newly exported scenes get collision embedded by lingbot_scene_export
--collision; this patches the already-exported demo clips.

    python3 tools/merge_collision.py \
        --vehicles frontend/public/clips/crash4_vehicles.json \
        --collision <run>/03c_collision/collision.json

Idempotent. Frame indices must share the same extraction (10 fps Stage 02).
"""

import argparse
import json


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vehicles", required=True)
    ap.add_argument("--collision", required=True)
    args = ap.parse_args()

    with open(args.collision) as f:
        col = json.load(f)
    with open(args.vehicles) as f:
        veh = json.load(f)

    veh["collision"] = col.get("collision")
    veh["ego_role"] = col.get("ego_role")

    ordered = {k: veh[k] for k in veh if k != "vehicles"}
    ordered["vehicles"] = veh["vehicles"]
    with open(args.vehicles, "w") as f:
        json.dump(ordered, f)

    c = veh["collision"]
    print(f"{args.vehicles}: " + (
        f"collision frame {c['frame_idx']} ({c['type']}, conf {c['confidence']})"
        if c else "collision null (미검출)"))


if __name__ == "__main__":
    main()
