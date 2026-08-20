"""Filter sparse 3D points by projecting into detected vehicle bounding boxes."""

import json
import logging
from pathlib import Path

import numpy as np

from .model_parser import (
    parse_images_txt,
    parse_images_txt_with_ids,
    parse_points3D_txt,
    write_points3D_txt,
)

logger = logging.getLogger(__name__)


def _load_bboxes_by_frame(bbox_sequence_path):
    """Load all vehicle bboxes from bbox_sequence.json, grouped by frame name.

    Returns dict: frame_name -> list of [x1, y1, x2, y2] bboxes.
    Includes ALL detected vehicles regardless of dynamic/static classification.
    """
    with open(bbox_sequence_path) as f:
        data = json.load(f)

    # Build frame_idx -> frame_name mapping is not available here,
    # so we index by frame_idx (int) and let caller map.
    bboxes_by_frame_idx = {}

    for track_id, track_data in data["tracks"].items():
        for frame_idx_str, frame_info in track_data["frames"].items():
            frame_idx = int(frame_idx_str)
            if frame_idx not in bboxes_by_frame_idx:
                bboxes_by_frame_idx[frame_idx] = []
            bboxes_by_frame_idx[frame_idx].append(frame_info["bbox"])

    return bboxes_by_frame_idx


def _frame_name_to_idx(frame_name):
    """Extract frame index from filename like 'frame_000001_1234567.jpg'.

    Also handles 'frame_000001.jpg' format.
    """
    stem = Path(frame_name).stem  # 'frame_000001_1234567' or 'frame_000001'
    parts = stem.split("_")
    # Index is always the second part (after 'frame')
    return int(parts[1])


def _project_point(xyz, pose_w2c, intrinsics):
    """Project a 3D world point into image coordinates.

    Args:
        xyz: (3,) world coordinates
        pose_w2c: (3, 4) world-to-camera [R|t] matrix
        intrinsics: dict with fx, fy, cx, cy

    Returns:
        (u, v) pixel coordinates or None if behind camera.
    """
    # Transform to camera coordinates
    p_cam = pose_w2c[:3, :3] @ xyz + pose_w2c[:3, 3]

    # Check if point is behind camera
    if p_cam[2] <= 0:
        return None

    # Project
    u = intrinsics["fx"] * p_cam[0] / p_cam[2] + intrinsics["cx"]
    v = intrinsics["fy"] * p_cam[1] / p_cam[2] + intrinsics["cy"]
    return u, v


def _point_in_any_bbox(u, v, bboxes, margin=10):
    """Check if pixel (u, v) falls inside any bbox (with margin).

    Args:
        u, v: pixel coordinates
        bboxes: list of [x1, y1, x2, y2]
        margin: extra pixels around bbox to catch near-boundary points
    """
    for x1, y1, x2, y2 in bboxes:
        if (x1 - margin) <= u <= (x2 + margin) and (y1 - margin) <= v <= (y2 + margin):
            return True
    return False


def filter_points_by_bboxes(text_dir, bbox_sequence_path, intrinsics):
    """Filter sparse 3D points that project into any detected vehicle bbox.

    Modifies points3D.txt in-place (overwrites).

    Args:
        text_dir: path to sparse_text/ directory containing cameras.txt, images.txt, points3D.txt
        bbox_sequence_path: path to bbox_sequence.json from Stage 03
        intrinsics: camera intrinsics dict (fx, fy, cx, cy)

    Returns:
        (original_count, filtered_count) tuple.
    """
    text_dir = Path(text_dir)
    points3d_path = text_dir / "points3D.txt"

    if not points3d_path.exists():
        logger.warning("points3D.txt not found at %s, skipping filter", points3d_path)
        return 0, 0

    if not Path(bbox_sequence_path).exists():
        logger.warning("bbox_sequence.json not found at %s, skipping filter", bbox_sequence_path)
        return 0, 0

    # Parse inputs
    points = parse_points3D_txt(points3d_path)
    bboxes_by_frame_idx = _load_bboxes_by_frame(bbox_sequence_path)
    id_to_name = parse_images_txt_with_ids(text_dir / "images.txt")

    # Build image_id -> frame_idx mapping
    id_to_frame_idx = {}
    for image_id, name in id_to_name.items():
        try:
            id_to_frame_idx[image_id] = _frame_name_to_idx(name)
        except (ValueError, IndexError):
            continue

    # Build world-to-camera poses from images.txt
    image_poses_c2w = parse_images_txt(text_dir / "images.txt")
    # Convert c2w to w2c for projection
    w2c_by_name = {}
    for name, T_c2w in image_poses_c2w.items():
        R_c2w = T_c2w[:3, :3]
        t_c2w = T_c2w[:3, 3]
        R_w2c = R_c2w.T
        t_w2c = -R_c2w.T @ t_c2w
        w2c = np.zeros((3, 4))
        w2c[:3, :3] = R_w2c
        w2c[:3, 3] = t_w2c
        w2c_by_name[name] = w2c

    original_count = len(points)
    filtered_points = []
    bbox_hit_threshold = 0.5  # Remove only if >50% of observing frames hit a bbox

    for point in points:
        xyz = np.array(point["xyz"])
        checked = 0
        hits = 0

        for image_id, _ in point["track"]:
            name = id_to_name.get(image_id)
            if name is None:
                continue

            frame_idx = id_to_frame_idx.get(image_id)
            if frame_idx is None:
                continue

            w2c = w2c_by_name.get(name)
            if w2c is None:
                continue

            proj = _project_point(xyz, w2c, intrinsics)
            if proj is None:
                continue

            checked += 1
            bboxes = bboxes_by_frame_idx.get(frame_idx, [])
            if bboxes and _point_in_any_bbox(u=proj[0], v=proj[1], bboxes=bboxes):
                hits += 1

        # Remove only if majority of observing frames have the point inside a bbox
        hit_rate = hits / checked if checked > 0 else 0
        if hit_rate <= bbox_hit_threshold:
            filtered_points.append(point)

    # Overwrite points3D.txt
    write_points3D_txt(filtered_points, points3d_path)

    filtered_count = len(filtered_points)
    removed = original_count - filtered_count
    logger.info(
        "Point filtering: %d -> %d (removed %d points in vehicle bboxes)",
        original_count, filtered_count, removed,
    )
    return original_count, filtered_count
