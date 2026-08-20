"""Stage 06: Scale Alignment — relative depth maps → absolute metres.

Two-pass algorithm:
  1. Linear regression between COLMAP sparse PC depths and relative depth values.
  2. Ground plane prior correction so camera height ≈ 1.5 m.
"""

import json
import logging
import traceback
from pathlib import Path

import cv2
import numpy as np

from .align import (
    CAMERA_HEIGHT_PRIOR,
    DEFAULT_CAMERA_HEIGHT,
    ScaleAlignmentError,
    collect_depth_pairs,
    compute_ground_correction,
    fit_ground_plane,
    fit_scale_shift,
    load_sparse_points,
    orient_normal_toward_cameras,
    select_ground_sparse_points,
)

logger = logging.getLogger(__name__)


def run(context):
    """Stage 06 entry point.

    Reads:
        context["artifacts"]["depth_maps"]         — dir of .npy (0-1)
        context["artifacts"]["sparse_ply"]         — sparse.ply
        context["artifacts"]["poses"]              — poses.npy (M,4,4) c2w
        context["artifacts"]["intrinsics"]         — intrinsics.json
        context["artifacts"]["registered_frames"]  — registered_frames.json

    Writes:
        context["artifacts"]["scaled_depth_maps"]  — dir of .npy (metres)
    """
    try:
        return _run_impl(context)
    except Exception:
        logger.error("Stage 06 failed:\n%s", traceback.format_exc())
        raise


def _run_impl(context):
    # ── paths ──────────────────────────────────────────────────────────
    depth_dir = Path(context["artifacts"]["depth_maps"])
    sparse_ply = Path(context["artifacts"]["sparse_ply"])
    poses_path = Path(context["artifacts"]["poses"])
    intrinsics_path = Path(context["artifacts"]["intrinsics"])
    reg_path = Path(context["artifacts"]["registered_frames"])

    out_root = Path(context["out_root"])
    workspace = out_root / "06_scale"
    scaled_dir = workspace / "scaled_depth_maps"
    scaled_dir.mkdir(parents=True, exist_ok=True)

    # ── load inputs ────────────────────────────────────────────────────
    poses = np.load(poses_path)                       # (M, 4, 4)
    with open(intrinsics_path) as f:
        intrinsics = json.load(f)
    with open(reg_path) as f:
        reg_frames = json.load(f)["frames"]
    points_world = load_sparse_points(sparse_ply)

    logger.info(
        "Stage 06 starting: %d sparse pts, %d registered frames, depth from %s",
        len(points_world), len(reg_frames), depth_dir,
    )

    # ── Pass 1: linear regression ──────────────────────────────────────
    rel_depths, colmap_depths = collect_depth_pairs(
        points_world, depth_dir, poses, reg_frames, intrinsics,
    )
    logger.info("Collected %d depth pairs for regression.", len(rel_depths))

    scale, shift = fit_scale_shift(rel_depths, colmap_depths)

    # Depth Anything V2 may output inverted depth (closer = higher value).
    # If scale is negative, invert the depth maps (1 - d) and refit.
    depth_inverted = False
    if scale < 0:
        logger.warning(
            "Negative scale (%.4f) — depth map convention is inverted. "
            "Refitting with (1 - depth)...", scale,
        )
        depth_inverted = True
        rel_depths_inv = 1.0 - rel_depths
        scale, shift = fit_scale_shift(rel_depths_inv, colmap_depths)
        if scale < 0:
            logger.error("Scale still negative after inversion (%.4f). Forcing abs.", scale)
            scale = abs(scale)

    # ── Pass 2: ground plane prior ─────────────────────────────────────
    logger.info("Pass 2: fitting ground plane from COLMAP sparse points...")

    correction = 1.0
    try:
        ground_pts = select_ground_sparse_points(
            points_world, poses, reg_frames, intrinsics,
        )
        normal, d = fit_ground_plane(ground_pts)
        normal, d = orient_normal_toward_cameras(normal, d, poses)
        input_type = context.get("input_type", "video")
        target_height = CAMERA_HEIGHT_PRIOR.get(input_type, DEFAULT_CAMERA_HEIGHT)
        logger.info("  using camera height prior: %.2f m (input_type=%s)", target_height, input_type)
        correction = compute_ground_correction(poses, normal, d, target_height=target_height)
    except ScaleAlignmentError as e:
        logger.warning("Ground plane fit failed — skipping Pass 2: %s", e)

    # ── Apply to all depth maps ────────────────────────────────────────
    all_npys = sorted(depth_dir.glob("*.npy"))
    vis_dir = workspace / "scaled_depth_vis"
    vis_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Scaling %d depth maps (scale=%.4f shift=%.4f k=%.4f inverted=%s) ...",
                len(all_npys), scale, shift, correction, depth_inverted)

    MAX_VIS_DEPTH = 50.0  # metres — colormap ceiling
    all_medians = []

    for idx, npy in enumerate(all_npys):
        rel = np.load(npy)
        if depth_inverted:
            rel = 1.0 - rel
        absolute = correction * (scale * rel + shift)
        absolute = np.clip(absolute, 0, None).astype(np.float32)
        np.save(scaled_dir / npy.name, absolute)

        # visualisation: 0-50 m → 0-255, TURBO colormap
        vis_u8 = (absolute / MAX_VIS_DEPTH * 255).clip(0, 255).astype(np.uint8)
        colored = cv2.applyColorMap(vis_u8, cv2.COLORMAP_TURBO)
        cv2.imwrite(str(vis_dir / (npy.stem + ".png")), colored)

        positive = absolute[absolute > 0]
        if len(positive) > 0:
            all_medians.append(float(np.median(positive)))

        if (idx + 1) % 50 == 0 or (idx + 1) == len(all_npys):
            logger.info("  scaled %d / %d", idx + 1, len(all_npys))

    # ── summary statistics ─────────────────────────────────────────────
    if all_medians:
        med_arr = np.array(all_medians)
        logger.info(
            "Depth statistics (metres): "
            "median=%.2f  min_frame_median=%.2f  max_frame_median=%.2f",
            float(np.median(med_arr)), float(med_arr.min()), float(med_arr.max()),
        )

    # ── artifacts ──────────────────────────────────────────────────────
    context["artifacts"]["scaled_depth_maps"] = str(scaled_dir)
    context["artifacts"]["scaled_depth_vis"] = str(vis_dir)

    logger.info("Stage 06 complete: scaled depth maps -> %s, vis -> %s",
                scaled_dir, vis_dir)
    return context
