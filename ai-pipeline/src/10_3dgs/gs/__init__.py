"""Stage 10: 3D Gaussian Splatting Training — background reconstruction.

Trains a 3DGS model using Inria gaussian-splatting with mask-based loss
exclusion to suppress floaters on dynamic objects (vehicles, pedestrians).
"""

import logging
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np
import open3d as o3d

from common.viz import render_pointcloud_topdown

from .data_prep import prepare_scene_dir

logger = logging.getLogger(__name__)


def run(context):
    """Stage 10 entry point.

    Reads:
        context["artifacts"]["images_3dgs"]          — subsampled registered frames
        context["artifacts"]["combined_masks"]        — combined (dynamic | sky) binary masks
        context["artifacts"]["colmap_model_dir"]      — sparse/0/ (cameras.bin, images.bin)
        context["artifacts"]["sparse_ply"]            — COLMAP sparse.ply (initial PC)

    Writes:
        context["artifacts"]["output_ply"]            — trained 3DGS point_cloud.ply
        context["artifacts"]["gs_model_dir"]          — model output directory
    """
    try:
        return _run_impl(context)
    except Exception:
        logger.error("Stage 10 failed:\n%s", traceback.format_exc())
        raise


def _run_impl(context):
    images_dir = Path(context["artifacts"]["images_3dgs"])
    masks_dir = Path(context["artifacts"]["combined_masks"])
    colmap_model_dir = Path(context["artifacts"]["colmap_model_dir"])
    # Prefer dense pointcloud from Stage 07; fall back to sparse PLY
    init_ply_key = "dense_pointcloud" if "dense_pointcloud" in context["artifacts"] else "sparse_ply"
    sparse_ply = Path(context["artifacts"][init_ply_key])
    logger.info("Stage 10: using %s for 3DGS initialisation (%s)", init_ply_key, sparse_ply)

    out_root = Path(context["out_root"])
    workspace = out_root / "10_3dgs"
    workspace.mkdir(parents=True, exist_ok=True)

    scene_dir = workspace / "scene"
    model_dir = workspace / "model"

    # ── 1. Prepare COLMAP-compatible directory structure ───────────────
    logger.info("Stage 10: Preparing scene directory...")
    prepare_scene_dir(
        scene_dir=scene_dir,
        images_dir=images_dir,
        masks_dir=masks_dir,
        colmap_model_dir=colmap_model_dir,
        sparse_ply=sparse_ply,
    )

    model_dir.mkdir(parents=True, exist_ok=True)

    # ── 2. Run 3DGS training ──────────────────────────────────────────
    ITERATIONS = 50_000
    SAVE_ITERATIONS = [7_000, 30_000, 50_000]

    train_script = Path(__file__).parent / "train_masked.py"

    cmd = [
        sys.executable, str(train_script),
        "--source_path", str(scene_dir),
        "--model_path", str(model_dir),
        "--mask_path", str(scene_dir / "masks"),
        "--iterations", str(ITERATIONS),
        "--save_iterations", *[str(i) for i in SAVE_ITERATIONS],
        "--densify_until_iter", "40000",
        "--densification_interval", "50",
        "--data_device", "cuda",
    ]

    logger.info("Stage 10: Starting 3DGS training (%d iterations)...", ITERATIONS)
    logger.info("  cmd: %s", " ".join(cmd))

    result = subprocess.run(cmd, check=True)

    # ── 3. Register output artifacts ──────────────────────────────────
    output_ply = model_dir / "point_cloud" / f"iteration_{ITERATIONS}" / "point_cloud.ply"

    if not output_ply.exists():
        raise FileNotFoundError(
            f"Expected output not found: {output_ply}. "
            f"Check training logs for errors."
        )

    n_gaussians = _count_ply_vertices(output_ply)
    logger.info("Stage 10 complete: %s (%d Gaussians)", output_ply, n_gaussians)

    context["artifacts"]["output_ply"] = str(output_ply)
    context["artifacts"]["gs_model_dir"] = str(model_dir)

    # ── visualisation: top-down of trained Gaussian centres ────────────
    vis_path = workspace / "output_topdown.png"
    try:
        pcd = o3d.io.read_point_cloud(str(output_ply))
        pts_np = np.asarray(pcd.points)
        cols_np = np.asarray(pcd.colors) if pcd.has_colors() else None
        cam_xyz = None
        poses_artifact = context["artifacts"].get("poses")
        if poses_artifact and Path(poses_artifact).exists():
            cam_xyz = np.load(poses_artifact)[:, :3, 3]
        render_pointcloud_topdown(
            pts_np, cam_xyz, vis_path,
            colors=cols_np,
            title=f"Stage 10 trained Gaussians ({n_gaussians} pts)",
        )
        context["artifacts"]["output_topdown"] = str(vis_path)
    except Exception as e:
        logger.warning("Stage 10 viz failed: %s", e)

    return context


def _count_ply_vertices(ply_path: Path) -> int:
    """Read vertex count from PLY header."""
    with open(ply_path, "rb") as f:
        for line in f:
            line = line.decode("ascii", errors="ignore").strip()
            if line.startswith("element vertex"):
                return int(line.split()[-1])
            if line == "end_header":
                break
    return -1
