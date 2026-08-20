"""Dynamic/static classification with state back-propagation."""

import logging
from collections import defaultdict

from .ego_motion import compute_object_motion

logger = logging.getLogger(__name__)


def classify_tracks(all_frame_detections, ego_flows, motion_threshold_px=3.0):
    """Classify each track_id as 'dynamic' or 'static'.

    State back-propagation: if ANY frame of a track shows ego-compensated
    motion > threshold, the ENTIRE track is forced to 'dynamic'.

    Untracked detections (track_id == -1) are conservatively treated as dynamic.

    Returns dict mapping track_id -> 'dynamic' | 'static'.
    """
    # Build per-track history: {track_id: [(frame_idx, Detection), ...]}
    track_history = defaultdict(list)
    for fd in all_frame_detections:
        for det in fd.detections:
            if det.track_id == -1:
                continue
            track_history[det.track_id].append((fd.frame_idx, det))

    track_states = {}

    for track_id, history in track_history.items():
        # Sort by frame index
        history.sort(key=lambda x: x[0])

        is_dynamic = False
        for j in range(1, len(history)):
            prev_frame_idx, prev_det = history[j - 1]
            curr_frame_idx, curr_det = history[j]

            # Only compute motion for consecutive or near-consecutive frames
            frame_gap = curr_frame_idx - prev_frame_idx
            if frame_gap > 5:
                continue

            ego_flow = ego_flows[curr_frame_idx] if curr_frame_idx < len(ego_flows) else None
            motion = compute_object_motion(curr_det, prev_det, ego_flow)

            # Normalize by frame gap for non-consecutive frames
            if frame_gap > 1:
                motion = motion / frame_gap

            if motion > motion_threshold_px:
                is_dynamic = True
                break  # State back-propagation: one frame is enough

        track_states[track_id] = "dynamic" if is_dynamic else "static"

    dynamic_count = sum(1 for s in track_states.values() if s == "dynamic")
    static_count = sum(1 for s in track_states.values() if s == "static")
    logger.info(
        "Track classification: %d dynamic, %d static (threshold=%.1f px)",
        dynamic_count,
        static_count,
        motion_threshold_px,
    )

    return track_states
