"""Stage 07: Dense Point Cloud — backproject metric depth maps to 3D.

Reads absolute-scale depth maps (metres) from Stage 06, original images for
RGB colour, and camera poses/intrinsics from Stage 04 to produce a coloured
dense point cloud saved as PLY.
"""

import json
import logging
import os
import traceback
from pathlib import Path

import cv2
import numpy as np
import open3d as o3d

from common.viz import render_pointcloud_topdown

from .backproject import backproject_frame

logger = logging.getLogger(__name__)


def _load_dynamic_mask(masks_dir: Path, stem: str,
                       depth_hw: tuple[int, int]) -> np.ndarray | None:
    """Load a Stage 03 dynamic mask (white=255=dynamic) for one frame.

    Returns a uint8 (H, W) array matching *depth_hw* (nonzero = dynamic), or
    None when no mask file exists. Resized with nearest-neighbour so the binary
    labels stay crisp.
    """
    for ext in (".png", ".jpg"):
        p = masks_dir / f"{stem}{ext}"
        if p.exists():
            m = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if m is None:
                return None
            H, W = depth_hw
            if m.shape[0] != H or m.shape[1] != W:
                m = cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)
            return m
    return None


def run(context):
    """Stage 07 entry point.

    Reads:
        context["artifacts"]["scaled_depth_maps"]  — dir of .npy (metres)
        context["artifacts"]["poses"]              — poses.npy (M, 4, 4) c2w
        context["artifacts"]["intrinsics"]         — intrinsics.json
        context["artifacts"]["registered_frames"]  — registered_frames.json
        context["artifacts"]["images_colmap"]      — dir of original .jpg

    Writes:
        context["artifacts"]["dense_pointcloud"]   — dense.ply (XYZ + RGB)
    """
    try:
        return _run_impl(context)
    except Exception:
        logger.error("Stage 07 failed:\n%s", traceback.format_exc())
        raise


