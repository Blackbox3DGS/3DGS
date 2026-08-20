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
    """Sample a robust (u, v, depth) tuple from a single track's ROI.

    ROI = bbox ∩ (mask == 255) ∩ lower `lower_frac` of bbox
          ∩ NOT(any other_bbox).

    Returns None when the ROI or [P_low, P_high] subset is too small.
    """
    H, W = depth_map.shape[:2]

    x1, y1, x2, y2 = bbox
    x1 = max(0, min(W, int(x1)))
    y1 = max(0, min(H, int(y1)))
    x2 = max(0, min(W, int(x2)))
    y2 = max(0, min(H, int(y2)))
    if x2 <= x1 or y2 <= y1:
        return None

    bh = y2 - y1
    y_lower = y1 + int(round((1.0 - lower_frac) * bh))
    if y_lower >= y2:
        return None

    mask_crop = mask_img[y_lower:y2, x1:x2] == 255
    if not mask_crop.any():
        return None

    if other_bboxes:
        excl = np.zeros_like(mask_crop, dtype=bool)
        for ob in other_bboxes:
            ox1, oy1, ox2, oy2 = ob
            ox1 = max(x1, min(x2, int(ox1)))
            oy1 = max(y_lower, min(y2, int(oy1)))
            ox2 = max(x1, min(x2, int(ox2)))
            oy2 = max(y_lower, min(y2, int(oy2)))
            if ox2 > ox1 and oy2 > oy1:
                excl[oy1 - y_lower : oy2 - y_lower, ox1 - x1 : ox2 - x1] = True
        mask_crop &= ~excl

    if int(mask_crop.sum()) < min_roi_pixels:
        return None

    depth_crop = depth_map[y_lower:y2, x1:x2]
    vs_local, us_local = np.nonzero(mask_crop)
    depths = depth_crop[vs_local, us_local]

    finite = np.isfinite(depths) & (depths > 0)
    if int(finite.sum()) < min_roi_pixels:
        return None
    vs_local = vs_local[finite]
    us_local = us_local[finite]
    depths = depths[finite]

    p_lo, p_hi = np.percentile(depths, [pct_low, pct_high])
    keep = (depths >= p_lo) & (depths <= p_hi)
    if int(keep.sum()) < min_pct_pixels:
        return None

    u_med = float(np.median(us_local[keep])) + x1
    v_med = float(np.median(vs_local[keep])) + y_lower
    d_med = float(np.median(depths[keep]))
    return u_med, v_med, d_med


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
