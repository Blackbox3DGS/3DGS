"""Stage 03c — frame-evidence collision detection & ego role classification.

Consumes Stage-02 frames + Stage-03 bbox_sequence.json; produces
`collision.json` ({collision, ego_role, series}). Runs on CPU in seconds —
no LingBot / 3D reconstruction needed, so it works in the upload service
before (or without) the GPU stage.

See `detect.py` for the detection rationale.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .detect import detect

logger = logging.getLogger(__name__)


def run_detection(
    images_dir: str | Path,
    bbox_sequence_path: str | Path,
    out_path: str | Path,
    fps: float = 10.0,
) -> dict:
    frame_paths = sorted(Path(images_dir).glob("*.jpg"))
    if not frame_paths:
        raise ValueError(f"No frames in {images_dir}")
    with open(bbox_sequence_path) as f:
        bbox_sequence = json.load(f)

    result = detect(bbox_sequence, frame_paths, fps=fps)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f)

    col = result["collision"]
    if col:
        logger.info("Collision: frame %d (t=%.1fs) type=%s conf=%.2f tracks=%s",
                    col["frame_idx"], col["time_s"], col["type"],
                    col["confidence"], col["track_ids"])
    else:
        logger.info("No collision detected (ego_role=none).")
    return result


def run(context: dict) -> dict:
    """Pipeline stage entry — after 03_seg."""
    artifacts = context["artifacts"]
    out_root = Path(context["out_root"])
    out_path = out_root / "03c_collision" / "collision.json"

    run_detection(
        artifacts["images_colmap"],
        artifacts["bbox_sequence"],
        out_path,
    )
    artifacts["collision"] = str(out_path)
    return context
