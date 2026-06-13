"""Gravity-align the LingBot world frame.

LingBot-MAP's predicted world is the first camera's frame and is only
approximately gravity-aligned (training data drives it toward that prior).
For Stage 12's car-mesh viewer the world MUST be gravity-aligned, with the
ground at z=0, so 3D meshes can sit flat on the road.

We RANSAC-fit a plane to the high-confidence world points, orient its normal
toward the cameras, and compose a 4x4 transform `T_align` that:
    1. rotates the dominant ground plane to be perpendicular to +z (normal → +z)
    2. translates so cameras live at a chosen height above z=0

Applied to every spatial output of the stage:
    extrinsics_c2w : (S, 4, 4) → T_align @ extrinsics_c2w
    world_points   : (N, 3)    → (R @ p + t)  (where R, t are blocks of T_align)
    sparse PC      : same as world_points
    depth maps     : unchanged (camera-frame quantity)
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

# Reuse the well-tested Stage 06 plane-fitting primitives.
# ground_align.py lives at src/04g_lingbot/lingbot/, so parents[2] == src/.
import sys
_SRC_ROOT = str(Path(__file__).resolve().parents[2])
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)
# Importable as "06_scale.scale.align" because 04_colmap.colmap_step works
# with the digit-prefixed package name pattern already used by run_pipeline.
_align = __import__("06_scale.scale.align", fromlist=["fit_ground_plane",
                                                       "orient_normal_toward_cameras",
                                                       "ScaleAlignmentError"])
fit_ground_plane = _align.fit_ground_plane
orient_normal_toward_cameras = _align.orient_normal_toward_cameras
ScaleAlignmentError = _align.ScaleAlignmentError

logger = logging.getLogger(__name__)


DEFAULT_CAMERA_HEIGHT_PRIOR = {
    "video": 1.5,
    "waymo": 2.05,
}
FALLBACK_CAMERA_HEIGHT = 1.5
GROUND_CONF_PERCENTILE = 75   # use top quartile of world_points_conf
MAX_GROUND_POINTS = 100_000   # cap before RANSAC


def _rotation_to_align_vec(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Return R (3x3) such that R @ src ≈ dst, both unit-norm.

    Uses Rodrigues' rotation formula about the axis = src × dst.
    Handles the antiparallel edge case (180° rotation about an arbitrary
    perpendicular axis) explicitly.
    """
    a = src / max(np.linalg.norm(src), 1e-12)
    b = dst / max(np.linalg.norm(dst), 1e-12)
    v = np.cross(a, b)
    c = float(a @ b)
    s = float(np.linalg.norm(v))

    if s < 1e-9:
        # Parallel or antiparallel.
        if c > 0:
            return np.eye(3)
        # Antiparallel — pick any perpendicular axis.
        axis = np.array([1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        axis = axis - (axis @ a) * a
        axis /= np.linalg.norm(axis)
        K = np.array([[0, -axis[2], axis[1]],
                      [axis[2], 0, -axis[0]],
                      [-axis[1], axis[0], 0]])
        return np.eye(3) + 2 * (K @ K)  # 180° rotation

    K = np.array([[0, -v[2], v[1]],
                  [v[2], 0, -v[0]],
                  [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * ((1 - c) / (s * s))


def compute_align_transform(
    world_points: np.ndarray,
    points_conf: np.ndarray,
    extrinsics_c2w_4x4: np.ndarray,
    *,
    input_type: str = "video",
    up_axis: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> tuple[np.ndarray, dict]:
    """Compute the 4x4 world transform that gravity-aligns the scene.

    Args:
        world_points:        (S, H, W, 3) per-pixel world points from LingBot
        points_conf:         (S, H, W)    confidence map
        extrinsics_c2w_4x4:  (S, 4, 4)    camera-to-world for each frame
        input_type:          chooses camera-height prior
        up_axis:             desired "up" direction in the *new* world frame.
                             Default (0,0,1) — gsplat / Blender convention.

    Returns:
        T_align : (4, 4)   transform applied as: p_new = T_align @ p_old
        info    : dict with diagnostics (inlier count, measured height, etc.)
    """
    # 1. Collect high-confidence points as ground candidates.
    flat_pts = world_points.reshape(-1, 3)
    flat_conf = points_conf.reshape(-1)
    if flat_conf.size == 0:
        raise ScaleAlignmentError("Empty world_points / points_conf.")

    conf_thresh = np.percentile(flat_conf, GROUND_CONF_PERCENTILE)
    mask = flat_conf > conf_thresh
    candidates = flat_pts[mask]
    if len(candidates) < 100:
        raise ScaleAlignmentError(
            f"Too few high-confidence points for ground fit "
            f"({len(candidates)}, threshold={conf_thresh:.3f})"
        )

    if len(candidates) > MAX_GROUND_POINTS:
        rng = np.random.default_rng(0)
        idx = rng.choice(len(candidates), size=MAX_GROUND_POINTS, replace=False)
        candidates = candidates[idx]
    logger.info("Ground RANSAC candidates: %d points (conf > %.3f)",
                len(candidates), conf_thresh)

    # 2. RANSAC fit dominant plane (≈ ground in driving footage).
    normal, d = fit_ground_plane(candidates)

    # 3. Orient normal upward (away from ground, toward cameras).
    poses_3x4 = extrinsics_c2w_4x4[:, :3, :4]
    normal, d = orient_normal_toward_cameras(normal, d, poses_3x4)

    # 4. Build rotation taking `normal` → `up_axis`.
    up = np.array(up_axis, dtype=np.float64)
    R = _rotation_to_align_vec(normal, up)

    # 5. Compute translation so cameras live at a sensible height above z=0.
    # After rotation, the plane equation becomes (R @ normal) · p + d = 0
    #   = up · p + d = 0     →     p_up = -d  (in *rotated* coords).
    # We want the *ground* (where the plane intersects p_up = 0) to be at 0,
    # which means subtracting -d from every point's up-component:
    #   p_new = R @ p_old + t,   t = -d * up    (so ground sits at p_up = 0)
    t = -d * up

    # 6. Sanity check — measure camera height in the new frame.
    cam_centers_new = (R @ poses_3x4[:, :3, 3].T).T + t  # (S, 3)
    measured_heights = cam_centers_new @ up
    median_height = float(np.median(measured_heights))

    # Optional: rescale so median camera height ≈ prior. Only do this if we have
    # strong evidence that LingBot world is non-metric (median height extremely
    # far from prior). LingBot is typically metric-ish for driving footage, so
    # default to a *report-only* check rather than rescaling.
    target_height = DEFAULT_CAMERA_HEIGHT_PRIOR.get(input_type, FALLBACK_CAMERA_HEIGHT)
    height_ratio = abs(median_height) / target_height if target_height > 0 else 1.0
    logger.info(
        "Ground alignment: median camera height after align = %.3f (target prior %.2f m, ratio=%.2f)",
        median_height, target_height, height_ratio,
    )

    # 6b. Metric rescale. LingBot world is up-to-scale; recover metric scale from
    # the camera-height prior, but ONLY when the scene is clearly non-metric
    # (ratio far from 1) so we don't distort already-metric driving footage.
    # The caller applies `scale` uniformly about the ground (z=0) to camera
    # centres, world points, and depth — keeping the ground plane fixed.
    scale = 1.0
    if abs(median_height) > 1e-6 and (height_ratio < 0.5 or height_ratio > 2.0):
        scale = target_height / abs(median_height)
        logger.info(
            "Non-metric LingBot world (ratio=%.3f) -> metric scale = %.4f", height_ratio, scale)
    else:
        logger.info("Scene scale within [0.5, 2.0]x prior -> no metric rescale (scale=1.0)")

    # 7. Compose final 4x4 transform (rigid — rotation + translation only; the
    # metric scale is returned separately so it can be applied without
    # corrupting the orthonormal rotation block of c2w extrinsics).
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = R
    T[:3, 3] = t

    info = {
        "plane_normal_pre": normal.tolist(),
        "plane_d_pre": float(d),
        "median_cam_height_post": median_height,
        "target_cam_height": float(target_height),
        "scale": float(scale),
        "median_cam_height_post_scaled": float(median_height * scale),
        "num_candidates": int(len(candidates)),
    }
    return T, info


def apply_to_extrinsics(T_align: np.ndarray, ext_c2w_4x4: np.ndarray) -> np.ndarray:
    """Apply T_align to a stack of c2w transforms: new_c2w = T_align @ old_c2w."""
    return np.einsum("ij,sjk->sik", T_align, ext_c2w_4x4)


def apply_to_points(T_align: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Apply T_align to a generic (..., 3) array of world points."""
    R = T_align[:3, :3]
    t = T_align[:3, 3]
    return pts @ R.T + t
