"""Stage 13 — quantitative evaluation vs Waymo GT.

Two-phase design (local mac cannot install tensorflow/waymo-open-dataset):

  1. `extract-gt` (Docker / GPU server, one-shot):  TFRecord -> gt.json
     -> see `waymo_gt.extract_waymo_gt`
  2. `evaluate` (numpy/matplotlib only, runs anywhere): vehicles.json +
     bbox_sequence.json + gt.json -> metrics.json / report.md / plots
     -> `run_evaluation` below

`run(context)` plugs phase 2 into the pipeline orchestrator; it is NOT in the
default step list — run explicitly with `--steps ...,13_eval` on a waymo input
after producing gt.json.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import numpy as np

from . import association, alignment, metrics, report

logger = logging.getLogger(__name__)

DEFAULT_FPS = 10.0
# Waymo FRONT camera height above road (m): z of extrinsic translation is
# ~2.115 for this vehicle; used only for the prior-scale cross-check.
WAYMO_CAMERA_HEIGHT_M = 2.115


def _verify_frame_sync(gt: dict, images_dir: Path | None) -> None:
    """Check est frame index -> GT record alignment via filename timestamps."""
    if images_dir is None or not images_dir.exists():
        return
    ts_by_index = {fr["index"]: fr["timestamp_micros"] for fr in gt["frames"]}
    pat = re.compile(r"frame_(\d{6})_(\d+)\.jpe?g$")
    checked = mismatched = 0
    for p in sorted(images_dir.iterdir()):
        m = pat.match(p.name)
        if not m:
            continue
        idx, ts = int(m.group(1)), int(m.group(2))
        if idx in ts_by_index:
            checked += 1
            if ts_by_index[idx] != ts:
                mismatched += 1
    if checked:
        if mismatched:
            logger.warning("Frame sync: %d/%d filename timestamps mismatch GT!",
                           mismatched, checked)
        else:
            logger.info("Frame sync OK: %d filename timestamps match GT.", checked)


def run_evaluation(
    gt_path: str | os.PathLike,
    vehicles_path: str | os.PathLike,
    bbox_path: str | os.PathLike,
    out_dir: str | os.PathLike,
    fps: float = DEFAULT_FPS,
    camera_height_prior_m: float = WAYMO_CAMERA_HEIGHT_M,
    images_dir: str | os.PathLike | None = None,
) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(gt_path) as f:
        gt = json.load(f)
    with open(vehicles_path) as f:
        veh = json.load(f)
    with open(bbox_path) as f:
        bseq = json.load(f)

    _verify_frame_sync(gt, Path(images_dir) if images_dir else None)

    vehicles = veh["vehicles"]
    ego = next(v for v in vehicles if v["class"] == "ego")
    dyn = [v for v in vehicles if v["class"] != "ego" and len(v["points"]) >= 2]

    ego_by_frame = metrics.track_points_by_frame(ego)
    cam_by_frame = metrics.gt_camera_positions(gt)

    # Prior-based scale (what the viewer HUD uses when GT is unavailable):
    # ground is y=0 after the export's recenter, so ego_y = camera height.
    ego_y_median = float(np.median([p[1] for p in ego["points"]]))
    mpu_prior = camera_height_prior_m / max(ego_y_median, 1e-9)

    # --- 1. Candidate alignments on the ego path (both handedness) --------
    common = sorted(set(ego_by_frame) & set(cam_by_frame))
    est_ego = np.array([ego_by_frame[f] for f in common])
    gt_cam = np.array([cam_by_frame[f] for f in common])
    cand = alignment.align_ego_path(est_ego, gt_cam)

    # --- 2. Track association ---------------------------------------------
    assoc = association.associate_tracks(bseq, gt, [v["id"] for v in dyn])
    logger.info("Associated %d/%d dynamic tracks with GT ids.", len(assoc), len(dyn))

    # --- 3. Gather matched-track data, then resolve handedness ------------
    matched = {}
    for v in dyn:
        tid = v["id"]
        if tid not in assoc:
            continue
        gt_states = metrics.gt_label_states(gt, assoc[tid]["gt_id"])
        est_by_frame = metrics.track_points_by_frame(v)
        frames = sorted(set(est_by_frame) & set(gt_states) & set(cam_by_frame))
        if len(frames) < 2:
            continue
        matched[tid] = {
            "frames": frames,
            "gt_states": gt_states,
            "est_by_frame": est_by_frame,
            "est_pts": np.array([est_by_frame[f] for f in frames]),
            "gt_near_xy": np.array([gt_states[f]["near_face"][:2] for f in frames]),
        }

    def _track_residual(f: dict) -> float:
        """Mean BEV error of matched tracks under a candidate fit — breaks the
        left/right mirror tie a (near-)straight ego path cannot decide."""
        errs = [
            float(np.linalg.norm(
                alignment.apply_similarity(m["est_pts"], f)[:, :2] - m["gt_near_xy"],
                axis=1).mean())
            for m in matched.values()
        ]
        return float(np.mean(errs)) if errs else float("inf")

    fit = alignment.choose_fit(cand["fits"], _track_residual)
    logger.info("Alignment: s=%.3f m/unit, det=%+d (%s%s), ego rmse=%.2f m "
                "(prior mpu=%.3f)",
                fit["s"], fit["det"], fit["handedness_source"],
                ", ego path ambiguous" if fit["ego_path_ambiguous"] else "",
                fit["rmse_m"], mpu_prior)

    # --- 4. Per-track metrics ----------------------------------------------
    track_results = {}
    bev_gt_tracks, bev_est_tracks = {}, {}
    for tid, m in matched.items():
        aligned = alignment.apply_similarity(m["est_pts"], fit)
        aligned_by_frame = {f: aligned[i] for i, f in enumerate(m["frames"])}

        track_results[tid] = metrics.evaluate_track(
            m["est_by_frame"], ego_by_frame, m["gt_states"], cam_by_frame,
            aligned_by_frame, fit["s"], fps,
        )
        bev_gt_tracks[tid] = m["gt_near_xy"]
        bev_est_tracks[tid] = aligned[:, :2]

    # --- 5. Ego speed ------------------------------------------------------
    ego_result = metrics.evaluate_ego_speed(ego_by_frame, cam_by_frame, fit["s"], fps)

    # --- 6. Outputs ----------------------------------------------------------
    payload = {
        "meta": {
            "scene_name": gt.get("scene_name"),
            "num_frames": len(common),
            "fps": fps,
            "vehicles_path": str(vehicles_path),
            "gt_path": str(gt_path),
            "camera_height_prior_m": camera_height_prior_m,
            "mpu_prior": mpu_prior,
            "ego_y_median": ego_y_median,
        },
        "alignment": {
            "s": fit["s"], "det": fit["det"],
            "rmse_m": fit["rmse_m"], "rmse_other_det_m": fit["rmse_other_det_m"],
            "handedness_source": fit["handedness_source"],
            "ego_path_ambiguous": fit["ego_path_ambiguous"],
            "track_residual_m": fit.get("track_residual_m"),
            "R2": np.asarray(fit["R2"]).tolist(),
            "t2": np.asarray(fit["t2"]).tolist(),
            "tz": fit["tz"],
            "n_points": cand["n_points"],
        },
        "association": assoc,
        "tracks": track_results,
        "ego": ego_result,
    }

    report.write_metrics_json(out_dir, payload)
    aligned_ego = alignment.apply_similarity(est_ego, fit)
    report.plot_bev_overlay(out_dir, gt_cam[:, :2], bev_gt_tracks,
                            aligned_ego[:, :2], bev_est_tracks)
    report.plot_error_series(out_dir, track_results, fps)
    report.plot_speed_comparison(out_dir, track_results, ego_result, fps)
    report.write_report_md(out_dir, payload)

    logger.info("Evaluation written to %s", out_dir)
    return payload


# --------------------------------------------------------------------------
# Orchestrator hook
# --------------------------------------------------------------------------

def run(context: dict) -> dict:
    """Pipeline stage entry. Requires a waymo input + a pre-extracted gt.json.

    gt.json lookup order: $WAYMO_GT_JSON, <out_root>/13_eval/gt.json,
    <input_dir>/gt.json (next to the tfrecord).
    """
    out_root = Path(context["out_root"])
    out_dir = out_root / "13_eval"

    if context.get("input_type") != "waymo":
        logger.info("13_eval skipped: input_type is not 'waymo'.")
        return context

    candidates = [
        os.environ.get("WAYMO_GT_JSON"),
        out_dir / "gt.json",
        Path(context["input_path"]).parent / "gt.json",
    ]
    gt_path = next((Path(c) for c in candidates if c and Path(c).exists()), None)
    if gt_path is None:
        logger.warning("13_eval skipped: no gt.json found. Run "
                       "`scripts/evaluate_waymo.py extract-gt` first.")
        return context

    artifacts = context["artifacts"]
    vehicles_path = artifacts.get("viewer_vehicles") or (out_root / "12_viewer" / "data" / "vehicles.json")
    bbox_path = artifacts.get("bbox_sequence") or (out_root / "03_seg" / "bbox_sequence.json")
    images_dir = artifacts.get("images_colmap")

    if not Path(vehicles_path).exists() or not Path(bbox_path).exists():
        logger.warning("13_eval skipped: vehicles.json or bbox_sequence.json missing.")
        return context

    run_evaluation(gt_path, vehicles_path, bbox_path, out_dir,
                   images_dir=images_dir)

    artifacts["eval_metrics"] = str(out_dir / "metrics.json")
    artifacts["eval_report"] = str(out_dir / "report.md")
    return context
