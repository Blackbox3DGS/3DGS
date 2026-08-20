"""Stage 11: Format Conversion — .ply → .splat for web viewer.

Converts the gaussian-splatting output PLY (with SH coefficients, opacity,
scale, rotation) to the compact .splat binary format used by web viewers
(gsplat.js, antimatter15/splat, etc.).
"""

import logging
import struct
import traceback
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# .splat format: per-gaussian, 32 bytes each
# [x(f32), y(f32), z(f32), scale_0(f32), scale_1(f32), scale_2(f32),
#  r(u8), g(u8), b(u8), a(u8), rot_0(u8), rot_1(u8), rot_2(u8), rot_3(u8)]
# Total = 6*4 + 4 + 4 = 32 bytes


def run(context):
    """Stage 11 entry point.

    Reads:
        context["artifacts"]["output_ply"]  — 3DGS trained point_cloud.ply

    Writes:
        context["artifacts"]["output_splat"] — .splat file for web viewer
    """
    try:
        return _run_impl(context)
    except Exception:
        logger.error("Stage 11 failed:\n%s", traceback.format_exc())
        raise


def _run_impl(context):
    ply_path = Path(context["artifacts"]["output_ply"])

    out_root = Path(context["out_root"])
    workspace = out_root / "11_format"
    workspace.mkdir(parents=True, exist_ok=True)
    splat_path = workspace / "output.splat"

    logger.info("Stage 11: Converting %s → %s", ply_path, splat_path)

    # Read gaussian-splatting PLY
    gaussians = _read_gs_ply(ply_path)
    n = len(gaussians["xyz"])
    logger.info("  Loaded %d Gaussians from PLY", n)

    # Sort by scale (largest first) for progressive rendering
    scales = gaussians["scale"]
    volume = np.exp(scales).prod(axis=1)
    sort_idx = np.argsort(-volume)

    # Convert SH DC component (degree 0) to RGB
    sh_dc = gaussians["sh_dc"]  # (N, 3) — SH band 0 coefficients
    C0 = 0.28209479177387814  # 1 / (2 * sqrt(pi))
    rgb = np.clip(sh_dc * C0 + 0.5, 0.0, 1.0)  # SH DC to linear RGB
    rgb_u8 = (rgb * 255).astype(np.uint8)

    # Opacity: sigmoid(raw_opacity)
    opacity = 1.0 / (1.0 + np.exp(-gaussians["opacity"].squeeze()))
    alpha_u8 = (np.clip(opacity, 0.0, 1.0) * 255).astype(np.uint8)

    # Rotation quaternion: normalize then quantize to uint8
    rot = gaussians["rotation"]  # (N, 4)
    rot = rot / (np.linalg.norm(rot, axis=1, keepdims=True) + 1e-10)
    # Map [-1, 1] → [0, 255]
    rot_u8 = ((rot * 128 + 128).clip(0, 255)).astype(np.uint8)

    # Scale: log-scale values, stored as float32
    scale_f32 = np.exp(gaussians["scale"]).astype(np.float32)

    # Write .splat binary
    xyz = gaussians["xyz"].astype(np.float32)

    # Build structured array for bulk write
    dtype = np.dtype([
        ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
        ("sx", "<f4"), ("sy", "<f4"), ("sz", "<f4"),
        ("r", "u1"), ("g", "u1"), ("b", "u1"), ("a", "u1"),
        ("qw", "u1"), ("qx", "u1"), ("qy", "u1"), ("qz", "u1"),
    ])
    data = np.zeros(n, dtype=dtype)

    # Apply sort order
    data["x"] = xyz[sort_idx, 0]
    data["y"] = xyz[sort_idx, 1]
    data["z"] = xyz[sort_idx, 2]
    data["sx"] = scale_f32[sort_idx, 0]
    data["sy"] = scale_f32[sort_idx, 1]
    data["sz"] = scale_f32[sort_idx, 2]
    data["r"] = rgb_u8[sort_idx, 0]
    data["g"] = rgb_u8[sort_idx, 1]
    data["b"] = rgb_u8[sort_idx, 2]
    data["a"] = alpha_u8[sort_idx]
    data["qw"] = rot_u8[sort_idx, 0]
    data["qx"] = rot_u8[sort_idx, 1]
    data["qy"] = rot_u8[sort_idx, 2]
    data["qz"] = rot_u8[sort_idx, 3]

    with open(splat_path, "wb") as f:
        f.write(data.tobytes())

    size_mb = splat_path.stat().st_size / (1024 * 1024)
    logger.info("Stage 11 complete: %s (%.1f MB, %d Gaussians, 32 bytes each)",
                splat_path, size_mb, n)

    context["artifacts"]["output_splat"] = str(splat_path)
    return context


def _read_gs_ply(ply_path: Path) -> dict:
    """Read gaussian-splatting output PLY (plyfile format).

    Expected properties: x,y,z, f_dc_0..2, f_rest_0..N, opacity,
    scale_0..2, rot_0..3.
    """
    from plyfile import PlyData

    plydata = PlyData.read(str(ply_path))
    v = plydata["vertex"]
    n = len(v)

    xyz = np.stack([v["x"], v["y"], v["z"]], axis=1).astype(np.float64)

    # SH DC coefficients (band 0, 3 channels)
    sh_dc = np.stack([v["f_dc_0"], v["f_dc_1"], v["f_dc_2"]], axis=1)

    opacity = v["opacity"].reshape(-1, 1)

    scale = np.stack([v["scale_0"], v["scale_1"], v["scale_2"]], axis=1)

    rotation = np.stack([v["rot_0"], v["rot_1"], v["rot_2"], v["rot_3"]], axis=1)

    return {
        "xyz": xyz,
        "sh_dc": sh_dc,
        "opacity": opacity,
        "scale": scale,
        "rotation": rotation,
    }
