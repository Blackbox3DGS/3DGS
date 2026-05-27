"""Write LingBot-MAP outputs as a COLMAP-compatible sparse model.

Produces a `sparse/0/` directory containing cameras.txt, images.txt, and
points3D.txt that Stage 10 (`10_3dgs/gs/data_prep.py`) can consume directly.

Conventions matching the rest of the pipeline:
  - `cameras.txt`: single PINHOLE entry (Stage 10 already strips OPENCV to PINHOLE)
  - `images.txt`: world-to-camera quaternion + translation per frame, same
                  ordering as `poses.npy`
  - `points3D.txt`: a thresholded subsample of LingBot's per-pixel world points

The text format is what `colmap model_converter --output_type TXT` writes; the
Inria gaussian-splatting Scene loader accepts either the text or binary form.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation as R

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Geometry helpers
# ----------------------------------------------------------------------------

def c2w_to_w2c_qvec_tvec(c2w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert a (4, 4) camera-to-world matrix into COLMAP's (qvec_wxyz, tvec).

    COLMAP stores world-to-camera; `R_w2c = R_c2w.T` and `t_w2c = -R_w2c @ t_c2w`.
    Quaternion is in (w, x, y, z) order.
    """
    R_c2w = c2w[:3, :3]
    t_c2w = c2w[:3, 3]
    R_w2c = R_c2w.T
    t_w2c = -R_w2c @ t_c2w
    quat_xyzw = R.from_matrix(R_w2c).as_quat()  # scipy returns (x, y, z, w)
    qvec = np.array([quat_xyzw[3], quat_xyzw[0], quat_xyzw[1], quat_xyzw[2]])
    return qvec, t_w2c


# ----------------------------------------------------------------------------
# Writers
# ----------------------------------------------------------------------------

def write_cameras_txt(out_path: Path, width: int, height: int,
                      fx: float, fy: float, cx: float, cy: float) -> None:
    """Write a single PINHOLE camera definition."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write("# Camera list with one line of data per camera:\n")
        f.write("#   CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n")
        f.write("# Number of cameras: 1\n")
        f.write(f"1 PINHOLE {width} {height} {fx} {fy} {cx} {cy}\n")


def write_images_txt(out_path: Path, frame_names: list[str],
                     c2w_poses: np.ndarray, camera_id: int = 1) -> None:
    """Write COLMAP images.txt — pose line + (empty) 2D points line per frame."""
    assert len(frame_names) == len(c2w_poses), \
        f"frame count mismatch: {len(frame_names)} names vs {len(c2w_poses)} poses"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write("# Image list with two lines of data per image:\n")
        f.write("#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n")
        f.write("#   POINTS2D[] as (X, Y, POINT3D_ID)\n")
        f.write(f"# Number of images: {len(frame_names)}\n")

        for idx, (name, c2w) in enumerate(zip(frame_names, c2w_poses), start=1):
            qvec, tvec = c2w_to_w2c_qvec_tvec(c2w)
            f.write(
                f"{idx} {qvec[0]} {qvec[1]} {qvec[2]} {qvec[3]} "
                f"{tvec[0]} {tvec[1]} {tvec[2]} {camera_id} {name}\n"
            )
            # Second line: 2D point observations. Stage 10's _filter_images_txt
            # treats this as opaque, and the Inria Scene loader uses it only when
            # reconstructing the sparse track graph (not needed for our flow).
            f.write("\n")


def write_points3D_txt(out_path: Path, xyz: np.ndarray,
                       rgb: np.ndarray | None = None) -> None:
    """Write a points3D.txt with N points; track is left empty (no observations)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = len(xyz)
    if rgb is None:
        rgb = np.full((n, 3), 128, dtype=np.uint8)
    with open(out_path, "w") as f:
        f.write("# 3D point list with one line of data per point:\n")
        f.write("#   POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[] as (IMAGE_ID, POINT2D_IDX)\n")
        f.write(f"# Number of points: {n}\n")
        for i in range(n):
            x, y, z = xyz[i]
            r, g, b = int(rgb[i, 0]), int(rgb[i, 1]), int(rgb[i, 2])
            f.write(f"{i + 1} {x} {y} {z} {r} {g} {b} 0.0\n")


def write_sparse_ply(out_path: Path, xyz: np.ndarray,
                     rgb: np.ndarray | None = None) -> None:
    """Write a simple binary-little-endian PLY with x,y,z + uchar r,g,b."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = len(xyz)
    if rgb is None:
        rgb = np.full((n, 3), 128, dtype=np.uint8)
    dtype = np.dtype([
        ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
        ("red", "u1"), ("green", "u1"), ("blue", "u1"),
    ])
    data = np.zeros(n, dtype=dtype)
    data["x"], data["y"], data["z"] = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    data["red"], data["green"], data["blue"] = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {n}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    )
    with open(out_path, "wb") as f:
        f.write(header.encode("ascii"))
        f.write(data.tobytes())
    logger.info("Wrote %d points to %s", n, out_path)
