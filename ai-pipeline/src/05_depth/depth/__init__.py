"""Stage 05: Monocular Depth Estimation via Depth Anything V2.

Runs Depth Anything V2 (Small) on the original extracted frames to produce
per-frame relative depth maps (0-1).  This stage reads images_colmap
(original frames without masks) and is independent of Stage 04 (COLMAP),
so they can run in parallel.
"""

import logging
from pathlib import Path

import torch

from .estimate import estimate_depth_batch

logger = logging.getLogger(__name__)


def run(context):
    """Stage 05 entry point.

    Reads:
        context["artifacts"]["images_colmap"] — directory of original .jpg frames

    Writes:
        context["artifacts"]["depth_maps"] — directory of .npy depth maps (float32, H×W, 0-1)
    """
    images_dir = Path(context["artifacts"]["images_colmap"])
    out_root = Path(context["out_root"])
    workspace = out_root / "05_depth"
    depth_dir = workspace / "depth_maps"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    total_frames = len(list(images_dir.glob("*.jpg")))
    logger.info(
        "Stage 05 starting: %d frames from %s (device=%s)",
        total_frames, images_dir, device,
    )

    vis_dir = workspace / "depth_vis"
    count = estimate_depth_batch(images_dir, depth_dir, device, vis_dir=vis_dir)

    context["artifacts"]["depth_maps"] = str(depth_dir)
    context["artifacts"]["depth_vis"] = str(vis_dir)

    logger.info(
        "Stage 05 complete: %d depth maps -> %s, vis -> %s",
        count, depth_dir, vis_dir,
    )
    return context
