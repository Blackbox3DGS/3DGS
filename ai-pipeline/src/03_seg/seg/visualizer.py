"""Stage 03 sample overlay: bbox + track ID + class on a 3x3 contact sheet."""

import logging
from pathlib import Path

import cv2
import numpy as np

from common.viz import render_frame_grid, sample_evenly

logger = logging.getLogger(__name__)


def _color_for_id(track_id: int) -> tuple[int, int, int]:
    """Deterministic BGR colour per track id."""
    if track_id < 0:
        return (120, 120, 120)
    hue = (track_id * 47) % 180
    hsv = np.uint8([[[hue, 220, 240]]])
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


def _draw_overlay(
    image: np.ndarray,
    detections,
    track_states: dict[int, str],
    *,
    mask_alpha: float = 0.35,
) -> np.ndarray:
    """Draw bbox + ID label + dynamic mask alpha on a copy of `image` (BGR)."""
    out = image.copy()
    overlay = out.copy()

    for det in detections:
        x1, y1, x2, y2 = (int(v) for v in det.bbox)
        state = track_states.get(det.track_id, "dynamic" if det.track_id != -1 else "static")
        color = _color_for_id(det.track_id) if state == "dynamic" else (140, 140, 140)

        # Mask alpha-fill within bbox (only dynamic)
        if state == "dynamic" and det.mask_crop is not None:
            crop_h, crop_w = det.mask_crop.shape
            ah = min(crop_h, max(0, y2 - y1), out.shape[0] - max(0, y1))
            aw = min(crop_w, max(0, x2 - x1), out.shape[1] - max(0, x1))
            if ah > 0 and aw > 0:
                mreg = det.mask_crop[:ah, :aw]
                yy, xx = np.where(mreg)
                if len(yy):
                    overlay[y1 + yy, x1 + xx] = color

        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"{det.track_id}:{det.class_name} ({state[0]})"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        ly1 = max(0, y1 - th - 4)
        cv2.rectangle(out, (x1, ly1), (x1 + tw + 6, ly1 + th + 4), color, -1)
        cv2.putText(out, label, (x1 + 3, ly1 + th + 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    return cv2.addWeighted(overlay, mask_alpha, out, 1.0 - mask_alpha, 0)


def write_seg_overlay_sample(
    frame_paths: list[Path],
    all_detections: list,
    track_states: dict[int, str],
    out_path: Path,
    *,
    n_samples: int = 9,
) -> str:
    """Render a 3x3 contact sheet of frames with seg overlays."""
    if not frame_paths:
        return ""
    pairs = list(zip(frame_paths, all_detections))
    picks = sample_evenly(pairs, n_samples)
    images: list[np.ndarray] = []
    labels: list[str] = []
    for fp, fd in picks:
        img = cv2.imread(str(fp))
        if img is None:
            continue
        overlay = _draw_overlay(img, fd.detections, track_states)
        images.append(overlay)
        n_dyn = sum(
            1 for d in fd.detections
            if track_states.get(d.track_id, "dynamic") == "dynamic" and d.track_id != -1
        )
        labels.append(f"{fp.stem}  dyn={n_dyn}")
    if not images:
        return ""
    return render_frame_grid(images, out_path, cols=3, labels=labels)


def write_final_mask_sample(
    frame_paths: list[Path],
    masks_dir: Path,
    out_path: Path,
    *,
    n_samples: int = 9,
    alpha: float = 0.45,
) -> str:
    """Render a 3x3 contact sheet showing the final exclusion mask (dynamic+sky+dilation).

    For each sampled frame, overlays the mask in red (alpha-blended) on the original
    image. Used to visually verify Stage 03 output before Stage 10 training.
    """
    if not frame_paths:
        return ""
    masks_dir = Path(masks_dir)
    picks = sample_evenly(list(frame_paths), n_samples)
    images: list[np.ndarray] = []
    labels: list[str] = []
    for fp in picks:
        img = cv2.imread(str(fp))
        if img is None:
            continue
        mask_path = masks_dir / f"{fp.stem}.png"
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE) if mask_path.exists() else None
        if mask is None or mask.shape[:2] != img.shape[:2]:
            images.append(img)
            labels.append(f"{fp.stem}  (no mask)")
            continue
        red_layer = np.zeros_like(img)
        red_layer[..., 2] = 255  # BGR red
        m_bool = mask > 127
        blended = img.copy()
        blended[m_bool] = cv2.addWeighted(img, 1 - alpha, red_layer, alpha, 0)[m_bool]
        images.append(blended)
        coverage = 100.0 * m_bool.mean()
        labels.append(f"{fp.stem}  excl={coverage:.1f}%")
    if not images:
        return ""
    return render_frame_grid(images, out_path, cols=3, labels=labels)
