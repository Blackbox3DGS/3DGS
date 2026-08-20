"""Prepare COLMAP-compatible directory structure for gaussian-splatting training."""

import logging
import shutil
import struct
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


# COLMAP camera model IDs (from colmap/src/base/camera_models.h)
_CAMERA_MODEL_IDS = {
    "SIMPLE_PINHOLE": 0,
    "PINHOLE": 1,
    "SIMPLE_RADIAL": 2,
    "RADIAL": 3,
    "OPENCV": 4,
}
_CAMERA_MODEL_NAMES = {v: k for k, v in _CAMERA_MODEL_IDS.items()}


def _convert_cameras_txt_to_pinhole(src: Path, dst: Path):
    """Rewrite cameras.txt, converting OPENCV → PINHOLE (drop distortion)."""
    lines_out = []
    converted = False
    with open(src) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                lines_out.append(line)
                continue
            parts = line.strip().split()
            cam_id, model = parts[0], parts[1]
            if model == "OPENCV":
                w, h = parts[2], parts[3]
                fx, fy, cx, cy = parts[4], parts[5], parts[6], parts[7]
                # Drop k1, k2, p1, p2 (params[4:8])
                lines_out.append(
                    f"{cam_id} PINHOLE {w} {h} {fx} {fy} {cx} {cy}\n"
                )
                converted = True
                logger.info("  cameras.txt: OPENCV -> PINHOLE (dropped distortion)")
            else:
                lines_out.append(line)
    with open(dst, "w") as f:
        f.writelines(lines_out)
    return converted


def _convert_cameras_bin_to_pinhole(src: Path, dst: Path):
    """Rewrite cameras.bin, converting OPENCV → PINHOLE (drop distortion)."""
    with open(src, "rb") as f:
        num_cameras = struct.unpack("<Q", f.read(8))[0]
        cameras = []
        for _ in range(num_cameras):
            cam_id = struct.unpack("<I", f.read(4))[0]
            model_id = struct.unpack("<i", f.read(4))[0]
            width = struct.unpack("<Q", f.read(8))[0]
            height = struct.unpack("<Q", f.read(8))[0]
            model_name = _CAMERA_MODEL_NAMES.get(model_id, f"UNKNOWN({model_id})")

            # Read params based on model
            if model_name == "OPENCV":
                params = struct.unpack("<8d", f.read(64))  # fx,fy,cx,cy,k1,k2,p1,p2
                # Convert to PINHOLE: keep only fx,fy,cx,cy
                cameras.append((cam_id, _CAMERA_MODEL_IDS["PINHOLE"],
                                width, height, params[:4]))
                logger.info("  cameras.bin: OPENCV -> PINHOLE (dropped distortion)")
            elif model_name == "PINHOLE":
                params = struct.unpack("<4d", f.read(32))
                cameras.append((cam_id, model_id, width, height, params))
            elif model_name == "SIMPLE_PINHOLE":
                params = struct.unpack("<3d", f.read(24))
                cameras.append((cam_id, model_id, width, height, params))
            else:
                raise ValueError(f"Unsupported camera model in bin: {model_name}")

    with open(dst, "wb") as f:
        f.write(struct.pack("<Q", num_cameras))
        for cam_id, model_id, width, height, params in cameras:
            f.write(struct.pack("<I", cam_id))
            f.write(struct.pack("<i", model_id))
            f.write(struct.pack("<Q", width))
            f.write(struct.pack("<Q", height))
            for p in params:
                f.write(struct.pack("<d", p))


