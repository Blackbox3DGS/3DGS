"""Extract ground-truth poses / 3D boxes / speeds from a Waymo TFRecord.

Produces a single `gt.json` consumed by the (numpy-only) evaluation steps, so
TensorFlow + waymo-open-dataset are needed only for this one-shot extraction
(run it inside the pipeline Docker image or on the GPU server — the local mac
cannot install them).

Per frame we keep:
  * `timestamp_micros`         — for index<->image-filename verification
  * `pose`                     — 4x4 vehicle->global
  * `labels`                   — LiDAR 3D boxes in the *vehicle* frame:
                                 center/size/heading + `metadata.speed_x/y`
                                 (GT object speed in m/s, global frame)
  * `projected_boxes`          — the same labels projected into the FRONT
                                 camera as 2D [x1,y1,x2,y2] boxes (used to
                                 associate our YOLO/ByteTrack track ids with
                                 GT object ids)

Scene-constant data (FRONT camera extrinsic camera->vehicle + intrinsics) is
stored once at the top level.

Follows the TFRecord iteration pattern of
`02_ingest/ingest/waymo.py:extract_waymo_front_frames`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Union


def extract_waymo_gt(
    tfrecord_path: Union[str, os.PathLike],
    out_path: Union[str, os.PathLike],
    every_n: int = 1,
    max_frames: Optional[int] = None,
) -> dict:
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

    import tensorflow as tf
    from waymo_open_dataset import dataset_pb2 as open_dataset
    from waymo_open_dataset import label_pb2

    tfrecord_path = Path(tfrecord_path).expanduser().resolve()
    if not tfrecord_path.exists():
        raise FileNotFoundError(f"TFRecord not found: {tfrecord_path}")

    type_names = {v: k.replace("TYPE_", "") for k, v in label_pb2.Label.Type.items()}
    front = open_dataset.CameraName.FRONT

    def _mat4(values) -> list:
        v = list(values)
        return [v[0:4], v[4:8], v[8:12], v[12:16]]

    frames_out = []
    scene_name = None
    camera_extrinsic = None
    camera_intrinsic = None

    dataset = tf.data.TFRecordDataset(str(tfrecord_path), compression_type="")
    for idx, data in enumerate(dataset):
        if max_frames is not None and idx >= max_frames:
            break
        if idx % every_n != 0:
            continue

        frame = open_dataset.Frame()
        frame.ParseFromString(bytearray(data.numpy()))

        if scene_name is None:
            scene_name = frame.context.name or tfrecord_path.stem
            for cal in frame.context.camera_calibrations:
                if cal.name == front:
                    camera_extrinsic = _mat4(cal.extrinsic.transform)
                    intr = list(cal.intrinsic)
                    camera_intrinsic = {
                        "fx": intr[0], "fy": intr[1], "cx": intr[2], "cy": intr[3],
                        "width": cal.width, "height": cal.height,
                    }
                    break

        labels = []
        for lab in frame.laser_labels:
            box = lab.box
            labels.append({
                "id": lab.id,
                "type": type_names.get(lab.type, str(lab.type)),
                "center": [box.center_x, box.center_y, box.center_z],
                "size": [box.length, box.width, box.height],
                "heading": box.heading,
                "speed": [lab.metadata.speed_x, lab.metadata.speed_y],
            })

        projected = []
        for cam_labels in frame.projected_lidar_labels:
            if cam_labels.name != front:
                continue
            for lab in cam_labels.labels:
                box = lab.box
                # Projected ids carry a camera suffix (e.g. "<laser_id>_FRONT").
                base_id = lab.id.rsplit("_FRONT", 1)[0]
                projected.append({
                    "id": base_id,
                    "bbox": [
                        box.center_x - box.length / 2.0,
                        box.center_y - box.width / 2.0,
                        box.center_x + box.length / 2.0,
                        box.center_y + box.width / 2.0,
                    ],
                })

        frames_out.append({
            "index": idx,
            "timestamp_micros": frame.timestamp_micros,
            "pose": _mat4(frame.pose.transform),
            "labels": labels,
            "projected_boxes": projected,
        })

    result = {
        "scene_name": scene_name,
        "camera": "FRONT",
        "camera_extrinsic": camera_extrinsic,   # 4x4 camera->vehicle
        "camera_intrinsic": camera_intrinsic,
        "num_frames": len(frames_out),
        "frames": frames_out,
    }

    out_path = Path(out_path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f)

    print(f"Wrote {out_path}: {len(frames_out)} frames, scene={scene_name}")
    return result
