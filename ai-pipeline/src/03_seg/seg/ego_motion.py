"""Ego-motion compensation via dense optical flow on background pixels."""

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _build_background_mask(frame_detections, h, w):
    """Build a boolean mask where True = background (no detected objects)."""
    bg_mask = np.ones((h, w), dtype=bool)
    for det in frame_detections.detections:
        x1, y1, x2, y2 = det.bbox
        crop_h, crop_w = det.mask_crop.shape
        # Ensure crop fits within bounds
        actual_h = min(crop_h, y2 - y1, h - y1)
        actual_w = min(crop_w, x2 - x1, w - x1)
        bg_mask[y1 : y1 + actual_h, x1 : x1 + actual_w] &= ~det.mask_crop[
            :actual_h, :actual_w
        ]
    return bg_mask


def compute_ego_flow(frame_paths, all_frame_detections):
    """Compute per-frame ego-motion as median optical flow of background pixels.

    Returns list of length len(frame_paths).
    Index 0 is None (no previous frame).
    Each subsequent entry is np.ndarray of shape (2,) representing (dx, dy).
    """
    ego_flows = [None]

    prev_gray = cv2.imread(str(frame_paths[0]), cv2.IMREAD_GRAYSCALE)
    if prev_gray is None:
        logger.error("Failed to read first frame: %s", frame_paths[0])
        return [None] * len(frame_paths)

    for i in range(1, len(frame_paths)):
        curr_gray = cv2.imread(str(frame_paths[i]), cv2.IMREAD_GRAYSCALE)
        if curr_gray is None:
            logger.warning("Failed to read frame %d: %s", i, frame_paths[i])
            ego_flows.append(None)
            continue

        h, w = curr_gray.shape

        # Compute dense optical flow
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray,
            curr_gray,
            None,
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0,
        )

        # Use previous frame's detections to mask out dynamic objects
        bg_mask = _build_background_mask(all_frame_detections[i - 1], h, w)

        bg_pixels = bg_mask.ravel()
        flow_x = flow[:, :, 0].ravel()[bg_pixels]
        flow_y = flow[:, :, 1].ravel()[bg_pixels]

        if len(flow_x) < 100:
            # Too few background pixels — fallback to full-image median
            logger.warning(
                "Frame %d: only %d background pixels, using full-image flow",
                i,
                len(flow_x),
            )
            flow_x = flow[:, :, 0].ravel()
            flow_y = flow[:, :, 1].ravel()

        ego_dx = float(np.median(flow_x))
        ego_dy = float(np.median(flow_y))
        ego_flows.append(np.array([ego_dx, ego_dy]))

        prev_gray = curr_gray

        if (i + 1) % 50 == 0 or i == len(frame_paths) - 1:
            logger.info("Ego-motion progress: %d/%d frames", i + 1, len(frame_paths))

    return ego_flows


def compute_object_motion(detection, prev_detection, ego_flow):
    """Compute ego-compensated motion magnitude for a single detection.

    Returns 0.0 if prev_detection or ego_flow is None.
    Motion = |centroid_displacement - ego_flow| (Euclidean norm in pixels).
    """
    if prev_detection is None or ego_flow is None:
        return 0.0

    dx = detection.centroid[0] - prev_detection.centroid[0]
    dy = detection.centroid[1] - prev_detection.centroid[1]

    compensated_dx = dx - ego_flow[0]
    compensated_dy = dy - ego_flow[1]

    return float(np.sqrt(compensated_dx**2 + compensated_dy**2))
