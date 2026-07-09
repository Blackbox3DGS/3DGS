"""Frame-evidence signals for collision detection.

All signals are computed from what the video actually shows — NOT from the
reconstructed 3D trajectories (whose depth error can make normal traffic look
like a crash, e.g. the Waymo demo scene).

Frame indexing convention: everything is 0-based bbox_sequence frame index.
`shake_z[k]` compares frame files k-1 and k, i.e. it is aligned to the LATER
frame, so a spike at k means "the impact shows between k-1 and k".
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

# 전역 쉐이크: 다운스케일 그레이 프레임 diff를 4x4 블록으로 나눠 중앙값.
# 와이퍼/국소 움직임(일부 블록)은 중앙값에서 눌리고, 충격(전 블록 이동)만 남는다.
SHAKE_RESIZE = (192, 108)
SHAKE_GRID = 4


def shake_series(frame_paths: list) -> np.ndarray:
    """Robust global-motion z-score per frame (index-aligned to later frame).

    Returns array of length len(frame_paths); index 0 is 0 (no previous frame).
    """
    n = len(frame_paths)
    raw = np.zeros(n, dtype=np.float64)
    prev = None
    for k, p in enumerate(frame_paths):
        img = cv2.imread(str(p))
        if img is None:
            prev = None
            continue
        g = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), SHAKE_RESIZE).astype(np.float32)
        if prev is not None:
            d = np.abs(g - prev)
            h, w = d.shape
            bh, bw = h // SHAKE_GRID, w // SHAKE_GRID
            blocks = [
                d[i * bh:(i + 1) * bh, j * bw:(j + 1) * bw].mean()
                for i in range(SHAKE_GRID) for j in range(SHAKE_GRID)
            ]
            raw[k] = float(np.median(blocks))
        prev = g
    med = np.median(raw[1:]) if n > 1 else 0.0
    mad = np.median(np.abs(raw[1:] - med)) + 1e-9
    z = (raw - med) / (1.4826 * mad)
    z[0] = 0.0
    return z


def frame_size_from_bboxes(bbox_sequence: dict) -> tuple:
    """(W, H) upper bound from all bboxes (bbox_sequence has no metadata size)."""
    w = h = 1.0
    for t in bbox_sequence.get("tracks", {}).values():
        for fr in t.get("frames", {}).values():
            w = max(w, fr["bbox"][2])
            h = max(h, fr["bbox"][3])
    return w, h


def proximity_series(bbox_sequence: dict, n_frames: int) -> tuple:
    """Per-frame max bbox-area ratio over all tracks + which track it was.

    "A vehicle filling much of the frame" is the image-space signature of a
    vehicle close to the ego — the gate that separates real impacts from
    wiper/scene-cut shake spikes.
    """
    W, H = frame_size_from_bboxes(bbox_sequence)
    area = np.zeros(n_frames, dtype=np.float64)
    which = [None] * n_frames
    for tid, t in bbox_sequence.get("tracks", {}).items():
        if tid == "-1":
            continue
        for fs, fr in t.get("frames", {}).items():
            k = int(fs)
            if k >= n_frames:
                continue
            x1, y1, x2, y2 = fr["bbox"]
            a = max(0.0, (x2 - x1)) * max(0.0, (y2 - y1)) / (W * H)
            if a > area[k]:
                area[k] = a
                which[k] = tid
    return area, which


# ── 트랙 운동학 (목격 충돌용) ──────────────────────────────────────────────────

def track_centers(bbox_sequence: dict) -> dict:
    """track id -> {frame: (cx, cy, w, h)} for dynamic tracks."""
    out = {}
    meta = bbox_sequence.get("metadata", {})
    dyn = {str(t) for t in meta.get("dynamic_track_ids", [])}
    for tid, t in bbox_sequence.get("tracks", {}).items():
        if dyn and tid not in dyn:
            continue
        if not dyn and t.get("state") != "dynamic":
            continue
        fr = {}
        for fs, f in t.get("frames", {}).items():
            x1, y1, x2, y2 = f["bbox"]
            fr[int(fs)] = (0.5 * (x1 + x2), 0.5 * (y1 + y2), x2 - x1, y2 - y1)
        if len(fr) >= 5:
            out[tid] = fr
    return out


def bbox_iou(a: tuple, b: tuple) -> float:
    """IoU from (cx, cy, w, h) tuples."""
    ax1, ay1, ax2, ay2 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1, bx2, by2 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    ix = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    iy = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    return inter / (a[2] * a[3] + b[2] * b[3] - inter)


def speed_px(centers: dict, k: int, half: int = 2) -> float | None:
    """Smoothed bbox-centre speed (px/frame) at frame k."""
    a, b = None, None
    for d in range(half, 0, -1):
        if k - d in centers:
            a = (k - d, centers[k - d])
            break
    for d in range(half, 0, -1):
        if k + d in centers:
            b = (k + d, centers[k + d])
            break
    if a is None or b is None or b[0] <= a[0]:
        return None
    dx = b[1][0] - a[1][0]
    dy = b[1][1] - a[1][1]
    return float(np.hypot(dx, dy) / (b[0] - a[0]))
