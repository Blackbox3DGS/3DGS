"""Stage 04: Camera Pose Estimation via COLMAP SfM.

Runs COLMAP's Structure-from-Motion pipeline on the extracted frames
with dynamic-object masks to estimate camera poses, intrinsics, and
a sparse point cloud. After registration, subsamples successfully
registered frames for 3DGS training.
"""

import logging
import shutil
from pathlib import Path

import numpy as np
import open3d as o3d

from common.viz import render_pointcloud_topdown

from .model_parser import (
    parse_cameras_txt,
    parse_images_txt,
    save_intrinsics,
    save_poses,
    save_registered_frames,
)
from .reconstruction import (
    check_colmap_available,
    prepare_masks_for_colmap,
    run_colmap_pipeline,
)

try:
    import torch
    _GPU_AVAILABLE = torch.cuda.is_available()
except ImportError:
    _GPU_AVAILABLE = False

logger = logging.getLogger(__name__)


def _subsample_for_3dgs(images_dir, registered_frames, out_dir, every_n=2):
    """Copy every_n-th registered frame for 3DGS training.

    Only includes frames that COLMAP successfully registered.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir = Path(images_dir)

    count = 0
    for i in range(0, len(registered_frames), every_n):
        src = images_dir / registered_frames[i]
        if src.exists():
            shutil.copy(src, out_dir / src.name)
            count += 1
    return count


def run(context):
    """Stage 04 entry point.

    Reads:
        context["artifacts"]["images_colmap"] — directory of .jpg frames
        context["artifacts"]["segmentation_masks"] — directory of binary .png masks

    Writes:
        context["artifacts"]["poses"] — path to poses.npy (M, 4, 4)
        context["artifacts"]["intrinsics"] — path to intrinsics.json
        context["artifacts"]["sparse_ply"] — path to sparse.ply
        context["artifacts"]["registered_frames"] — path to registered_frames.json
        context["artifacts"]["images_3dgs"] — directory of subsampled frames
        context["artifacts"]["colmap_model_dir"] — path to sparse/0/
    """
    images_dir = Path(context["artifacts"]["images_colmap"])
    masks_dir = Path(context["artifacts"]["segmentation_masks"])
    out_root = Path(context["out_root"])
    workspace = out_root / "04_colmap"
    workspace.mkdir(parents=True, exist_ok=True)

    # 0. Check COLMAP is installed
    check_colmap_available()

    total_frames = len(list(images_dir.glob("*.jpg")))
    logger.info(
        "Stage 04 starting: %d frames from %s, masks from %s",
        total_frames, images_dir, masks_dir,
    )

    # 1. Prepare masks with COLMAP naming convention
    logger.info("Step 1: Preparing masks for COLMAP...")
    colmap_masks = workspace / "masks_colmap"
    prepare_masks_for_colmap(masks_dir, colmap_masks, images_dir)

    # 2. Run COLMAP pipeline (feature extraction, matching, mapping)
    logger.info("Step 2: Running COLMAP SfM pipeline...")
    waymo_intrinsics = context["artifacts"].get("waymo_intrinsics")
    if waymo_intrinsics:
        logger.info(
            "Using Waymo known intrinsics: fx=%.1f fy=%.1f cx=%.1f cy=%.1f",
            waymo_intrinsics["fx"], waymo_intrinsics["fy"],
            waymo_intrinsics["cx"], waymo_intrinsics["cy"],
        )
    model_dir = run_colmap_pipeline(
        images_dir, colmap_masks, workspace, use_gpu=_GPU_AVAILABLE,
        camera_params=waymo_intrinsics,
    )

    # 3. Parse results
    logger.info("Step 3: Parsing COLMAP output...")
    text_dir = workspace / "sparse_text"
    camera_params = parse_cameras_txt(text_dir / "cameras.txt")
    image_poses = parse_images_txt(text_dir / "images.txt")

    # 4. Save poses, intrinsics, registered frames
    sorted_names = sorted(image_poses.keys())
    poses_path = workspace / "poses.npy"
    save_poses(image_poses, sorted_names, poses_path)

    intrinsics_path = workspace / "intrinsics.json"
    save_intrinsics(camera_params, intrinsics_path)

    reg_frames_path = workspace / "registered_frames.json"
    save_registered_frames(sorted_names, total_frames, reg_frames_path)

    # Warn if low registration rate
    rate = len(sorted_names) / total_frames if total_frames > 0 else 0
    if rate < 0.5:
        logger.warning(
            "Low registration rate (%.1f%%). "
            "COLMAP may have struggled with this sequence.",
            rate * 100,
        )

    # 5. Subsample registered frames for 3DGS training
    logger.info("Step 4: Subsampling registered frames for 3DGS...")
    images_3dgs_dir = workspace / "images_3dgs"
    count = _subsample_for_3dgs(images_dir, sorted_names, images_3dgs_dir, every_n=2)
    logger.info("3DGS subsampled: %d frames -> %s", count, images_3dgs_dir)

    # 6. Set artifacts
    sparse_ply = workspace / "sparse.ply"
    context["artifacts"]["poses"] = str(poses_path)
    context["artifacts"]["intrinsics"] = str(intrinsics_path)
    context["artifacts"]["sparse_ply"] = str(sparse_ply)
    context["artifacts"]["registered_frames"] = str(reg_frames_path)
    context["artifacts"]["images_3dgs"] = str(images_3dgs_dir)
    context["artifacts"]["colmap_model_dir"] = str(model_dir)

    # 7. Top-down visualisation: sparse PC + camera path
    sparse_vis = workspace / "sparse_topdown.png"
    if sparse_ply.exists():
        try:
            pcd = o3d.io.read_point_cloud(str(sparse_ply))
            sparse_pts = np.asarray(pcd.points)
            poses_arr = np.load(poses_path)
            cam_xyz = poses_arr[:, :3, 3]
            render_pointcloud_topdown(
                sparse_pts, cam_xyz, sparse_vis,
                title="Stage 04 sparse PC + camera path",
            )
            context["artifacts"]["sparse_topdown"] = str(sparse_vis)
        except Exception as e:  # don't fail the stage on viz issues
            logger.warning("Stage 04 viz failed: %s", e)

    logger.info(
        "Stage 04 complete: %d/%d registered, %d 3DGS frames, sparse PC -> %s",
        len(sorted_names), total_frames, count, sparse_ply,
    )
    return context
