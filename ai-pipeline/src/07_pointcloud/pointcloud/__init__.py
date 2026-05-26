"""Stage 07: Dense Point Cloud — backproject depth maps to 3D.

Reads relative depth maps (0-1) from Stage 05, calibrates per-frame metric
scale against COLMAP sparse points, then backprojects to world space and
saves a coloured dense PLY for 3DGS initialisation.
"""

import json
import logging
import traceback
from pathlib import Path

import cv2
import numpy as np
import open3d as o3d

from common.viz import render_pointcloud_topdown

from .backproject import backproject_frame

logger = logging.getLogger(__name__)


def _calibrate_scale(depth_map: np.ndarray, c2w: np.ndarray,
                     sparse_pts: np.ndarray,
                     fx: float, fy: float, cx: float, cy: float) -> float | None:
    """Estimate metric scale factor: metric_depth = relative_depth * scale.

    Projects COLMAP sparse 3D points into the camera frame, samples the
    relative depth map at those pixel positions, and returns the median
    of (colmap_depth / relative_depth) across all visible sparse points.
    Returns None if fewer than 3 valid correspondences are found.
    """
    H, W = depth_map.shape
    w2c = np.linalg.inv(c2w)
    pts_h = np.concatenate([sparse_pts, np.ones((len(sparse_pts), 1))], axis=1)
    pts_cam = (w2c @ pts_h.T).T[:, :3]

    in_front = pts_cam[:, 2] > 0.5
    pts_cam = pts_cam[in_front]
    if len(pts_cam) == 0:
        return None

    u = (fx * pts_cam[:, 0] / pts_cam[:, 2] + cx).astype(int)
    v = (fy * pts_cam[:, 1] / pts_cam[:, 2] + cy).astype(int)
    colmap_z = pts_cam[:, 2]

    in_bounds = (u >= 0) & (u < W) & (v >= 0) & (v < H)
    u, v, colmap_z = u[in_bounds], v[in_bounds], colmap_z[in_bounds]
    if len(u) == 0:
        return None

    rel_d = depth_map[v, u].astype(np.float64)
    valid = (rel_d > 1e-4) & np.isfinite(rel_d)
    if valid.sum() < 3:
        return None

    scales = colmap_z[valid] / rel_d[valid]
    return float(np.median(scales))


def run(context):
    """Stage 07 entry point.

    Reads:
        context["artifacts"]["depth_maps"]         — dir of .npy float32 [0,1]
        context["artifacts"]["sparse_ply"]         — COLMAP sparse.ply for scale calibration
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
    depth_dir = Path(context["artifacts"]["depth_maps"])
    sparse_ply_path = Path(context["artifacts"]["sparse_ply"])
    poses_path = Path(context["artifacts"]["poses"])
    intrinsics_path = Path(context["artifacts"]["intrinsics"])
    reg_path = Path(context["artifacts"]["registered_frames"])
    images_dir = Path(context["artifacts"]["images_colmap"])

    out_root = Path(context["out_root"])
    workspace = out_root / "07_pointcloud"
    workspace.mkdir(parents=True, exist_ok=True)
    ply_path = workspace / "dense.ply"

    poses = np.load(poses_path)  # (M, 4, 4)
    with open(intrinsics_path) as f:
        intrinsics = json.load(f)
    with open(reg_path) as f:
        reg_frames = json.load(f)["frames"]

    fx, fy = intrinsics["fx"], intrinsics["fy"]
    cx, cy = intrinsics["cx"], intrinsics["cy"]

    sparse_pcd = o3d.io.read_point_cloud(str(sparse_ply_path))
    sparse_pts = np.asarray(sparse_pcd.points)
    logger.info("Loaded %d sparse points for scale calibration", len(sparse_pts))

    logger.info(
        "Stage 07 starting: %d registered frames, depth from %s",
        len(reg_frames), depth_dir,
    )

    STEP = 4           # pixel subsampling stride (4 = ~1/16 pixels)
    MIN_DEPTH = 1.0    # metres
    MAX_DEPTH = 80.0   # metres

    all_points = []
    all_colors = []
    total_pts = 0
    no_scale = 0

    for idx, fname in enumerate(reg_frames):
        stem = Path(fname).stem
        npy_path = depth_dir / f"{stem}.npy"
        if not npy_path.exists():
            continue

        depth_rel = np.load(npy_path)  # float32 [0, 1]

        scale = _calibrate_scale(depth_rel, poses[idx], sparse_pts, fx, fy, cx, cy)
        if scale is None or scale <= 0:
            no_scale += 1
            continue
        depth_metric = depth_rel * scale

        img_path = images_dir / fname
        image = None
        if img_path.exists():
            bgr = cv2.imread(str(img_path))
            if bgr is not None:
                image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        pts, colors = backproject_frame(
            depth_metric, poses[idx],
            fx, fy, cx, cy,
            image=image, step=STEP,
            min_depth=MIN_DEPTH, max_depth=MAX_DEPTH,
        )

        if len(pts) > 0:
            all_points.append(pts)
            if colors is not None:
                all_colors.append(colors)
            total_pts += len(pts)

        if (idx + 1) % 50 == 0 or (idx + 1) == len(reg_frames):
            logger.info("  backprojected %d / %d frames  (%d points so far)",
                        idx + 1, len(reg_frames), total_pts)

    if not all_points:
        raise RuntimeError(
            "No points generated — check depth maps and sparse PLY. "
            f"Frames with no scale: {no_scale}/{len(reg_frames)}"
        )

    if no_scale > 0:
        logger.warning("%d / %d frames had no scale calibration and were skipped",
                       no_scale, len(reg_frames))

    logger.info("Merging %d points from %d frames...", total_pts, len(all_points))
    points = np.concatenate(all_points)

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    if all_colors:
        colors_arr = np.concatenate(all_colors)
        pcd.colors = o3d.utility.Vector3dVector(colors_arr.astype(np.float64) / 255.0)

    VOXEL_SIZE = 0.40  # metres
    logger.info("Voxel downsampling: voxel_size=%.3f m  (%d points before)", VOXEL_SIZE, total_pts)
    pcd = pcd.voxel_down_sample(voxel_size=VOXEL_SIZE)
    final_pts = len(pcd.points)
    logger.info("After downsampling: %d points (%.1f%% of original)",
                final_pts, final_pts / total_pts * 100)

    o3d.io.write_point_cloud(str(ply_path), pcd)
    logger.info("Stage 07 complete: %d points -> %s", final_pts, ply_path)

    vis_path = workspace / "dense_topdown.png"
    try:
        pts_np = np.asarray(pcd.points)
        cols_np = np.asarray(pcd.colors) if pcd.has_colors() else None
        render_pointcloud_topdown(
            pts_np, poses[:, :3, 3], vis_path,
            colors=cols_np,
            title=f"Stage 07 dense PC + camera path ({final_pts} pts)",
        )
        context["artifacts"]["dense_topdown"] = str(vis_path)
    except Exception as e:
        logger.warning("Stage 07 viz failed: %s", e)

    context["artifacts"]["dense_pointcloud"] = str(ply_path)
    return context
