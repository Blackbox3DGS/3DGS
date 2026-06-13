"""Stage 04g: LingBot-MAP feed-forward 3D reconstruction.

Drop-in replacement for the chain Stage 04 (COLMAP) → 05 (Depth Anything) →
06 (scale alignment). Produces the same artifact keys those three stages would,
so Stage 07 (dense PC) and Stage 10 (3DGS training) work unchanged.

LingBot-MAP processes images at a fixed resolution (default 518 wide, height
adjusted to a multiple of 14). Both depth maps and intrinsics live in that
processed frame. Before handing off to downstream stages we resize depth back
to the **original** image resolution and rescale the intrinsics to match — that
way `images_colmap` (original frames) and the depth grids stay coregistered,
and Stage 10 (which copies original frames into `images_3dgs`) needs no change.

Reads:
    context["artifacts"]["images_colmap"]        — directory of original frames
    context["artifacts"]["segmentation_masks"]    — Stage 03 binary masks (used by Stage 10)
    context.get("input_type")                     — "video"/"waymo" (informational)
    env LINGBOT_MODEL_PATH                        — HF repo id or local path to checkpoint

Writes the same artifact keys Stage 04/05/06 would set, all rooted at
out_root/04g_lingbot/:
    poses, intrinsics, sparse_ply, registered_frames, images_3dgs,
    colmap_model_dir, depth_maps, scaled_depth_maps
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import traceback
from pathlib import Path

import cv2
import numpy as np

from .colmap_writer import (
    write_cameras_txt,
    write_images_txt,
    write_points3D_txt,
    write_sparse_ply,
)
from .ground_align import (
    apply_to_extrinsics,
    apply_to_points,
    compute_align_transform,
)
from .inference import run_inference

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Sparse PC sampling for points3D.txt / sparse.ply
# ----------------------------------------------------------------------------

DEFAULT_CONF_THRESHOLD = 1.5  # demo.py default
DEFAULT_DOWNSAMPLE = 10       # demo.py default
MAX_INIT_POINTS = 500_000     # cap so the 3DGS scene loader stays responsive


def _build_sparse_pointcloud(world_points: np.ndarray, points_conf: np.ndarray,
                             images_proc: np.ndarray,
                             conf_threshold: float = DEFAULT_CONF_THRESHOLD,
                             downsample: int = DEFAULT_DOWNSAMPLE,
                             max_points: int = MAX_INIT_POINTS):
    """Threshold + spatially subsample world_points to a sparse init cloud.

    Args:
        world_points: (S, H, W, 3)
        points_conf:  (S, H, W)
        images_proc:  (S, 3, H, W) in [0, 1] for per-point colours
    Returns:
        xyz (N, 3) float32, rgb (N, 3) uint8
    """
    if downsample > 1:
        wp = world_points[:, ::downsample, ::downsample, :]
        pc = points_conf[:, ::downsample, ::downsample]
        imgs = images_proc[:, :, ::downsample, ::downsample]
    else:
        wp = world_points
        pc = points_conf
        imgs = images_proc

    mask = pc > conf_threshold
    xyz = wp[mask]
    # Colours: (S, 3, H', W') → (S, H', W', 3)
    rgb_arr = np.transpose(imgs, (0, 2, 3, 1))[mask]
    rgb = np.clip(rgb_arr * 255.0, 0, 255).astype(np.uint8)

    n = len(xyz)
    if n > max_points:
        idx = np.random.default_rng(0).choice(n, size=max_points, replace=False)
        xyz = xyz[idx]
        rgb = rgb[idx]
        logger.info("Sparse PC capped: %d → %d points", n, max_points)
    return xyz.astype(np.float32), rgb


def _resize_depth_to_original(depth_proc: np.ndarray, orig_hw: tuple[int, int]) -> np.ndarray:
    """Bilinear resize depth (H_p, W_p) → (H_orig, W_orig)."""
    H, W = orig_hw
    return cv2.resize(depth_proc, (W, H), interpolation=cv2.INTER_LINEAR)


def _rescale_intrinsic(intrinsic_proc: np.ndarray,
                       proc_hw: tuple[int, int],
                       orig_hw: tuple[int, int]) -> np.ndarray:
    """Scale intrinsic from (H_p, W_p) frame to (H_orig, W_orig) frame.

    Note: LingBot uses "crop" mode (resize so width=518 then center-crop height),
    not a pure resize. For typical dashcam 16:9 aspect ratios the crop is small
    enough that a simple proportional rescale is a good first approximation;
    rigorous handling would invert the crop translation, but in practice the
    cropped strip is a few rows of road/sky that COLMAP / 3DGS handle either way.
    """
    H_p, W_p = proc_hw
    H_o, W_o = orig_hw
    sx, sy = W_o / W_p, H_o / H_p
    K = intrinsic_proc.copy().astype(np.float32)
    K[0, 0] *= sx       # fx
    K[1, 1] *= sy       # fy
    K[0, 2] *= sx       # cx
    K[1, 2] *= sy       # cy
    return K


def _zero_conf_on_dynamic(points_conf: np.ndarray, masks_dir: Path | None,
                          frame_names: list[str],
                          proc_hw: tuple[int, int]) -> int:
    """Zero out confidence on Stage 03 dynamic pixels (in place).

    LingBot world points live at the processed (H_p, W_p) resolution while the
    masks are at original resolution, so each mask is resized down with
    nearest-neighbour. Setting confidence to 0 makes `_build_sparse_pointcloud`
    drop those pixels (conf <= threshold), keeping moving-vehicle ghosts out of
    the sparse init. Returns the number of pixels zeroed.
    """
    if masks_dir is None or not masks_dir.exists():
        return 0
    H_p, W_p = proc_hw
    zeroed = 0
    for i, name in enumerate(frame_names):
        stem = Path(name).stem
        mask_path = None
        for ext in (".png", ".jpg"):
            cand = masks_dir / f"{stem}{ext}"
            if cand.exists():
                mask_path = cand
                break
        if mask_path is None:
            continue
        m = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if m is None:
            continue
        if m.shape[0] != H_p or m.shape[1] != W_p:
            m = cv2.resize(m, (W_p, H_p), interpolation=cv2.INTER_NEAREST)
        dyn = m > 0
        points_conf[i][dyn] = 0.0
        zeroed += int(dyn.sum())
    return zeroed


def _subsample_for_3dgs(images_dir: Path, registered_frames: list[str],
                        out_dir: Path, every_n: int = 2) -> int:
    """Mirror Stage 04's `_subsample_for_3dgs`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for i in range(0, len(registered_frames), every_n):
        src = images_dir / registered_frames[i]
        if src.exists():
            shutil.copy(src, out_dir / src.name)
            count += 1
    return count


