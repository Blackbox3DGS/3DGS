"""Stage 10p: Point-cloud → .splat (no 3DGS training).

Drop-in replacement for Stage 10 (3DGS) + Stage 11 (format) when the scene is
forward-driving monocular footage, where 3DGS produces spiky blobs because the
poses lack the mm/sub-degree accuracy GS needs at low parallax. LingBot's fused
point cloud (Stage 07 → 08, already dynamic-masked + metric + outlier-filtered)
is robust to that pose noise, so we render it directly: each point becomes a
small isotropic Gaussian written in the exact 32-byte .splat layout the web
viewer (and Stage 12) already consume — so the frontend needs no change.

Reads:
    context["artifacts"]["filtered_pointcloud"]  — Stage 08 filtered.ply (XYZ+RGB)

Writes:
    context["artifacts"]["output_splat"]         — output.splat (points as Gaussians)

Env:
    PC_SPLAT_MAX_POINTS   web point budget (default 1_500_000; voxel-downsampled)
    PC_SPLAT_POINT_SIZE   per-point gaussian size in metres (default 0.05)
"""

import logging
import os
import traceback
from pathlib import Path

import numpy as np
import open3d as o3d

logger = logging.getLogger(__name__)

DEFAULT_MAX_POINTS = 1_500_000
DEFAULT_POINT_SIZE = 0.05  # metres (scene is metric after Stage 04g Gap 6)

# .splat layout (matches 11_format): 32 bytes/point —
# x,y,z,sx,sy,sz (f32) + r,g,b,a (u8) + qw,qx,qy,qz (u8, quat*128+128).
_SPLAT_DTYPE = np.dtype([
    ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
    ("sx", "<f4"), ("sy", "<f4"), ("sz", "<f4"),
    ("r", "u1"), ("g", "u1"), ("b", "u1"), ("a", "u1"),
    ("qw", "u1"), ("qx", "u1"), ("qy", "u1"), ("qz", "u1"),
])


def run(context):
    """Stage 10p entry point."""
    try:
        return _run_impl(context)
    except Exception:
        logger.error("Stage 10p failed:\n%s", traceback.format_exc())
        raise


def _voxel_downsample_to_budget(pcd: o3d.geometry.PointCloud,
                                max_points: int) -> o3d.geometry.PointCloud:
    """Voxel-downsample until the cloud fits the web point budget.

    Starts from the cloud's own scale and grows the voxel geometrically until
    under budget — keeps the cloud spatially uniform (better than random drop
    for a background) without needing to know absolute units up front.
    """
    n = len(pcd.points)
    if n <= max_points:
        return pcd

    aabb = pcd.get_axis_aligned_bounding_box()
    diag = float(np.linalg.norm(aabb.get_extent())) or 1.0
    voxel = diag / 1000.0  # ~1/1000 of scene diagonal as a starting guess
    for _ in range(20):
        down = pcd.voxel_down_sample(voxel_size=voxel)
        if len(down.points) <= max_points:
            logger.info("Voxel downsample: %d -> %d points (voxel=%.4f m)",
                        n, len(down.points), voxel)
            return down
        voxel *= 1.3
    logger.info("Voxel downsample (capped): %d -> %d points (voxel=%.4f m)",
                n, len(down.points), voxel)
    return down


def _run_impl(context):
    ply_path = Path(context["artifacts"]["filtered_pointcloud"])

    out_root = Path(context["out_root"])
    workspace = out_root / "10p_pcsplat"
    workspace.mkdir(parents=True, exist_ok=True)
    splat_path = workspace / "output.splat"

    max_points = int(os.environ.get("PC_SPLAT_MAX_POINTS", DEFAULT_MAX_POINTS))
    point_size = float(os.environ.get("PC_SPLAT_POINT_SIZE", DEFAULT_POINT_SIZE))

    logger.info("Stage 10p: %s -> %s (max_points=%d, point_size=%.3f m)",
                ply_path, splat_path, max_points, point_size)

    pcd = o3d.io.read_point_cloud(str(ply_path))
    if len(pcd.points) == 0:
        raise RuntimeError(f"Empty point cloud: {ply_path}")
    pcd = _voxel_downsample_to_budget(pcd, max_points)

    xyz = np.asarray(pcd.points, dtype=np.float32)
    n = len(xyz)
    if pcd.has_colors():
        rgb = np.clip(np.asarray(pcd.colors) * 255.0, 0, 255).astype(np.uint8)
    else:
        rgb = np.full((n, 3), 200, dtype=np.uint8)

    data = np.zeros(n, dtype=_SPLAT_DTYPE)
    data["x"], data["y"], data["z"] = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    # Isotropic small gaussian per point (linear scale in metres).
    data["sx"] = data["sy"] = data["sz"] = np.float32(point_size)
    data["r"], data["g"], data["b"] = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    data["a"] = 255  # opaque
    # Identity quaternion (1,0,0,0) -> u8 via q*128+128.
    data["qw"], data["qx"], data["qy"], data["qz"] = 255, 128, 128, 128

    with open(splat_path, "wb") as f:
        f.write(data.tobytes())

    size_mb = splat_path.stat().st_size / (1024 * 1024)
    logger.info("Stage 10p complete: %s (%.1f MB, %d points as Gaussians)",
                splat_path, size_mb, n)

    context["artifacts"]["output_splat"] = str(splat_path)
    return context
