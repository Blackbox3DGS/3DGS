"""Binary mask PNG generation and bbox_sequence JSON export."""

import json
import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def write_masks(frame_paths, all_frame_detections, track_states, out_dir):
    """Write per-frame binary masks as PNG files.

    For each frame, creates a black image and paints dynamic-track masks white.
    Untracked detections (track_id == -1) are conservatively painted as dynamic.

    Returns str path to out_dir.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for fd in all_frame_detections:
        h, w = fd.height, fd.width
        if h == 0 or w == 0:
            continue

        mask_img = np.zeros((h, w), dtype=np.uint8)

        for det in fd.detections:
            # Determine if this detection should be masked
            if det.track_id == -1:
                is_dynamic = True  # conservative: untracked → dynamic
            else:
                is_dynamic = track_states.get(det.track_id, "static") == "dynamic"

            if not is_dynamic:
                continue

            x1, y1, x2, y2 = det.bbox
            crop_h, crop_w = det.mask_crop.shape
            actual_h = min(crop_h, y2 - y1, h - y1)
            actual_w = min(crop_w, x2 - x1, w - x1)

            # Paint cropped mask onto full image
            mask_region = det.mask_crop[:actual_h, :actual_w]
            mask_img[y1 : y1 + actual_h, x1 : x1 + actual_w][mask_region] = 255

        # Save with same stem as input frame
        stem = Path(fd.frame_name).stem
        out_path = out_dir / f"{stem}.png"
        cv2.imwrite(str(out_path), mask_img)

    logger.info("Masks written: %d files -> %s", len(all_frame_detections), out_dir)
    return str(out_dir)


def write_bbox_sequence(all_frame_detections, track_states, out_path):
    """Write bbox_sequence.json with tracking and state information.

    Returns str path to the JSON file.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build tracks dict
    tracks = {}
    for fd in all_frame_detections:
        for det in fd.detections:
            tid = str(det.track_id)
            if tid not in tracks:
                tracks[tid] = {
                    "class_name": det.class_name,
                    "state": (
                        track_states.get(det.track_id, "dynamic")
                        if det.track_id != -1
                        else "dynamic"
                    ),
                    "frames": {},
                }
            tracks[tid]["frames"][str(fd.frame_idx)] = {
                "bbox": [int(v) for v in det.bbox],
                "confidence": round(float(det.confidence), 4),
            }

    # Metadata
    all_track_ids = [
        int(tid) for tid in tracks.keys() if tid != "-1"
    ]
    dynamic_ids = [tid for tid in all_track_ids if track_states.get(tid) == "dynamic"]
    static_ids = [tid for tid in all_track_ids if track_states.get(tid) == "static"]

    data = {
        "metadata": {
            "num_frames": len(all_frame_detections),
            "num_tracks": len(all_track_ids),
            "dynamic_track_ids": sorted(dynamic_ids),
            "static_track_ids": sorted(static_ids),
        },
        "tracks": tracks,
    }

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    logger.info("Bbox sequence written: %d tracks -> %s", len(tracks), out_path)
    return str(out_path)