# ----------------------------------------------------------------------------
# Stage entry
# ----------------------------------------------------------------------------

def run(context: dict) -> dict:
    """Stage 04g entry point."""
    try:
        return _run_impl(context)
    except Exception:
        logger.error("Stage 04g failed:\n%s", traceback.format_exc())
        raise


def _run_impl(context: dict) -> dict:
    images_dir = Path(context["artifacts"]["images_colmap"])
    out_root = Path(context["out_root"])
    workspace = out_root / "04g_lingbot"
    workspace.mkdir(parents=True, exist_ok=True)

    image_paths = sorted(images_dir.glob("*.jpg"))
    if not image_paths:
        raise RuntimeError(f"No .jpg frames found in {images_dir}")
    total = len(image_paths)
    logger.info("Stage 04g starting: %d frames from %s", total, images_dir)

    # Original image resolution (read one to learn H, W).
    sample = cv2.imread(str(image_paths[0]))
    if sample is None:
        raise RuntimeError(f"Failed to read sample image: {image_paths[0]}")
    H_orig, W_orig = sample.shape[:2]

    # ── Run LingBot-MAP ──────────────────────────────────────────────────
    model_path = os.environ.get("LINGBOT_MODEL_PATH")
    if not model_path:
        raise RuntimeError(
            "LINGBOT_MODEL_PATH env var not set. "
            "Point it at a HuggingFace repo id or a local checkpoint directory."
        )

    pred = run_inference(image_paths, model_path)
    H_p, W_p = pred["processed_hw"]
    extrinsics_c2w = pred["extrinsic_c2w"]        # (S, 3, 4)
    intrinsics_proc = pred["intrinsic"]           # (S, 3, 3)
    depth_proc = pred["depth"]                    # (S, H_p, W_p) or None
    wp = pred["world_points"]
    wp_conf = pred["world_points_conf"]
    imgs_proc = pred["images_proc"]
    S = extrinsics_c2w.shape[0]
    logger.info("LingBot output: S=%d processed @ %d×%d, will resize back to %d×%d",
                S, H_p, W_p, H_orig, W_orig)

    if depth_proc is None:
        raise RuntimeError("LingBot did not return depth maps — model output incomplete.")
    if wp is None or wp_conf is None:
        raise RuntimeError("LingBot did not return world_points — model output incomplete.")

    # ── Frame name list (LingBot consumes them in sorted order) ──────────
    frame_names = [p.name for p in image_paths]
    if S != total:
        raise RuntimeError(
            f"Frame count mismatch: {total} input vs {S} LingBot outputs."
        )

    # ── Build 4x4 c2w from 3x4 ───────────────────────────────────────────
    poses_4x4 = np.zeros((S, 4, 4), dtype=np.float64)
    poses_4x4[:, :3, :4] = extrinsics_c2w
    poses_4x4[:, 3, 3] = 1.0

    # ── Phase D-pre: gravity-align the world frame ───────────────────────
    # Stage 10 (3DGS) and Stage 12 (viewer w/ car meshes) need ground at z=0.
    # LingBot's predicted world is roughly aligned but not exact; RANSAC-fit
    # the dominant plane and rotate so its normal becomes +z.
    align_info = None
    try:
        input_type = context.get("input_type", "video")
        T_align, align_info = compute_align_transform(
            wp, wp_conf, poses_4x4, input_type=input_type,
        )
        logger.info("Ground alignment: %s", align_info)
        np.save(workspace / "align_transform.npy", T_align)

        # Apply to everything that lives in world frame.
        poses_4x4 = apply_to_extrinsics(T_align, poses_4x4)
        wp = apply_to_points(T_align, wp)
        # Depth maps live in camera frame; the metric scale below also scales them.
    except Exception as e:  # pragma: no cover  — never let alignment crash the stage
        logger.warning("Ground alignment failed (%s); using raw LingBot world.", e)
        T_align = np.eye(4)

    # ── Metric rescale (Gap 6): LingBot world can be non-metric. Apply the
    # camera-height-prior scale uniformly about the ground (z=0) to camera
    # centres, world points, and depth so downstream metric thresholds
    # (Stage 07 MIN/MAX_DEPTH, VOXEL_SIZE; Stage 09 velocities) are correct. ─
    metric_scale = float(align_info.get("scale", 1.0)) if align_info else 1.0
    if abs(metric_scale - 1.0) > 1e-6:
        logger.info("Applying metric scale %.4f to poses/world_points/depth", metric_scale)
        poses_4x4[:, :3, 3] *= metric_scale   # camera centres (rotation block intact)
        wp = wp * metric_scale                # world points (ground at z=0 stays fixed)
        depth_proc = depth_proc * metric_scale  # camera-frame depth scales the same

    poses_4x4 = poses_4x4.astype(np.float32)
    poses_path = workspace / "poses.npy"
    np.save(poses_path, poses_4x4)
    logger.info("Saved poses: %s -> %s", poses_4x4.shape, poses_path)

    # ── intrinsics.json — single shared intrinsic (LingBot is per-frame,
    # but our pipeline expects one; take the median fx/fy/cx/cy across frames). ─
    K_orig = np.stack([_rescale_intrinsic(intrinsics_proc[i], (H_p, W_p), (H_orig, W_orig))
                       for i in range(S)], axis=0)  # (S, 3, 3)
    K_med = np.median(K_orig, axis=0)
    intrinsics_dict = {
        "model": "PINHOLE",
        "width": int(W_orig),
        "height": int(H_orig),
        "fx": float(K_med[0, 0]),
        "fy": float(K_med[1, 1]),
        "cx": float(K_med[0, 2]),
        "cy": float(K_med[1, 2]),
    }
    intrinsics_path = workspace / "intrinsics.json"
    with open(intrinsics_path, "w") as f:
        json.dump(intrinsics_dict, f, indent=2)
    logger.info("Intrinsics (orig %dx%d): fx=%.1f fy=%.1f cx=%.1f cy=%.1f",
                W_orig, H_orig, intrinsics_dict["fx"], intrinsics_dict["fy"],
                intrinsics_dict["cx"], intrinsics_dict["cy"])

    # ── registered_frames.json (all frames "registered") ────────────────
    reg_path = workspace / "registered_frames.json"
    with open(reg_path, "w") as f:
        json.dump({
            "total_input": total,
            "registered": total,
            "rate": 1.0,
            "frames": frame_names,
        }, f, indent=2)

    # ── Depth maps: save processed-resolution + resized-to-original ──────
    depth_dir = workspace / "depth_maps"
    scaled_dir = workspace / "scaled_depth_maps"
    vis_dir = workspace / "scaled_depth_vis"
    for d in (depth_dir, scaled_dir, vis_dir):
        d.mkdir(parents=True, exist_ok=True)

    MAX_VIS_DEPTH = 50.0
    for i, name in enumerate(frame_names):
        stem = Path(name).stem
        d_proc = depth_proc[i].astype(np.float32)
        d_orig = _resize_depth_to_original(d_proc, (H_orig, W_orig)).astype(np.float32)
        np.save(depth_dir / f"{stem}.npy", d_proc)
        np.save(scaled_dir / f"{stem}.npy", d_orig)

        # Top-of-funnel vis (turbo colourmap, 0-50 m).
        vis_u8 = np.clip(d_orig / MAX_VIS_DEPTH * 255, 0, 255).astype(np.uint8)
        cv2.imwrite(str(vis_dir / f"{stem}.png"),
                    cv2.applyColorMap(vis_u8, cv2.COLORMAP_TURBO))

    logger.info("Saved %d depth maps (proc %dx%d) and %d scaled (%dx%d).",
                S, W_p, H_p, S, W_orig, H_orig)

    # ── Sparse PC for 3DGS init + Stage 07 viz reference ────────────────
    # Drop dynamic-object pixels (Stage 03 masks) so moving vehicles don't seed
    # ghost points in the sparse init. Stage 07 masks the dense PC the same way.
    masks_artifact = context["artifacts"].get("segmentation_masks")
    masks_dir = Path(masks_artifact) if masks_artifact else None
    n_zeroed = _zero_conf_on_dynamic(wp_conf, masks_dir, frame_names, (H_p, W_p))
    logger.info("Dynamic-masked sparse init: zeroed %d pixels (masks=%s)",
                n_zeroed, masks_dir)
    xyz, rgb = _build_sparse_pointcloud(wp, wp_conf, imgs_proc)
    sparse_ply_path = workspace / "sparse.ply"
    write_sparse_ply(sparse_ply_path, xyz, rgb)

    # ── COLMAP-format sparse model dir ───────────────────────────────────
    sparse_model_dir = workspace / "sparse" / "0"
    write_cameras_txt(
        sparse_model_dir / "cameras.txt",
        width=W_orig, height=H_orig,
        fx=intrinsics_dict["fx"], fy=intrinsics_dict["fy"],
        cx=intrinsics_dict["cx"], cy=intrinsics_dict["cy"],
    )
    write_images_txt(sparse_model_dir / "images.txt", frame_names, poses_4x4)
    write_points3D_txt(sparse_model_dir / "points3D.txt", xyz, rgb)

    # ── 3DGS subsample (mirrors Stage 04) ────────────────────────────────
    images_3dgs_dir = workspace / "images_3dgs"
    count = _subsample_for_3dgs(images_dir, frame_names, images_3dgs_dir, every_n=2)
    logger.info("Subsampled %d frames into %s", count, images_3dgs_dir)

    # ── Register artifacts (same keys Stage 04/05/06 would emit) ─────────
    context["artifacts"].update({
        "poses":               str(poses_path),
        "intrinsics":          str(intrinsics_path),
        "sparse_ply":          str(sparse_ply_path),
        "registered_frames":   str(reg_path),
        "images_3dgs":         str(images_3dgs_dir),
        "colmap_model_dir":    str(sparse_model_dir),
        "depth_maps":          str(depth_dir),
        "scaled_depth_maps":   str(scaled_dir),
        "scaled_depth_vis":    str(vis_dir),
    })

    logger.info("Stage 04g complete: poses + %d-pt sparse init + %d depth maps", len(xyz), S)
    return context
