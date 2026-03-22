import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Union


def extract_video_frames(
    video_path: Union[str, os.PathLike],
    out_dir: Union[str, os.PathLike],
    fps: int = 10,
    quality: int = 2,
    pattern: str = "frame_%06d.jpg",
) -> str:
    video_path = Path(video_path).expanduser().resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found in PATH.")

    out_pattern = str(out_dir / pattern)
    cmd = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps}",
        "-q:v",
        str(quality),
        out_pattern,
    ]
    subprocess.run(cmd, check=True)
    return str(out_dir)


def subsample_frames(
    in_dir: Union[str, os.PathLike],
    out_dir: Union[str, os.PathLike],
    every_n: int,
    ext: str = ".jpg",
) -> int:
    in_dir = Path(in_dir).expanduser().resolve()
    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = sorted([p for p in in_dir.iterdir() if p.suffix.lower() == ext])
    count = 0
    for i in range(0, len(frames), every_n):
        src = frames[i]
        dst = out_dir / src.name
        shutil.copy(src, dst)
        count += 1
    return count