def _run_impl(context):
    # ── paths ──────────────────────────────────────────────────────────
    depth_dir = Path(context["artifacts"]["scaled_depth_maps"])
    poses_path = Path(context["artifacts"]["poses"])
    intrinsics_path = Path(context["artifacts"]["intrinsics"])
    reg_path = Path(context["artifacts"]["registered_frames"])
    images_dir = Path(context["artifacts"]["images_colmap"])
    masks_artifact = context["artifacts"].get("segmentation_masks")
    masks_dir = Path(masks_artifact) if masks_artifact else None
    conf_artifact = context["artifacts"].get("scaled_conf_maps")
    conf_dir = Path(conf_artifact) if conf_artifact else None

    out_root = Path(context["out_root"])
    workspace = out_root / "07_pointcloud"
    workspace.mkdir(parents=True, exist_ok=True)
    ply_path = workspace / "dense.ply"

    # ── load metadata ──────────────────────────────────────────────────
    poses = np.load(poses_path)  # (M, 4, 4)
    with open(intrinsics_path) as f:
        intrinsics = json.load(f)
    with open(reg_path) as f:
        reg_frames = json.load(f)["frames"]

    fx, fy = intrinsics["fx"], intrinsics["fy"]
    cx, cy = intrinsics["cx"], intrinsics["cy"]

    logger.info(
        "Stage 07 starting: %d registered frames, depth from %s",
        len(reg_frames), depth_dir,
    )

    # ── backproject each frame ─────────────────────────────────────────
    STEP = 2          # pixel subsampling stride
    MIN_DEPTH = 0.5   # metres
    # Env-tunable: cut far/low-confidence points that fan out (LingBot-style).
    MAX_DEPTH = float(os.environ.get("PC_MAX_DEPTH", "150.0"))     # metres
    CONF_THRESHOLD = float(os.environ.get("PC_CONF_THRESHOLD", "1.5"))  # LingBot demo default

    all_points = []
    all_colors = []
    total_pts = 0
    masked_frames = 0
    conf_frames = 0

    for idx, fname in enumerate(reg_frames):
        stem = Path(fname).stem
        npy_path = depth_dir / f"{stem}.npy"
        if not npy_path.exists():
            continue

        depth_map = np.load(npy_path)

        # Load original image for RGB
        img_path = images_dir / fname
        image = None
        if img_path.exists():
            bgr = cv2.imread(str(img_path))
            if bgr is not None:
                image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        # Load Stage 03 dynamic mask (white=dynamic) so moving vehicles don't
        # seed ghost points in the dense cloud. Resize to depth resolution.
        mask = None
        if masks_dir is not None:
            mask = _load_dynamic_mask(masks_dir, stem, depth_map.shape)
            if mask is not None:
                masked_frames += 1

        # Load LingBot confidence map (if Stage 04g produced it) to drop
        # unreliable far/sky points — the main cause of the fanned-out cloud.
        conf = None
        if conf_dir is not None:
            cpath = conf_dir / f"{stem}.npy"
            if cpath.exists():
                conf = np.load(cpath)
                if conf.shape != depth_map.shape:
                    conf = cv2.resize(conf, (depth_map.shape[1], depth_map.shape[0]),
                                      interpolation=cv2.INTER_LINEAR)
                conf_frames += 1

        pts, colors = backproject_frame(
            depth_map, poses[idx],
            fx, fy, cx, cy,
            image=image, step=STEP,
            min_depth=MIN_DEPTH, max_depth=MAX_DEPTH,
            mask=mask,
            conf=conf, conf_threshold=CONF_THRESHOLD,
        )

        if len(pts) > 0:
            all_points.append(pts)
            if colors is not None:
                all_colors.append(colors)
            total_pts += len(pts)

        if (idx + 1) % 50 == 0 or (idx + 1) == len(reg_frames):
            logger.info("  backprojected %d / %d frames  (%d points so far)",
                        idx + 1, len(reg_frames), total_pts)

    if masks_dir is not None:
        logger.info("Dynamic masks applied to %d/%d frames (from %s)",
                    masked_frames, len(reg_frames), masks_dir)
    else:
        logger.info("No segmentation_masks artifact — dense PC keeps dynamic objects.")
    if conf_dir is not None:
        logger.info("Confidence filter (conf>%.2f) applied to %d/%d frames (max_depth=%.0fm)",
                    CONF_THRESHOLD, conf_frames, len(reg_frames), MAX_DEPTH)
    else:
        logger.info("No scaled_conf_maps artifact — dense PC keeps low-confidence points.")

    if not all_points:
        raise RuntimeError("No points generated — check depth maps and poses.")

    # ── merge and save ─────────────────────────────────────────────────
    logger.info("Merging %d points from %d frames...", total_pts, len(all_points))
    points = np.concatenate(all_points)

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    if all_colors:
        colors_arr = np.concatenate(all_colors)
        pcd.colors = o3d.utility.Vector3dVector(colors_arr.astype(np.float64) / 255.0)

    # ── voxel downsampling ─────────────────────────────────────────────
    VOXEL_SIZE = 0.1  # metres — spatially uniform downsampling
    logger.info("Voxel downsampling: voxel_size=%.3f m  (%d points before)", VOXEL_SIZE, total_pts)
    pcd = pcd.voxel_down_sample(voxel_size=VOXEL_SIZE)
    final_pts = len(pcd.points)
    logger.info("After downsampling: %d points (%.1f%% of original)",
                final_pts, final_pts / total_pts * 100)

    o3d.io.write_point_cloud(str(ply_path), pcd)
    logger.info("Stage 07 complete: %d points -> %s", final_pts, ply_path)

    # ── visualisation: top-down dense PC + camera path ─────────────────
    vis_path = workspace / "dense_topdown.png"
    try:
        pts_np = np.asarray(pcd.points)
        cols_np = np.asarray(pcd.colors) if pcd.has_colors() else None
        render_pointcloud_topdown(
            pts_np, poses[:, :3, 3], vis_path,
            colors=cols_np,
            title="Stage 07 dense PC + camera path",
        )
        context["artifacts"]["dense_topdown"] = str(vis_path)
    except Exception as e:
        logger.warning("Stage 07 viz failed: %s", e)

    # ── artifacts ──────────────────────────────────────────────────────
    context["artifacts"]["dense_pointcloud"] = str(ply_path)
    return context
