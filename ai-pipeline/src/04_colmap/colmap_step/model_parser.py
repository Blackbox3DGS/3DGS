"""Parse COLMAP text model output (cameras.txt, images.txt)."""

import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def qvec_to_rotmat(qvec):
    """Convert COLMAP quaternion (w, x, y, z) to 3x3 rotation matrix."""
    w, x, y, z = qvec
    return np.array([
        [1 - 2*y*y - 2*z*z, 2*x*y - 2*w*z,     2*x*z + 2*w*y],
        [2*x*y + 2*w*z,     1 - 2*x*x - 2*z*z, 2*y*z - 2*w*x],
        [2*x*z - 2*w*y,     2*y*z + 2*w*x,     1 - 2*x*x - 2*y*y],
    ])


def parse_cameras_txt(cameras_path):
    """Parse COLMAP cameras.txt.

    Returns dict with fx, fy, cx, cy, width, height, model.
    Supports PINHOLE (fx, fy, cx, cy) and SIMPLE_PINHOLE (f, cx, cy).
    """
    cameras_path = Path(cameras_path)
    with open(cameras_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            model = parts[1]
            width = int(parts[2])
            height = int(parts[3])
            params = [float(p) for p in parts[4:]]

            if model == "PINHOLE":
                fx, fy, cx, cy = params[:4]
            elif model == "SIMPLE_PINHOLE":
                f, cx, cy = params[:3]
                fx = fy = f
            elif model == "OPENCV":
                fx, fy, cx, cy = params[:4]
            else:
                raise ValueError(f"Unsupported camera model: {model}")

            result = {
                "model": model,
                "width": width,
                "height": height,
                "fx": fx,
                "fy": fy,
                "cx": cx,
                "cy": cy,
            }
            if model == "OPENCV" and len(params) >= 8:
                result["k1"] = params[4]
                result["k2"] = params[5]
                result["p1"] = params[6]
                result["p2"] = params[7]
            logger.info(
                "Camera: %s %dx%d, fx=%.1f fy=%.1f cx=%.1f cy=%.1f",
                model, width, height, fx, fy, cx, cy,
            )
            return result

    raise ValueError(f"No camera entries found in {cameras_path}")


def parse_images_txt(images_path):
    """Parse COLMAP images.txt.

    COLMAP outputs world-to-camera transforms. This function inverts
    them to camera-to-world (c2w) 4x4 SE(3) matrices.

    Returns dict mapping filename -> (4, 4) camera-to-world matrix.
    """
    images_path = Path(images_path)
    poses = {}

    with open(images_path) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    # Lines alternate: pose line, then 2D points line
    for i in range(0, len(lines), 2):
        parts = lines[i].split()
        qw, qx, qy, qz = (
            float(parts[1]), float(parts[2]),
            float(parts[3]), float(parts[4]),
        )
        tx, ty, tz = float(parts[5]), float(parts[6]), float(parts[7])
        name = parts[9]

        # COLMAP gives world-to-camera: p_cam = R * p_world + t
        R_w2c = qvec_to_rotmat(np.array([qw, qx, qy, qz]))
        t_w2c = np.array([tx, ty, tz])

        # Invert to camera-to-world
        R_c2w = R_w2c.T
        t_c2w = -R_w2c.T @ t_w2c

        T = np.eye(4)
        T[:3, :3] = R_c2w
        T[:3, 3] = t_c2w
        poses[name] = T

    logger.info("Parsed %d image poses from %s", len(poses), images_path)
    return poses


def parse_points3D_txt(points3d_path):
    """Parse COLMAP points3D.txt.

    Each line: POINT3D_ID X Y Z R G B ERROR TRACK[] (IMAGE_ID POINT2D_IDX pairs)

    Returns list of dicts with keys: point3d_id, xyz, rgb, error, track.
    track is list of (image_id, point2d_idx) tuples.
    """
    points3d_path = Path(points3d_path)
    points = []

    with open(points3d_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            point3d_id = int(parts[0])
            xyz = [float(parts[1]), float(parts[2]), float(parts[3])]
            rgb = [int(parts[4]), int(parts[5]), int(parts[6])]
            error = float(parts[7])

            track = []
            for i in range(8, len(parts), 2):
                image_id = int(parts[i])
                point2d_idx = int(parts[i + 1])
                track.append((image_id, point2d_idx))

            points.append({
                "point3d_id": point3d_id,
                "xyz": xyz,
                "rgb": rgb,
                "error": error,
                "track": track,
            })

    logger.info("Parsed %d 3D points from %s", len(points), points3d_path)
    return points


def write_points3D_txt(points, out_path):
    """Write COLMAP points3D.txt format."""
    out_path = Path(out_path)
    with open(out_path, "w") as f:
        f.write("# 3D point list with one line of data per point:\n")
        f.write("#   POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[] as (IMAGE_ID, POINT2D_IDX)\n")
        f.write(f"# Number of points: {len(points)}\n")

        for p in points:
            track_str = " ".join(
                f"{img_id} {pt_idx}" for img_id, pt_idx in p["track"]
            )
            f.write(
                f"{p['point3d_id']} {p['xyz'][0]} {p['xyz'][1]} {p['xyz'][2]} "
                f"{p['rgb'][0]} {p['rgb'][1]} {p['rgb'][2]} {p['error']} "
                f"{track_str}\n"
            )

    logger.info("Wrote %d 3D points to %s", len(points), out_path)


def parse_images_txt_with_ids(images_path):
    """Parse COLMAP images.txt, returning image_id -> filename mapping.

    Unlike parse_images_txt(), this returns a dict of {image_id: filename}
    for use in point filtering (points3D.txt references image_id).
    """
    images_path = Path(images_path)
    id_to_name = {}

    with open(images_path) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    for i in range(0, len(lines), 2):
        parts = lines[i].split()
        image_id = int(parts[0])
        name = parts[9]
        id_to_name[image_id] = name

    return id_to_name


def save_poses(image_poses, sorted_names, out_path):
    """Save camera-to-world poses as (M, 4, 4) numpy array.

    Returns list of registered frame names in order.
    """
    out_path = Path(out_path)
    matrices = np.stack([image_poses[name] for name in sorted_names])
    np.save(out_path, matrices)
    logger.info("Saved poses: shape %s -> %s", matrices.shape, out_path)
    return sorted_names


def save_intrinsics(camera_params, out_path):
    """Save camera intrinsics as JSON."""
    out_path = Path(out_path)
    with open(out_path, "w") as f:
        json.dump(camera_params, f, indent=2)
    logger.info("Saved intrinsics -> %s", out_path)


def save_registered_frames(frame_names, total_input, out_path):
    """Save registered frames list as JSON."""
    out_path = Path(out_path)
    data = {
        "total_input": total_input,
        "registered": len(frame_names),
        "rate": round(len(frame_names) / total_input, 4) if total_input > 0 else 0,
        "frames": frame_names,
    }
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(
        "Registration: %d/%d frames (%.1f%%)",
        len(frame_names), total_input, data["rate"] * 100,
    )