def _filter_images_txt(src: Path, dst: Path, keep_names: set[str]):
    """Rewrite images.txt keeping only frames in keep_names.

    COLMAP images.txt format: pairs of lines per image.
      Line 1: IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME
      Line 2: POINTS2D[] as (X Y POINT3D_ID) ...
    """
    lines_out = []
    kept = 0
    with open(src) as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#") or not line.strip():
            lines_out.append(line)
            i += 1
            continue
        # Image header line — check NAME (last field)
        parts = line.strip().split()
        name = parts[-1] if len(parts) >= 10 else ""
        if name in keep_names:
            lines_out.append(line)
            if i + 1 < len(lines):
                lines_out.append(lines[i + 1])  # points2D line
            kept += 1
        i += 2  # skip both lines (header + points2D)

    with open(dst, "w") as f:
        f.writelines(lines_out)
    logger.info("  images.txt: %d/%d frames kept (filtered to images_3dgs)",
                kept, kept + (len(lines) - len(lines_out)) // 2)


def _filter_images_bin(src: Path, dst: Path, keep_names: set[str]):
    """Rewrite images.bin keeping only frames in keep_names.

    COLMAP images.bin format per image:
      image_id (4B uint32) + qvec (32B, 4×double) + tvec (24B, 3×double)
      + camera_id (4B uint32) + name (null-terminated string)
      + num_points2D (8B uint64) + points2D (num × 24B: x,y,point3d_id)
    """
    kept_entries = []
    with open(src, "rb") as f:
        num_images = struct.unpack("<Q", f.read(8))[0]
        for _ in range(num_images):
            image_id = struct.unpack("<I", f.read(4))[0]
            qvec = f.read(32)   # 4 doubles
            tvec = f.read(24)   # 3 doubles
            camera_id = struct.unpack("<I", f.read(4))[0]
            # Read null-terminated name
            name_bytes = b""
            while True:
                ch = f.read(1)
                if ch == b"\x00":
                    break
                name_bytes += ch
            name = name_bytes.decode("utf-8")
            num_points2D = struct.unpack("<Q", f.read(8))[0]
            points2D_data = f.read(num_points2D * 24)  # each: x(8B) + y(8B) + id(8B)

            if name in keep_names:
                kept_entries.append((image_id, qvec, tvec, camera_id,
                                    name_bytes, num_points2D, points2D_data))

    with open(dst, "wb") as f:
        f.write(struct.pack("<Q", len(kept_entries)))
        for image_id, qvec, tvec, camera_id, name_bytes, num_pts, pts_data in kept_entries:
            f.write(struct.pack("<I", image_id))
            f.write(qvec)
            f.write(tvec)
            f.write(struct.pack("<I", camera_id))
            f.write(name_bytes + b"\x00")
            f.write(struct.pack("<Q", num_pts))
            f.write(pts_data)

    logger.info("  images.bin: %d/%d frames kept", len(kept_entries), num_images)


def _convert_ply_for_gs(src: Path, dst: Path, max_points: int | None = None):
    """Convert Open3D PLY to gaussian-splatting compatible format.

    gaussian-splatting's fetchPly() requires: float x,y,z + float nx,ny,nz + uchar red,green,blue.
    Open3D writes: double x,y,z + uchar red,green,blue (no normals).
    We use plyfile's storePly convention for compatibility.

    When *max_points* is set and the cloud exceeds it, the init cloud is randomly
    subsampled to that size. The dense fused cloud from Stage 07/08 can hold
    >10M points, which makes 3DGS start with that many Gaussians and OOM on a
    24GB GPU; standard 3DGS inits with ~1e5–5e5. Densification still grows the
    model during training, so this only caps the *starting* count.
    """
    import open3d as o3d

    pcd = o3d.io.read_point_cloud(str(src))
    xyz = np.asarray(pcd.points, dtype=np.float32)
    colors = np.asarray(pcd.colors)  # 0-1 float64

    # Convert colors to uint8
    rgb = (colors * 255).clip(0, 255).astype(np.uint8) if len(colors) > 0 else np.zeros((len(xyz), 3), dtype=np.uint8)

    # Cap the init cloud (random subsample) to keep the 3DGS starting Gaussian
    # count within GPU memory. Same RNG-seeded pattern as 04g's sparse cap.
    if max_points is not None and len(xyz) > max_points:
        n_before = len(xyz)
        idx = np.random.default_rng(0).choice(n_before, size=max_points, replace=False)
        xyz = xyz[idx]
        rgb = rgb[idx]  # rgb is always original-length (from colors or zeros)
        logger.info("  Init cloud capped for 3DGS: %d -> %d points", n_before, max_points)

    n = len(xyz)
    logger.info("  Converting PLY for gaussian-splatting: %d points", n)

    # Write PLY with the exact property names gaussian-splatting expects.
    # Use numpy structured array for fast bulk write.
    dtype = np.dtype([
        ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
        ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"),
        ("red", "u1"), ("green", "u1"), ("blue", "u1"),
    ])
    data = np.zeros(n, dtype=dtype)
    data["x"], data["y"], data["z"] = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    data["red"], data["green"], data["blue"] = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    # nx, ny, nz remain zero

    with open(dst, "wb") as f:
        header = (
            "ply\n"
            "format binary_little_endian 1.0\n"
            f"element vertex {n}\n"
            "property float x\n"
            "property float y\n"
            "property float z\n"
            "property float nx\n"
            "property float ny\n"
            "property float nz\n"
            "property uchar red\n"
            "property uchar green\n"
            "property uchar blue\n"
            "end_header\n"
        )
        f.write(header.encode("ascii"))
        f.write(data.tobytes())


def prepare_scene_dir(
    scene_dir: Path,
    images_dir: Path,
    masks_dir: Path,
    colmap_model_dir: Path,
    filtered_ply: Path,
    max_init_points: int | None = None,
) -> Path:
    """Create directory structure expected by gaussian-splatting.

    Layout::

        scene_dir/
        ├── images/          → symlink to images_dir (3DGS subset)
        ├── masks/           → symlink to masks_dir
        └── sparse/0/
            ├── cameras.bin  (PINHOLE, converted from OPENCV if needed)
            ├── images.bin   (filtered to match images_dir)
            └── points3D.ply (our filtered dense PC)
    """
    scene_dir.mkdir(parents=True, exist_ok=True)

    # Collect filenames present in images_dir (the 3DGS subset)
    keep_names = {p.name for p in images_dir.iterdir() if p.suffix in (".jpg", ".png")}
    logger.info("  images_3dgs contains %d frames", len(keep_names))

    # Symlink images
    img_link = scene_dir / "images"
    if img_link.exists():
        img_link.unlink() if img_link.is_symlink() else shutil.rmtree(img_link)
    img_link.symlink_to(images_dir.resolve())
    logger.info("  images -> %s", images_dir)

    # Symlink masks
    mask_link = scene_dir / "masks"
    if mask_link.exists():
        mask_link.unlink() if mask_link.is_symlink() else shutil.rmtree(mask_link)
    mask_link.symlink_to(masks_dir.resolve())
    logger.info("  masks -> %s", masks_dir)

    # Copy COLMAP model — convert OPENCV → PINHOLE for gaussian-splatting
    sparse_dir = scene_dir / "sparse" / "0"
    sparse_dir.mkdir(parents=True, exist_ok=True)

    # cameras: convert OPENCV → PINHOLE (gaussian-splatting only supports PINHOLE)
    for name, converter in [
        ("cameras.txt", _convert_cameras_txt_to_pinhole),
        ("cameras.bin", _convert_cameras_bin_to_pinhole),
    ]:
        src = colmap_model_dir / name
        if src.exists():
            converter(src, sparse_dir / name)

    # images: filter to only include frames present in images_3dgs
    for name, filterer in [
        ("images.txt", _filter_images_txt),
        ("images.bin", _filter_images_bin),
    ]:
        src = colmap_model_dir / name
        if src.exists():
            filterer(src, sparse_dir / name, keep_names)

    # Convert filtered PC to gaussian-splatting compatible PLY format.
    # gaussian-splatting's fetchPly() expects: float x,y,z + uchar red,green,blue + float nx,ny,nz
    # Our Open3D PLY has double x,y,z + uchar red,green,blue (no normals).
    dst_ply = sparse_dir / "points3D.ply"
    _convert_ply_for_gs(filtered_ply, dst_ply, max_points=max_init_points)
    logger.info("  points3D.ply <- %s (converted for gaussian-splatting)", filtered_ply)

    # Remove points3D.bin/.txt if present (force PLY loading)
    for ext in [".bin", ".txt"]:
        p = sparse_dir / f"points3D{ext}"
        if p.exists():
            p.unlink()

    logger.info("Scene directory ready: %s", scene_dir)
    return scene_dir
