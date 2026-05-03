import logging
from pathlib import Path

import cv2

from common.viz import render_frame_grid, sample_evenly

from .video import extract_video_frames, subsample_frames
from .waymo import extract_waymo_front_frames

logger = logging.getLogger(__name__)


def _write_sample_grid(out_dir: Path, vis_path: Path, n: int = 9) -> None:
    """Save a contact-sheet PNG of n evenly-spaced extracted frames."""
    frame_paths = sorted(Path(out_dir).glob("*.jpg"))
    if not frame_paths:
        return
    picks = sample_evenly(frame_paths, n)
    images = []
    labels = []
    for p in picks:
        img = cv2.imread(str(p))
        if img is None:
            continue
        images.append(img)
        labels.append(p.stem)
    if images:
        render_frame_grid(images, vis_path, cols=3, labels=labels)

__all__ = [
    "extract_video_frames",
    "subsample_frames",
    "extract_waymo_front_frames",
    "run",
]


def run(context):
    input_path = Path(context["input_path"])
    input_type = context["input_type"]
    out_root = Path(context["out_root"])

    out_dir = out_root / "02_ingest" / "images_colmap"
    out_dir.mkdir(parents=True, exist_ok=True)
    vis_path = out_root / "02_ingest" / "sample_grid.png"

    if input_type == "waymo":
        logger.info("Extracting Waymo front camera frames from %s", input_path.name)
        result = extract_waymo_front_frames(
            tfrecord_path=input_path,
            out_dir=out_dir,
            every_n=1,
        )
        context["artifacts"]["images_colmap"] = result["out_dir"]
        context["artifacts"]["scene_name"] = result["scene_name"]
        if "waymo_intrinsics" in result:
            context["artifacts"]["waymo_intrinsics"] = result["waymo_intrinsics"]
            logger.info(
                "Waymo intrinsics: fx=%.1f fy=%.1f cx=%.1f cy=%.1f",
                result["waymo_intrinsics"]["fx"],
                result["waymo_intrinsics"]["fy"],
                result["waymo_intrinsics"]["cx"],
                result["waymo_intrinsics"]["cy"],
            )
        logger.info(
            "Waymo extraction complete: %d frames -> %s",
            result["extracted_frames"],
            result["out_dir"],
        )
        _write_sample_grid(Path(result["out_dir"]), vis_path)
        context["artifacts"]["ingest_vis"] = str(vis_path)
        return context

    if input_type == "video":
        logger.info("Extracting video frames at 10fps from %s", input_path.name)
        extract_video_frames(
            video_path=input_path,
            out_dir=out_dir,
            fps=10,
            quality=2,
        )
        frame_count = len(list(out_dir.glob("*.jpg")))
        context["artifacts"]["images_colmap"] = str(out_dir)
        logger.info("Video extraction complete: %d frames -> %s", frame_count, out_dir)
        _write_sample_grid(out_dir, vis_path)
        context["artifacts"]["ingest_vis"] = str(vis_path)
        return context

    raise ValueError(f"Unknown input_type: {input_type}")
