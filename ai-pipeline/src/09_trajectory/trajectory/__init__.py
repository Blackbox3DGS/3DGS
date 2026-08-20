"""Stage 09: 3D Vehicle Trajectory Extraction.

For every dynamic track in bbox_sequence.json, sample a robust depth from the
lower 40% of the per-frame mask (rear bumper region, P20–P30 depth percentile)
and unproject (u, v, depth) into world space. Per-track 3D positions are then
filtered through a constant-velocity Kalman filter (AB3DMOT KF) with
predict-only interpolation across short occlusion gaps. Output: trajectories.json.

Coordinate frame matches Stage 04's c2w (`colmap_world`). Velocity is reported
in m/s assuming Stage 02's 10 fps extraction.
"""

import json
import logging
import traceback
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

from .extractor import (
    build_frame_index,
    build_per_frame_track_bboxes,
    collect_other_bboxes,
    sample_track_frame,
)
from .tracker import Track3DKalman
from .unproject import pixel_to_world
from .visualizer import render_topdown
from .writer import write_trajectories

logger = logging.getLogger(__name__)

# ROI / depth sampling (unchanged).
LOWER_FRAC = 0.40
PCT_LOW = 20.0
PCT_HIGH = 30.0
MIN_ROI_PIXELS = 20
MIN_PCT_PIXELS = 5

# Kalman filter / occlusion interpolation.
MAX_PREDICT_GAP = 5         # consecutive predict-only frames before splitting
KF_OBSERVATION_NOISE = 1.0  # scales AB3DMOT's measurement noise on (x, y, z)
ASSUMED_FPS = 10            # Stage 02 default; used to convert KF vel (m/frame) → m/s


def run(context):
    """Stage 09 entry point.

    Reads (from context["artifacts"]):
        bbox_sequence, segmentation_masks, target_ids,
        images_colmap, scaled_depth_maps,
        poses, intrinsics, registered_frames

    Writes:
        context["artifacts"]["trajectories"] = "<out_root>/09_trajectory/trajectories.json"
    """
    try:
        return _run_impl(context)
    except Exception:
        logger.error("Stage 09 failed:\n%s", traceback.format_exc())
        raise


def _resolve_target_ids(target_ids_artifact, bbox_sequence: dict) -> set[str]:
    tracks = bbox_sequence.get("tracks", {})
    if target_ids_artifact == "all_dynamic" or target_ids_artifact is None:
        return {
            tid
            for tid, tinfo in tracks.items()
            if tinfo.get("state") == "dynamic" and tid != "-1"
        }
    if isinstance(target_ids_artifact, str):
        return {t.strip() for t in target_ids_artifact.split(",") if t.strip()}
    if isinstance(target_ids_artifact, (list, tuple, set)):
        return {str(t) for t in target_ids_artifact}
    raise ValueError(f"Unsupported target_ids type: {type(target_ids_artifact)}")


def _kf_track_points(
    tid: str,
    obs_by_frame: dict[int, dict],
    sorted_filenames: list[str],
) -> list[dict]:
    """Run per-track KF + occlusion-gap predict over [first_obs ... last_obs].

    Splits the track silently when consecutive predict-only ticks exceed
    MAX_PREDICT_GAP — the next observation re-initialises a fresh KF and the
    output `points` list simply has a real gap in `frame_idx`.
    """
    frame_indices = sorted(obs_by_frame.keys())
    first_f, last_f = frame_indices[0], frame_indices[-1]

    kf: Track3DKalman | None = None
    points: list[dict] = []

    for f in range(first_f, last_f + 1):
        obs = obs_by_frame.get(f)

        if kf is None:
            if obs is None:
                continue
            kf = Track3DKalman(obs["xyz"], tid, observation_noise=KF_OBSERVATION_NOISE)
            points.append(_make_point(f, kf, obs, interpolated=False))
            continue

        kf.predict()
        if obs is not None:
            kf.update(obs["xyz"])
            points.append(_make_point(f, kf, obs, interpolated=False))
        elif kf.frames_since_update <= MAX_PREDICT_GAP:
            fname = sorted_filenames[f] if 0 <= f < len(sorted_filenames) else None
            points.append(_make_point(f, kf, None, interpolated=True, frame_name=fname))
        else:
            kf = None

    return points


