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
        description="Extract FRONT camera frames from a Waymo TFRecord."
    )
    parser.add_argument(
        "--tfrecord",
        required=True,
        help="Path to the Waymo .tfrecord file",
    )
    parser.add_argument(
        "--out_dir",
        default=None,
        help="Output directory for extracted JPGs (default: ai-pipeline/data/waymo/<scene>/images_colmap)",
    )
    parser.add_argument(
        "--every_n",
        type=int,
        default=1,
        help="Keep every Nth frame (Waymo is 10Hz, so 1 = 10fps).",
    )
    parser.add_argument(
        "--max_frames",
        type=int,
        default=None,
        help="Optional cap on number of frames to extract.",
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    _add_src_to_path()

    from ingest.waymo import extract_waymo_front_frames

    result = extract_waymo_front_frames(
        tfrecord_path=args.tfrecord,
        out_dir=args.out_dir,
        every_n=args.every_n,
        max_frames=args.max_frames,
    )

    print(f"Scene: {result['scene_name']}")
    print(f"Total frames scanned: {result['total_frames']}")
    print(f"Extracted FRONT frames: {result['extracted_frames']}")
    print(f"Output dir: {result['out_dir']}")


if __name__ == "__main__":
    main()
