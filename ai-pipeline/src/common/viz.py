"""Shared visualisation helpers used by multiple pipeline stages.

All functions render to PNG via OpenCV only — no matplotlib dependency.
"""

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def render_pointcloud_topdown(
    points: np.ndarray,
    camera_xyz: np.ndarray | None,
    out_path: Path,
    *,
    colors: np.ndarray | None = None,
    title: str = "Point cloud (top-down X-Z)",
    canvas_size: int = 1024,
    margin: int = 80,
    max_points: int = 200_000,
    point_radius: int = 1,
) -> str:
    """Render a top-down (X–Z plane) scatter plot of a point cloud.

    Parameters
    ----------
    points     : (N, 3) world-frame point cloud.
    camera_xyz : (M, 3) camera centres, drawn on top of the scatter as a
                 black polyline. May be None.
    colors     : (N, 3) RGB uint8 or float in [0,1]. If None, points are dark grey.
    max_points : random subsample to at most this many points to keep render fast.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pts = np.asarray(points, dtype=np.float64)
    if pts.size == 0:
        canvas = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
        cv2.putText(canvas, "empty point cloud", (40, canvas_size // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        cv2.imwrite(str(out_path), canvas)
        return str(out_path)

    if len(pts) > max_points:
        rng = np.random.default_rng(0)
        sel = rng.choice(len(pts), size=max_points, replace=False)
        pts = pts[sel]
        if colors is not None:
            colors = np.asarray(colors)[sel]

    cam_xz = (
        np.asarray(camera_xyz, dtype=np.float64)[:, [0, 2]]
        if camera_xyz is not None and len(camera_xyz)
        else np.zeros((0, 2))
    )
    pts_xz = pts[:, [0, 2]]

    # Robust extent — clip to 1st/99th percentiles so a few outliers don't
    # squash the useful structure.
    pct_low = np.percentile(pts_xz, 1, axis=0)
    pct_high = np.percentile(pts_xz, 99, axis=0)
    if len(cam_xz):
        pct_low = np.minimum(pct_low, cam_xz.min(axis=0))
        pct_high = np.maximum(pct_high, cam_xz.max(axis=0))

    x_min, z_min = pct_low
    x_max, z_max = pct_high
    extent_x = max(x_max - x_min, 1.0)
    extent_z = max(z_max - z_min, 1.0)
    extent = max(extent_x, extent_z)
    drawable = canvas_size - 2 * margin
    scale = drawable / extent

    cx_off = margin + (drawable - extent_x * scale) * 0.5
    cz_off = margin + (drawable - extent_z * scale) * 0.5

    def to_canvas(x: float, z: float) -> tuple[int, int]:
        u = int(round(cx_off + (x - x_min) * scale))
        v = int(round(canvas_size - (cz_off + (z - z_min) * scale)))
        return u, v

    canvas = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)

    # Frame border
    cv2.rectangle(canvas, (margin, margin),
                  (canvas_size - margin, canvas_size - margin),
                  (200, 200, 200), 1)

    # Scatter points (clip stragglers outside extent so cv2 doesn't fail)
    pix = np.empty((len(pts_xz), 2), dtype=np.int32)
    pix[:, 0] = np.round(cx_off + (pts_xz[:, 0] - x_min) * scale).astype(np.int32)
    pix[:, 1] = np.round(canvas_size - (cz_off + (pts_xz[:, 1] - z_min) * scale)).astype(np.int32)
    in_bounds = (
        (pix[:, 0] >= margin) & (pix[:, 0] < canvas_size - margin) &
        (pix[:, 1] >= margin) & (pix[:, 1] < canvas_size - margin)
    )
    pix = pix[in_bounds]

    if colors is not None:
        col_arr = np.asarray(colors)[in_bounds]
        if col_arr.dtype != np.uint8:
            col_arr = np.clip(col_arr * 255, 0, 255).astype(np.uint8)
        # RGB -> BGR for OpenCV
        col_bgr = col_arr[:, [2, 1, 0]]
        if point_radius <= 1:
            for (u, v), c in zip(pix, col_bgr):
                canvas[v, u] = c
        else:
            for (u, v), c in zip(pix, col_bgr):
                cv2.circle(canvas, (int(u), int(v)), point_radius,
                           (int(c[0]), int(c[1]), int(c[2])), -1)
    else:
        col = (90, 90, 90)
        if point_radius <= 1:
            for u, v in pix:
                canvas[v, u] = col
        else:
            for u, v in pix:
                cv2.circle(canvas, (int(u), int(v)), point_radius, col, -1)

    # Camera path on top
    if len(cam_xz) >= 2:
        cam_pts = np.array([to_canvas(p[0], p[1]) for p in cam_xz], dtype=np.int32)
        cv2.polylines(canvas, [cam_pts], isClosed=False, color=(0, 0, 220),
                      thickness=2, lineType=cv2.LINE_AA)
        cv2.circle(canvas, tuple(cam_pts[0]), 6, (0, 0, 220), -1)

    # Title
    cv2.putText(canvas, f"{title}  N={len(pts)}  extent: {extent_x:.1f} x {extent_z:.1f} m",
                (margin, margin - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (60, 60, 60), 1, cv2.LINE_AA)

    # 10 m scale bar bottom-left
    bar_m = 10.0
    bar_px = int(round(bar_m * scale))
    bar_y = canvas_size - margin // 2
    bar_x1 = margin
    bar_x2 = bar_x1 + bar_px
    cv2.line(canvas, (bar_x1, bar_y), (bar_x2, bar_y), (0, 0, 0), 2)
    cv2.line(canvas, (bar_x1, bar_y - 5), (bar_x1, bar_y + 5), (0, 0, 0), 2)
    cv2.line(canvas, (bar_x2, bar_y - 5), (bar_x2, bar_y + 5), (0, 0, 0), 2)
    cv2.putText(canvas, f"{int(bar_m)} m",
                (bar_x1 + bar_px // 2 - 14, bar_y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

    # Axes
    cv2.putText(canvas, "+X ->", (canvas_size - margin - 60, canvas_size - margin + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 80, 80), 1, cv2.LINE_AA)
    cv2.putText(canvas, "+Z", (margin - 35, margin + 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 80, 80), 1, cv2.LINE_AA)

    cv2.imwrite(str(out_path), canvas)
    logger.info("Wrote top-down PC plot: %s (%d points)", out_path, len(pts))
    return str(out_path)


def render_frame_grid(
    images: list[np.ndarray],
    out_path: Path,
    *,
    cols: int = 3,
    cell_height: int = 240,
    pad: int = 4,
    labels: list[str] | None = None,
) -> str:
    """Render a contact-sheet grid of frame images.

    Each input image is BGR (OpenCV). Frames are letterboxed into uniform
    cells preserving aspect ratio. Optional per-cell label text.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not images:
        canvas = np.full((cell_height, cell_height * cols, 3), 255, dtype=np.uint8)
        cv2.putText(canvas, "no frames", (40, cell_height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        cv2.imwrite(str(out_path), canvas)
        return str(out_path)

    # Pick uniform cell size from the first image's aspect.
    h0, w0 = images[0].shape[:2]
    aspect = w0 / h0
    cell_w = int(round(cell_height * aspect))

    n = len(images)
    rows = (n + cols - 1) // cols

    grid_w = cols * cell_w + (cols + 1) * pad
    grid_h = rows * cell_height + (rows + 1) * pad
    canvas = np.full((grid_h, grid_w, 3), 240, dtype=np.uint8)

    for i, img in enumerate(images):
        r = i // cols
        c = i % cols
        x0 = pad + c * (cell_w + pad)
        y0 = pad + r * (cell_height + pad)

        h, w = img.shape[:2]
        s = min(cell_w / w, cell_height / h)
        new_w, new_h = int(round(w * s)), int(round(h * s))
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        ox = x0 + (cell_w - new_w) // 2
        oy = y0 + (cell_height - new_h) // 2
        canvas[oy : oy + new_h, ox : ox + new_w] = resized

        if labels is not None and i < len(labels):
            cv2.putText(canvas, labels[i], (x0 + 6, y0 + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)
            cv2.putText(canvas, labels[i], (x0 + 6, y0 + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    cv2.imwrite(str(out_path), canvas)
    logger.info("Wrote frame grid: %s (%d frames)", out_path, n)
    return str(out_path)


def sample_evenly(seq: list, n: int) -> list:
    """Pick n evenly spaced items from seq (deterministic)."""
    if len(seq) <= n:
        return list(seq)
    idx = np.linspace(0, len(seq) - 1, n).round().astype(int)
    return [seq[int(i)] for i in idx]
