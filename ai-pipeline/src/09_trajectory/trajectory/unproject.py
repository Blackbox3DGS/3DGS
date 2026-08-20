"""Single-pixel pinhole unprojection: (u, v, depth_m) → world (x, y, z)."""

import numpy as np


def pixel_to_world(
    u: float,
    v: float,
    depth: float,
    c2w: np.ndarray,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
) -> tuple[float, float, float]:
    """Unproject a single pixel to world coordinates.

    Inverse of the forward projection in 06_scale.scale.align.project_points_to_frame.

    Parameters
    ----------
    u, v   : pixel coordinates (float; sub-pixel allowed)
    depth  : metric depth at that pixel (metres, > 0)
    c2w    : (4, 4) camera-to-world transform
    fx, fy, cx, cy : pinhole intrinsics
    """
    x_cam = (u - cx) / fx * depth
    y_cam = (v - cy) / fy * depth
    z_cam = depth
    pt_cam = np.array([x_cam, y_cam, z_cam, 1.0], dtype=np.float64)
    pt_world = c2w @ pt_cam
    return float(pt_world[0]), float(pt_world[1]), float(pt_world[2])
