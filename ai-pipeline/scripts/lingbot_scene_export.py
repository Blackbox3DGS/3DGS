#!/usr/bin/env python3
"""LingBot scene export: images → background .splat + vehicles.json (ego + dynamic).

Self-contained runner that uses lingbot-map only as an installed library (no
edits to the lingbot clone, no scp). Reuses Stage-04g's `run_inference` for the
LingBot forward pass, then writes a web-renderable point-cloud `.splat` plus a
`vehicles.json` (ego blackbox path + dynamic-vehicle trajectories) in the same
ground-aligned, recentered frame for the React frontend.

Example:
    CUDA_VISIBLE_DEVICES=0 python ai-pipeline/scripts/lingbot_scene_export.py \\
        --model_path /data/byungk/lingbot-map-long.pt \\
        --image_folder <run>/02_ingest/images_colmap \\
        --dynamic_mask_dir <run>/03_seg/masks \\
        --bbox_sequence <run>/03_seg/bbox_sequence.json \\
        --out_splat out/sample3.splat \\
        --out_vehicles out/sample3_vehicles.json
"""

import argparse
import importlib
import sys
from pathlib import Path

# ai-pipeline/src on path so the digit-prefixed Stage-04g package is importable.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

run_inference = importlib.import_module("04g_lingbot.lingbot.inference").run_inference
predictions_to_splat = importlib.import_module("04g_lingbot.lingbot.splat_export").predictions_to_splat
export_trajectories_json = importlib.import_module("04g_lingbot.lingbot.trajectory_export").export_trajectories_json


def main():
    ap = argparse.ArgumentParser(description="LingBot → .splat + vehicles.json")
    ap.add_argument("--model_path", required=True)
    ap.add_argument("--image_folder", required=True)
    ap.add_argument("--out_splat", required=True)
    ap.add_argument("--out_vehicles", default=None,
                    help="vehicles.json output (ego + dynamic). Needs --bbox_sequence + --dynamic_mask_dir.")
    ap.add_argument("--dynamic_mask_dir", default=None, help="Stage-03 white=dynamic PNG masks")
    ap.add_argument("--bbox_sequence", default=None, help="Stage-03 bbox_sequence.json")
    ap.add_argument("--conf_threshold", type=float, default=2.0)
    ap.add_argument("--splat_up", choices=["y+", "y-"], default="y+",
                    help="Ground-align up axis: y+ for the Three.js/gsplat frontend, y- for antimatter15")
    ap.add_argument("--splat_point_size", type=float, default=None)
    ap.add_argument("--splat_max_points", type=int, default=2_000_000)
    ap.add_argument("--camera_height_prior", type=float, default=1.4,
                    help="real camera height above road in meters (dashcam ~1.4, "
                         "Waymo FRONT ~2.115) — sets vehicles.json meters_per_unit")
    ap.add_argument("--collision", default=None,
                    help="Stage-03c collision.json — embeds collision/ego_role into vehicles.json")
    ap.add_argument("--fps", type=float, default=10.0,
                    help="frame rate of the extracted frames (vehicles.json metadata)")
    args = ap.parse_args()

    image_paths = sorted([p for p in Path(args.image_folder).iterdir()
                          if p.suffix.lower() in (".jpg", ".jpeg", ".png")])
    if not image_paths:
        raise SystemExit(f"No images in {args.image_folder}")
    print(f"LingBot inference on {len(image_paths)} frames...")

    pred = run_inference(image_paths, args.model_path)

    vis = {
        "images": pred["images_proc"],          # (S,3,H,W) [0,1]
        "depth": pred.get("depth"),             # (S,H,W)
        "depth_conf": pred.get("depth_conf"),
        "extrinsic": pred["extrinsic_c2w"],     # (S,3,4) c2w
        "intrinsic": pred["intrinsic"],         # (S,3,3) processed res
        "world_points": pred.get("world_points"),
        "world_points_conf": pred.get("world_points_conf"),
    }

    up = (0.0, 1.0, 0.0) if args.splat_up == "y+" else (0.0, -1.0, 0.0)
    frame_paths = [str(p) for p in image_paths]

    _, R, center, ground_n, ground_p = predictions_to_splat(
        vis, args.out_splat,
        conf_threshold=args.conf_threshold,
        mask_sky=True,
        image_folder=args.image_folder,
        dynamic_mask_dir=args.dynamic_mask_dir,
        frame_paths=frame_paths,
        point_size=args.splat_point_size,
        max_points=args.splat_max_points,
        up_axis=up,
    )

    if args.out_vehicles:
        export_trajectories_json(
            vis, args.out_vehicles,
            frame_paths=frame_paths,
            center=center, R=R,
            bbox_sequence_path=args.bbox_sequence,
            dynamic_mask_dir=args.dynamic_mask_dir,
            ground_normal=ground_n, ground_point=ground_p,  # 지면 광선 교차로 차량 위치
            camera_height_prior_m=args.camera_height_prior,
            fps=args.fps,
            collision_path=args.collision,
        )

    print("Done.")


if __name__ == "__main__":
    main()
