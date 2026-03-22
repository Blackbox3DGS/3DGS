import os
import sys
from pathlib import Path
from typing import Optional, Union


def _setup_waymo_import(repo_root: Optional[Path] = None) -> Path:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]
    waymo_src = repo_root / "third_party" / "waymo-open-dataset" / "src"
    if not waymo_src.exists():
        raise FileNotFoundError(
            f"Waymo repo not found at {waymo_src}. "
            "Clone it into ai-pipeline/third_party/waymo-open-dataset."
        )
    sys.path.insert(0, str(waymo_src))
    return waymo_src


def extract_waymo_front_frames(
    tfrecord_path: Union[str, os.PathLike],
    out_dir: Optional[Union[str, os.PathLike]] = None,
    every_n: int = 1,
    max_frames: Optional[int] = None,
) -> dict:
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

    _setup_waymo_import()

    import tensorflow as tf
    from waymo_open_dataset import dataset_pb2 as open_dataset

    tfrecord_path = Path(tfrecord_path).expanduser().resolve()
    if not tfrecord_path.exists():
        raise FileNotFoundError(f"TFRecord not found: {tfrecord_path}")

    dataset = tf.data.TFRecordDataset(str(tfrecord_path), compression_type="")
    iterator = iter(dataset)

    try:
        first = next(iterator)
    except StopIteration as exc:
        raise RuntimeError("TFRecord is empty.") from exc

    first_frame = open_dataset.Frame()
    first_frame.ParseFromString(bytearray(first.numpy()))
    scene_name = first_frame.context.name or tfrecord_path.stem

    if out_dir is None:
        repo_root = Path(__file__).resolve().parents[3]
        out_dir = (
            repo_root
            / "data"
            / "waymo"
            / scene_name
            / "images_colmap"
        )
    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    def should_extract(index: int) -> bool:
        if index % every_n != 0:
            return False
        if max_frames is not None and index >= max_frames:
            return False
        return True

    def extract_frame(frame, index: int) -> bool:
        if not should_extract(index):
            return False
        for image in frame.images:
            if image.name == open_dataset.CameraName.FRONT:
                ts = frame.timestamp_micros
                out_name = f"frame_{index:06d}_{ts}.jpg"
                out_path = out_dir / out_name
                with open(out_path, "wb") as f:
                    f.write(image.image)
                return True
        return False

    extracted = 0
    total = 0

    if extract_frame(first_frame, 0):
        extracted += 1
    total += 1

    for idx, data in enumerate(iterator, start=1):
        frame = open_dataset.Frame()
        frame.ParseFromString(bytearray(data.numpy()))
        if extract_frame(frame, idx):
            extracted += 1
        total += 1
        if max_frames is not None and idx >= max_frames:
            break

    return {
        "scene_name": scene_name,
        "total_frames": total,
        "extracted_frames": extracted,
        "out_dir": str(out_dir),
    }
