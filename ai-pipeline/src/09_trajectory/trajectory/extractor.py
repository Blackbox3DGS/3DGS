"""Per-frame ROI / depth-percentile sampling for Stage 09."""

import logging
from collections import defaultdict
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def build_frame_index(
    images_colmap: Path,
    registered_frames: list[str],
) -> tuple[list[str], dict[str, int]]:
    """Resolve frame_idx ↔ filename ↔ pose_idx mapping.

    Stage 03 enumerates `sorted(images_colmap.glob("*.jpg"))` and assigns
    frame_idx by enumerate index — see 03_seg/seg/detect.py. Mirror that here
    so bbox_sequence frame_idx values resolve to the same filenames.

    Returns
    -------
    sorted_filenames : list[str]
        Filenames (basename only) of all extracted frames in frame_idx order.
    fname_to_pose_idx : dict[str, int]
        Maps registered filenames → index into poses.npy. Unregistered
        filenames are absent.
    """
    sorted_paths = sorted(Path(images_colmap).glob("*.jpg"))
    sorted_filenames = [p.name for p in sorted_paths]
    fname_to_pose_idx = {name: i for i, name in enumerate(registered_frames)}
    return sorted_filenames, fname_to_pose_idx


def build_per_frame_track_bboxes(
    bbox_sequence: dict,
    target_ids: set[str],
) -> dict[int, list[tuple[str, tuple[int, int, int, int]]]]:
    """Map frame_idx → [(track_id, bbox), ...] for target tracks present.

    Used both as the frame-major work plan and to derive the
    "other-track bbox exclusion" set when sampling a given track.
    """
    out: dict[int, list[tuple[str, tuple[int, int, int, int]]]] = defaultdict(list)
    tracks = bbox_sequence.get("tracks", {})
    for tid, tinfo in tracks.items():
        if tid not in target_ids:
            continue
        for f_str, fdata in tinfo.get("frames", {}).items():
            f_idx = int(f_str)
            bbox = tuple(int(v) for v in fdata["bbox"])  # (x1, y1, x2, y2)
            out[f_idx].append((tid, bbox))
    return out


def _bboxes_overlap(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def sample_track_frame(
    mask_img: np.ndarray,
    depth_map: np.ndarray,
    bbox: tuple[int, int, int, int],
    other_bboxes: list[tuple[int, int, int, int]],
    *,
    lower_frac: float = 0.40,
    pct_low: float = 20.0,
    pct_high: float = 30.0,
    min_roi_pixels: int = 20,
    min_pct_pixels: int = 5,
) -> tuple[float, float, float] | None:
    """Sample (u, v, depth) at the bottom-center pixel of the bounding box.

    u = horizontal midpoint of bbox, v = bottom edge of bbox (ground contact).
    depth is read directly from depth_map at that pixel.
    Returns None if the pixel is out of bounds or depth is invalid.
    """
    H, W = depth_map.shape[:2]

    x1, y1, x2, y2 = bbox
    x1 = max(0, min(W - 1, int(x1)))
    x2 = max(0, min(W - 1, int(x2)))
    y2 = max(0, min(H - 1, int(y2)))
    if x2 <= x1:
        return None

    u = (x1 + x2) / 2.0
    v = float(y2)

    depth = float(depth_map[int(round(v)), int(round(u))])
    if not np.isfinite(depth) or depth <= 0:
        return None

    return u, v, depth


def collect_other_bboxes(
    frame_track_bboxes: list[tuple[str, tuple[int, int, int, int]]],
    current_tid: str,
    current_bbox: tuple[int, int, int, int],
) -> list[tuple[int, int, int, int]]:
    """Return bboxes of OTHER target tracks at this frame that overlap the current bbox."""
    out = []
    for tid, bb in frame_track_bboxes:
        if tid == current_tid:
            continue
        if _bboxes_overlap(bb, current_bbox):
            out.append(bb)
    return out
