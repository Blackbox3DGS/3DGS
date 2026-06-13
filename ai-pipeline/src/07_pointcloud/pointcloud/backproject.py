"""Dense backprojection: depth map pixels → 3D world coordinates with RGB."""

import numpy as np


def backproject_frame(
    depth_map: np.ndarray,
    c2w: np.ndarray,
    fx: float, fy: float, cx: float, cy: float,
    image: np.ndarray | None = None,
    step: int = 2,
    min_depth: float = 0.5,
    max_depth: float = 150.0,
    mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Backproject all valid pixels in a depth map to 3D world coordinates.

    Parameters
    ----------
    depth_map : (H, W) float32, absolute depth in metres.
    c2w       : (4, 4) camera-to-world transform.
    image     : (H, W, 3) uint8 RGB image for colour extraction.
    step      : pixel subsampling stride (1 = every pixel, 2 = every other).
    min_depth : discard pixels with depth below this (metres).
    max_depth : discard pixels with depth above this (metres).
    mask      : (H, W) dynamic-object mask (Stage 03 convention: nonzero =
                dynamic). Dynamic pixels are excluded so moving vehicles do not
                seed ghost points / floaters in the dense cloud. Must match the
                depth_map resolution. None keeps every pixel.

    Returns
    -------
    points : (K, 3) float64 world coordinates.
    colors : (K, 3) uint8 RGB, or None if *image* is None.
    """
    H, W = depth_map.shape

    vs = np.arange(0, H, step)
    us = np.arange(0, W, step)
    uu, vv = np.meshgrid(us, vs)  # (Hg, Wg)
    uu = uu.ravel()
    vv = vv.ravel()

    depths = depth_map[vv, uu]
    valid = (depths > min_depth) & (depths < max_depth) & np.isfinite(depths)
    if mask is not None:
        valid = valid & (mask[vv, uu] == 0)  # drop dynamic pixels
    uu = uu[valid]
    vv = vv[valid]
    depths = depths[valid]

    # Camera-space coordinates (pinhole model)
    x_cam = (uu.astype(np.float64) - cx) / fx * depths
    y_cam = (vv.astype(np.float64) - cy) / fy * depths
    z_cam = depths.astype(np.float64)

    # World-space via c2w
    ones = np.ones_like(z_cam)
    pts_cam = np.stack([x_cam, y_cam, z_cam, ones], axis=1)  # (K, 4)
    pts_world = (c2w @ pts_cam.T).T[:, :3]  # (K, 3)

    # Filter non-finite results
    finite = np.all(np.isfinite(pts_world), axis=1)
    pts_world = pts_world[finite]

    colors = None
    if image is not None:
        colors = image[vv, uu]  # (K, 3) uint8
        colors = colors[finite]

    return pts_world, colors