def _make_point(
    frame_idx: int,
    kf: Track3DKalman,
    obs: dict | None,
    *,
    interpolated: bool,
    frame_name: str | None = None,
) -> dict:
    x, y, z = kf.xyz()
    vx, vy, vz = kf.velocity_per_frame()
    fname = obs["frame_name"] if obs is not None else frame_name
    depth = obs["depth_m"] if obs is not None else None
    return {
        "frame_idx": frame_idx,
        "frame_name": fname,
        "xyz": [x, y, z],
        "velocity_mps": [vx * ASSUMED_FPS, vy * ASSUMED_FPS, vz * ASSUMED_FPS],
        "depth_m": depth,
        "interpolated": interpolated,
    }


def _run_impl(context):
    artifacts = context["artifacts"]

    # ── paths ──────────────────────────────────────────────────────────
    required_keys = [
        "bbox_sequence",
        "segmentation_masks",
        "images_colmap",
        "scaled_depth_maps",
        "poses",
        "intrinsics",
        "registered_frames",
    ]
    for k in required_keys:
        if k not in artifacts:
            raise FileNotFoundError(f"Stage 09 missing required artifact: {k}")

    bbox_path = Path(artifacts["bbox_sequence"])
    mask_dir = Path(artifacts["segmentation_masks"])
    images_dir = Path(artifacts["images_colmap"])
    depth_dir = Path(artifacts["scaled_depth_maps"])
    poses_path = Path(artifacts["poses"])
    intrinsics_path = Path(artifacts["intrinsics"])
    reg_path = Path(artifacts["registered_frames"])

    for p in (bbox_path, poses_path, intrinsics_path, reg_path):
        if not p.exists():
            raise FileNotFoundError(f"Stage 09 input file missing: {p}")
    for d in (mask_dir, images_dir, depth_dir):
        if not d.is_dir():
            raise FileNotFoundError(f"Stage 09 input dir missing: {d}")

    out_root = Path(context["out_root"])
    workspace = out_root / "09_trajectory"
    workspace.mkdir(parents=True, exist_ok=True)
    out_json = workspace / "trajectories.json"

    # ── Step 1/4: Load inputs ──────────────────────────────────────────
    logger.info("Step 1/4: Loading bbox_sequence, poses, intrinsics, registered_frames...")
    with open(bbox_path) as f:
        bbox_sequence = json.load(f)
    poses = np.load(poses_path)  # (M, 4, 4)
    with open(intrinsics_path) as f:
        intrinsics = json.load(f)
    with open(reg_path) as f:
        reg_frames = json.load(f)["frames"]

    fx, fy = intrinsics["fx"], intrinsics["fy"]
    cx, cy = intrinsics["cx"], intrinsics["cy"]

    target_set = _resolve_target_ids(artifacts.get("target_ids"), bbox_sequence)
    if not target_set:
        logger.warning("Stage 09: no target tracks found — writing empty trajectories.")

    # ── Step 2/4: Index construction ───────────────────────────────────
    logger.info(
        "Step 2/4: Indexing %d target tracks across %d registered frames...",
        len(target_set), len(reg_frames),
    )
    sorted_filenames, fname_to_pose_idx = build_frame_index(images_dir, reg_frames)
    work_by_frame = build_per_frame_track_bboxes(bbox_sequence, target_set)

    # ── Step 3/4: Frame-major sampling → per-track raw observations ────
    logger.info(
        "Step 3/4: Sampling depth percentiles per (track, frame) — %d frames have target tracks...",
        len(work_by_frame),
    )
    raw_obs: dict[str, dict[int, dict]] = defaultdict(dict)
    skipped: Counter = Counter()
    processed_frames = 0

    for frame_idx in sorted(work_by_frame):
        frame_tracks = work_by_frame[frame_idx]
        n_in_frame = len(frame_tracks)

        if frame_idx >= len(sorted_filenames):
            skipped["frame_idx_out_of_range"] += n_in_frame
            continue
        fname = sorted_filenames[frame_idx]
        if fname not in fname_to_pose_idx:
            skipped["unregistered_frame"] += n_in_frame
            continue
        pose_idx = fname_to_pose_idx[fname]
        c2w = poses[pose_idx]

        stem = Path(fname).stem
        mask_path = mask_dir / f"{stem}.png"
        depth_path = depth_dir / f"{stem}.npy"
        if not mask_path.exists() or not depth_path.exists():
            skipped["mask_or_depth_missing"] += n_in_frame
            continue
        mask_img = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if mask_img is None:
            skipped["mask_or_depth_missing"] += n_in_frame
            continue
        depth_map = np.load(depth_path)

        for tid, bbox in frame_tracks:
            others = collect_other_bboxes(frame_tracks, tid, bbox)
            sample = sample_track_frame(
                mask_img, depth_map, bbox, others,
                lower_frac=LOWER_FRAC,
                pct_low=PCT_LOW,
                pct_high=PCT_HIGH,
                min_roi_pixels=MIN_ROI_PIXELS,
                min_pct_pixels=MIN_PCT_PIXELS,
            )
            if sample is None:
                skipped["empty_or_low_roi"] += 1
                continue
            u, v, d = sample
            x, y, z = pixel_to_world(u, v, d, c2w, fx, fy, cx, cy)
            raw_obs[tid][frame_idx] = {
                "frame_name": fname,
                "xyz": (x, y, z),
                "depth_m": d,
            }

        processed_frames += 1
        if processed_frames % 50 == 0:
            logger.info("  processed %d / %d frames", processed_frames, len(work_by_frame))

    # ── Step 4/4: Per-track KF tick + serialise ────────────────────────
    logger.info(
        "Step 4/4: Running Kalman filter (AB3DMOT KF) on %d tracks (max_predict_gap=%d)...",
        len(raw_obs), MAX_PREDICT_GAP,
    )
    tracks_out: dict = {}
    interpolated_count = 0
    for tid in sorted(raw_obs.keys(), key=lambda s: int(s)):
        points = _kf_track_points(tid, raw_obs[tid], sorted_filenames)
        if not points:
            continue
        interpolated_count += sum(1 for p in points if p["interpolated"])
        tracks_out[tid] = {
            "class_name": bbox_sequence["tracks"][tid].get("class_name", "unknown"),
            "points": points,
        }

    params = {
        "tracker": "AB3DMOT-KF",
        "lower_frac": LOWER_FRAC,
        "pct_low": PCT_LOW,
        "pct_high": PCT_HIGH,
        "min_roi_pixels": MIN_ROI_PIXELS,
        "min_pct_pixels": MIN_PCT_PIXELS,
        "max_predict_gap": MAX_PREDICT_GAP,
        "kf_observation_noise": KF_OBSERVATION_NOISE,
        "assumed_fps": ASSUMED_FPS,
    }
    write_trajectories(
        tracks_out,
        frame_count_total=len(sorted_filenames),
        skipped=dict(skipped),
        out_path=out_json,
        params=params,
    )

    artifacts["trajectories"] = str(out_json)

    # Top-down visualisation: camera path + per-track XZ trajectories.
    vis_path = workspace / "trajectories_topdown.png"
    camera_xyz = poses[:, :3, 3]
    render_topdown(camera_xyz, tracks_out, vis_path)
    artifacts["trajectories_vis"] = str(vis_path)

    total_points = sum(len(t["points"]) for t in tracks_out.values())
    logger.info(
        "Stage 09 complete: %d tracks, %d points (%d interpolated), skipped=%s -> %s (vis: %s)",
        len(tracks_out), total_points, interpolated_count, dict(skipped), out_json, vis_path,
    )
    return context
