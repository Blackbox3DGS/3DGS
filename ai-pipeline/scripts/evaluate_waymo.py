#!/usr/bin/env python3
"""Quantitative evaluation CLI — Waymo GT vs estimated accident scene.

Two subcommands matching the two-phase design (Stage 13):

  extract-gt   TFRecord -> gt.json. Needs tensorflow + waymo-open-dataset,
               so run inside the pipeline Docker image (or the GPU server):

      docker run --rm -v ~/Downloads:/in -v $(pwd)/ai-pipeline/data:/out \\
          --entrypoint python3 3dgs-lingbot:cu118 \\
          ai-pipeline/scripts/evaluate_waymo.py extract-gt \\
          --tfrecord /in/sample1.tfrecord --out /out/waymo/sample1/gt.json

  evaluate     gt.json + vehicles.json + bbox_sequence.json -> metrics.json,
               report.md, plots/. numpy + matplotlib only; runs on the mac:

      python3 ai-pipeline/scripts/evaluate_waymo.py evaluate \\
          --gt ai-pipeline/data/waymo/sample1/gt.json \\
          --vehicles frontend/public/sample3_vehicles.json \\
          --bbox frontend/public/sample3_bbox.json \\
          --images ai-pipeline/data/waymo/sample1/images_colmap \\
          --out ai-pipeline/outputs/eval_sample1
"""

import argparse
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("extract-gt", help="TFRecord -> gt.json (needs TF/waymo pkgs)")
    g.add_argument("--tfrecord", required=True)
    g.add_argument("--out", required=True, help="gt.json output path")
    g.add_argument("--every_n", type=int, default=1)
    g.add_argument("--max_frames", type=int, default=None)

    e = sub.add_parser("evaluate", help="gt.json + estimates -> metrics/report/plots")
    e.add_argument("--gt", required=True, help="gt.json from extract-gt")
    e.add_argument("--vehicles", required=True, help="vehicles.json (est trajectories)")
    e.add_argument("--bbox", required=True, help="Stage-03 bbox_sequence.json")
    e.add_argument("--out", required=True, help="output directory")
    e.add_argument("--images", default=None,
                   help="images_colmap dir with frame_XXXXXX_<ts>.jpg names "
                        "(optional; verifies frame<->GT sync)")
    e.add_argument("--fps", type=float, default=10.0)
    e.add_argument("--camera_height_prior", type=float, default=2.115,
                   help="camera height above road in meters (Waymo FRONT ~2.115; "
                        "used only for the prior-scale cross-check)")

    args = ap.parse_args()

    if args.cmd == "extract-gt":
        import importlib
        waymo_gt = importlib.import_module("13_eval.eval_step.waymo_gt")
        waymo_gt.extract_waymo_gt(args.tfrecord, args.out,
                                  every_n=args.every_n, max_frames=args.max_frames)
    else:
        import importlib
        import logging
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        eval_step = importlib.import_module("13_eval.eval_step")
        payload = eval_step.run_evaluation(
            args.gt, args.vehicles, args.bbox, args.out,
            fps=args.fps,
            camera_height_prior_m=args.camera_height_prior,
            images_dir=args.images,
        )
        al = payload["alignment"]
        print(f"\n=== Summary ===")
        print(f"scale s = {al['s']:.3f} m/unit (det {al['det']:+d}), "
              f"ego align RMSE = {al['rmse_m']:.2f} m")
        for tid, res in sorted(payload["tracks"].items(), key=lambda kv: int(kv[0])):
            if res.get("n_frames", 0) < 2:
                continue
            print(f"track #{tid}: pos err mean {res['position_error_m']['mean']:.2f} m, "
                  f"rel-dist err mean {res['relative_distance_error_m']['mean']:.2f} m "
                  f"({res['relative_distance_error_pct']['mean']:.1f}%), "
                  f"ADE {res['ade_m']:.2f} m, "
                  f"speed err {res['speed_error_kmh']['mean']:.1f} km/h")
        ego = payload["ego"]
        if ego.get("speed_error_kmh_mean") is not None:
            print(f"ego: speed err mean {ego['speed_error_kmh_mean']:.1f} km/h")
        print(f"\nreport: {Path(args.out) / 'report.md'}")


if __name__ == "__main__":
    main()
