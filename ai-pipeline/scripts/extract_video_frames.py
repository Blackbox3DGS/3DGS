#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path


def _add_src_to_path():
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src" / "02_ingest"
    sys.path.insert(0, str(src_path))


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Extract frames from a video using ffmpeg (COLMAP용)."
    )
    parser.add_argument(
        "--video",
        required=True,
        help="Path to input video (.mp4/.avi)",
    )
    parser.add_argument(
        "--out_dir",
        default=None,
        help="Output directory for extracted JPGs (default: ai-pipeline/data/videos/<name>/images_colmap)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=10,
        help="Frames per second to extract (default: 10)",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=2,
        help="ffmpeg -q:v quality (lower is higher quality, default: 2)",
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    _add_src_to_path()

    from ingest.video import extract_video_frames

    video_path = Path(args.video).expanduser().resolve()
    if args.out_dir is None:
        repo_root = Path(__file__).resolve().parents[1]
        out_dir = (
            repo_root
            / "data"
            / "videos"
            / video_path.stem
            / "images_colmap"
        )
    else:
        out_dir = Path(args.out_dir).expanduser().resolve()

    extract_video_frames(
        video_path=video_path,
        out_dir=out_dir,
        fps=args.fps,
        quality=args.quality,
    )

    print(f"Extracted frames to: {out_dir}")


if __name__ == "__main__":
    main()
