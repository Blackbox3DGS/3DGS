import logging
from pathlib import Path

from .video import extract_video_frames, subsample_frames
from .waymo import extract_waymo_front_frames

logger = logging.getLogger(__name__)

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

    if input_type == "waymo":
        logger.info("Extracting Waymo front camera frames from %s", input_path.name)
        result = extract_waymo_front_frames(
            tfrecord_path=input_path,
            out_dir=out_dir,
            every_n=1,
        )
        context["artifacts"]["images_colmap"] = result["out_dir"]
        context["artifacts"]["scene_name"] = result["scene_name"]
        logger.info(
            "Waymo extraction complete: %d frames -> %s",
            result["extracted_frames"],
            result["out_dir"],
        )
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
        return context

    raise ValueError(f"Unknown input_type: {input_type}")
