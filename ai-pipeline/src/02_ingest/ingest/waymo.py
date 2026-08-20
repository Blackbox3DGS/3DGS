import json
import os
from pathlib import Path
from typing import Optional, Union


def extract_waymo_front_frames(
    tfrecord_path: Union[str, os.PathLike],
    out_dir: Optional[Union[str, os.PathLike]] = None,
    every_n: int = 1,
    max_frames: Optional[int] = None,
) -> dict:
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

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

    # Extract FRONT camera intrinsics from calibration
    waymo_intrinsics = None
    for cal in first_frame.context.camera_calibrations:
        if cal.name == open_dataset.CameraName.FRONT:
            intrinsic = list(cal.intrinsic)  # [f_u, f_v, c_u, c_v, k1, k2, p1, p2, k3]
            waymo_intrinsics = {
                "fx": intrinsic[0], "fy": intrinsic[1],
                "cx": intrinsic[2], "cy": intrinsic[3],
                "k1": intrinsic[4], "k2": intrinsic[5],
                "p1": intrinsic[6], "p2": intrinsic[7],
                "k3": intrinsic[8] if len(intrinsic) > 8 else 0.0,
                "width": cal.width, "height": cal.height,
            }
            break

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

    result = {
        "scene_name": scene_name,
        "total_frames": total,
        "extracted_frames": extracted,
        "out_dir": str(out_dir),
    }

    if waymo_intrinsics:
        intrinsics_path = out_dir.parent / "intrinsics_waymo.json"
        with open(intrinsics_path, "w") as f:
            json.dump(waymo_intrinsics, f, indent=2)
        result["waymo_intrinsics"] = waymo_intrinsics

    return result
