"""Stage 08: Point Cloud Filtering — statistical outlier removal.

Removes noisy points from the dense point cloud using Open3D's
statistical outlier removal before 3DGS training.
"""

import logging
import traceback
from pathlib import Path

import numpy as np
import open3d as o3d

from common.viz import render_pointcloud_topdown

logger = logging.getLogger(__name__)


def run(context):
    """Stage 08 entry point.

    Reads:
        context["artifacts"]["dense_pointcloud"]     — dense.ply (XYZ + RGB)

    Writes:
        context["artifacts"]["filtered_pointcloud"]  — filtered.ply
    """
    try:
        return _run_impl(context)
    except Exception:
        logger.error("Stage 08 failed:\n%s", traceback.format_exc())
        raise


def _run_impl(context):
    dense_path = Path(context["artifacts"]["dense_pointcloud"])

    out_root = Path(context["out_root"])
    workspace = out_root / "08_filtering"
    workspace.mkdir(parents=True, exist_ok=True)
    filtered_path = workspace / "filtered.ply"

    # ── load ───────────────────────────────────────────────────────────
    pcd = o3d.io.read_point_cloud(str(dense_path))
    n_before = len(pcd.points)
    logger.info("Stage 08 starting: %d points from %s", n_before, dense_path)

    # ── statistical outlier removal ────────────────────────────────────
    NB_NEIGHBORS = 20
    STD_RATIO = 2.0

    logger.info("Statistical outlier removal: nb_neighbors=%d, std_ratio=%.1f",
                NB_NEIGHBORS, STD_RATIO)
    pcd_filtered, idx = pcd.remove_statistical_outlier(
        nb_neighbors=NB_NEIGHBORS,
        std_ratio=STD_RATIO,
    )

    n_after = len(pcd_filtered.points)
    n_removed = n_before - n_after
    logger.info("Removed %d outliers (%.1f%%), %d points remaining",
                n_removed, n_removed / max(n_before, 1) * 100, n_after)

    # ── save ───────────────────────────────────────────────────────────
    o3d.io.write_point_cloud(str(filtered_path), pcd_filtered)
    logger.info("Stage 08 complete: %d points -> %s", n_after, filtered_path)

    context["artifacts"]["filtered_pointcloud"] = str(filtered_path)

    # ── visualisation: top-down filtered PC (+ camera path if available) ──
    vis_path = workspace / "filtered_topdown.png"
    try:
        pts_np = np.asarray(pcd_filtered.points)
        cols_np = np.asarray(pcd_filtered.colors) if pcd_filtered.has_colors() else None
        cam_xyz = None
        poses_artifact = context["artifacts"].get("poses")
        if poses_artifact and Path(poses_artifact).exists():
            cam_xyz = np.load(poses_artifact)[:, :3, 3]
        render_pointcloud_topdown(
            pts_np, cam_xyz, vis_path,
            colors=cols_np,
            title="Stage 08 filtered PC + camera path",
        )
        context["artifacts"]["filtered_topdown"] = str(vis_path)
    except Exception as e:
        logger.warning("Stage 08 viz failed: %s", e)

    return context
