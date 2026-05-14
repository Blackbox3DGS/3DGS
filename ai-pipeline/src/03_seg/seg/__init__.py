"""Stage 03: Instance Segmentation & Multi-Object Tracking.

Detects dynamic objects (vehicles, pedestrians) using YOLOv8-seg,
tracks them with ByteTrack, compensates for ego-motion, and classifies
each track as dynamic or static via state back-propagation.

Stage 3.5 (user target selection) is deferred — defaults to all dynamic objects.
"""

import logging
import os
from pathlib import Path

from .classify import classify_tracks
from .detect import run_tracking
from .ego_motion import compute_ego_flow
from .mask_writer import write_bbox_sequence, write_masks
from .semantic import run_semantic_masks
from .visualizer import write_final_mask_sample, write_seg_overlay_sample

logger = logging.getLogger(__name__)


def run(context):
    """Stage 03 entry point.

    Reads:
        context["artifacts"]["images_colmap"] — directory of .jpg frames

    Writes:
        context["artifacts"]["segmentation_masks"] — directory of binary .png masks
            (white = dynamic objects + sky/far-background; excluded from 3DGS loss)
        context["artifacts"]["sky_masks"] — directory of per-frame sky-only PNGs (QA)
        context["artifacts"]["bbox_sequence"] — path to bbox_sequence.json
        context["artifacts"]["target_ids"] — "all_dynamic" (Stage 3.5 deferred)
        context["artifacts"]["seg_overlay_sample"] — dynamic-detection contact sheet
        context["artifacts"]["final_mask_sample"] — final combined-mask contact sheet
    """
    images_dir = Path(context["artifacts"]["images_colmap"])
    out_root = Path(context["out_root"])
    seg_dir = out_root / "03_seg"
    masks_dir = seg_dir / "masks"
    sky_dir = seg_dir / "sky_masks"

    # Collect and sort input frames
    frame_paths = sorted(images_dir.glob("*.jpg"))
    if not frame_paths:
        raise ValueError(f"No .jpg frames found in {images_dir}")

    logger.info("Stage 03 starting: %d frames from %s", len(frame_paths), images_dir)

    # 1. Detection & tracking
    logger.info("Step 1/5: Running YOLOv8-seg + ByteTrack...")
    all_detections = run_tracking(frame_paths)

    # 2. Ego-motion compensation
    logger.info("Step 2/5: Computing ego-motion via optical flow...")
    ego_flows = compute_ego_flow(frame_paths, all_detections)

    # 3. Dynamic/static classification with state back-propagation
    logger.info("Step 3/5: Classifying tracks (dynamic/static)...")
    track_states = classify_tracks(all_detections, ego_flows)

    # 4. Semantic sky / far-background segmentation (SegFormer ADE20K)
    logger.info("Step 4/5: Semantic sky segmentation (SegFormer)...")
    sky_masks = run_semantic_masks(frame_paths, sky_dir)

    # 5. Write outputs (dynamic ∪ sky, dilated)
    dilate_kernel = int(os.getenv("MASK_DILATE_KERNEL", "5"))
    logger.info("Step 5/5: Writing masks (dilate=%d) and bbox sequence...", dilate_kernel)
    masks_path = write_masks(
        frame_paths,
        all_detections,
        track_states,
        masks_dir,
        sky_masks=sky_masks,
        dilate_kernel=dilate_kernel,
    )
    bbox_path = write_bbox_sequence(
        all_detections, track_states, seg_dir / "bbox_sequence.json"
    )

    # Sample overlay grids for visual inspection
    overlay_path = seg_dir / "seg_overlay_sample.png"
    write_seg_overlay_sample(frame_paths, all_detections, track_states, overlay_path)
    final_mask_path = seg_dir / "final_mask_sample.png"
    write_final_mask_sample(frame_paths, masks_dir, final_mask_path)

    # Set artifacts
    context["artifacts"]["segmentation_masks"] = masks_path
    context["artifacts"]["sky_masks"] = str(sky_dir)
    context["artifacts"]["bbox_sequence"] = bbox_path
    context["artifacts"]["target_ids"] = "all_dynamic"
    context["artifacts"]["seg_overlay_sample"] = str(overlay_path)
    context["artifacts"]["final_mask_sample"] = str(final_mask_path)

    logger.info(
        "Stage 03 complete: masks -> %s, bbox -> %s, overlay -> %s, final -> %s",
        masks_path, bbox_path, overlay_path, final_mask_path,
    )
    return context
