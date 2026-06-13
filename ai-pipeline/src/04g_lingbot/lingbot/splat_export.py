"""Export LingBot predictions to a web-renderable .splat point cloud.

Lives in the 3DGS repo (git-managed) and uses lingbot-map only as an installed
library. Mirrors LingBot's own point assembly (world points + confidence +
optional sky mask) but writes the compact 32-byte `.splat` format used by web
viewers (antimatter15/splat, gsplat.js). Each point becomes a small isotropic
Gaussian, so forward-driving footage that 3DGS can't fit cleanly is rendered
faithfully as a point cloud.

Adds **dynamic-object masking**: a directory of binary PNG masks (white =
dynamic, the Stage-03 convention) drops the matching pixels, so moving vehicles
leave a clean hole for a 3D car model to be placed on later.

Also **ground-aligns** the scene (road normal → up_axis) and recenters it, then
removes statistical outliers — so the web viewer frames it at a sensible
distance with cars sitting flat on the road.

.splat layout (per point, 32 bytes):
    x,y,z (f32) | sx,sy,sz (f32) | r,g,b,a (u8) | qw,qx,qy,qz (u8, quat*128+128)
"""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np

from lingbot_map.utils.geometry import unproject_depth_map_to_point_map

_SPLAT_DTYPE = np.dtype([
    ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
    ("sx", "<f4"), ("sy", "<f4"), ("sz", "<f4"),
    ("r", "u1"), ("g", "u1"), ("b", "u1"), ("a", "u1"),
    ("qw", "u1"), ("qx", "u1"), ("qy", "u1"), ("qz", "u1"),
])


def _fit_ground_normal(xyz: np.ndarray, ransac_iters: int = 500,
                       max_points: int = 50000) -> np.ndarray:
    """RANSAC-fit the dominant plane (road) and return its unit normal.

    Same approach as 06_scale.align.fit_ground_plane (economy-SVD refit to avoid
    a giant U on large inlier sets).
    """
    pts = xyz
    if len(pts) > max_points:
        idx = np.random.default_rng(0).choice(len(pts), max_points, replace=False)
        pts = pts[idx]
    centroid = np.median(pts, axis=0)
    extent = float(np.percentile(np.linalg.norm(pts - centroid, axis=1), 90)) * 2
    thresh = max(1e-6, 0.01 * extent)
    rng = np.random.default_rng(42)
    best_n, best_d, best_cnt = np.array([0.0, 1.0, 0.0]), 0.0, 0
    for _ in range(ransac_iters):
        i = rng.choice(len(pts), 3, replace=False)
        p0, p1, p2 = pts[i]
        n = np.cross(p1 - p0, p2 - p0)
        nn = np.linalg.norm(n)
        if nn < 1e-9:
            continue
        n = n / nn
        d = -n @ p0
        cnt = int(np.sum(np.abs(pts @ n + d) < thresh))
        if cnt > best_cnt:
            best_cnt, best_n, best_d = cnt, n, d
    inl = pts[np.abs(pts @ best_n + best_d) < thresh]
    if len(inl) >= 3:
        c = inl.mean(axis=0)
        _, _, Vt = np.linalg.svd(inl - c, full_matrices=False)
        best_n = Vt[-1]
    return best_n / (np.linalg.norm(best_n) + 1e-12)


def _rotation_normal_to_up(normal: np.ndarray, up=(0.0, 1.0, 0.0)) -> np.ndarray:
    """Rotation matrix taking unit `normal` → `up` (Rodrigues)."""
    a = normal / (np.linalg.norm(normal) + 1e-12)
    b = np.asarray(up, dtype=np.float64)
    v = np.cross(a, b)
    s = float(np.linalg.norm(v))
    c = float(a @ b)
    if s < 1e-9:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * ((1 - c) / (s * s))


def _ground_align_rotation(xyz: np.ndarray, cam_centers: np.ndarray,
                           up=(0.0, 1.0, 0.0)) -> np.ndarray:
    """Compute R (3x3) that rotates the scene so the road normal points to `up`.

    Orients the fitted normal toward the cameras (above the road) = the world
    "up" direction, then rotates that to `up`. Default +Y matches the Three.js /
    gsplat.js frontend (cars upright); use -Y for the antimatter15 debug viewer
    (Y-down) if it looks flipped there.
    """
    normal = _fit_ground_normal(xyz)
    if cam_centers is not None and len(cam_centers):
        ground_pt = np.median(xyz, axis=0)
        if normal @ (np.median(cam_centers, axis=0) - ground_pt) < 0:
            normal = -normal
    return _rotation_normal_to_up(normal, up=up).astype(np.float64)


def _clip_and_recenter(xyz: np.ndarray, rgb: np.ndarray,
                       dist_percentile: float = 99.0):
    """Drop far-outlier points and translate the cloud so its center is at origin.

    Returns (xyz, rgb, center); `center` is the subtracted translation so the
    SAME shift can be applied to ego/vehicle trajectories to keep them aligned.
    """
    center = np.median(xyz, axis=0)
    if dist_percentile and dist_percentile < 100:
        d = np.linalg.norm(xyz - center, axis=1)
        thresh = np.percentile(d, dist_percentile)
        keep = d <= thresh
        n_drop = int((~keep).sum())
        xyz, rgb = xyz[keep], rgb[keep]
        center = np.median(xyz, axis=0)
        print(f"Far-outlier clip (>{dist_percentile}th pct = {thresh:.3f}): dropped {n_drop} points")
    xyz = (xyz - center).astype(np.float32)
    print(f"Recentered cloud by {np.round(center, 3)} (now origin-centered)")
    return xyz, rgb, center.astype(np.float32)


def _apply_dynamic_masks(conf: np.ndarray, dynamic_mask_dir: str,
                         frame_paths: list) -> int:
    """Zero confidence on dynamic-object pixels (white=dynamic), in place."""
    S, H, W = conf.shape
    md = Path(dynamic_mask_dir)
    zeroed = 0
    for i in range(min(S, len(frame_paths))):
        stem = Path(frame_paths[i]).stem
        mpath = None
        for ext in (".png", ".jpg"):
            cand = md / f"{stem}{ext}"
            if cand.exists():
                mpath = cand
                break
        if mpath is None:
            continue
        m = cv2.imread(str(mpath), cv2.IMREAD_GRAYSCALE)
        if m is None:
            continue
        if m.shape[0] != H or m.shape[1] != W:
            m = cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)
        dyn = m > 127
        conf[i][dyn] = 0.0
        zeroed += int(dyn.sum())
    return zeroed


def _apply_sky_mask(conf: np.ndarray, image_folder, images, sky_mask_dir):
    """Run LingBot's ONNX sky segmenter, loaded by file path to bypass
    `lingbot_map/vis/__init__.py` (which eagerly imports viser). The sky module
    only needs onnxruntime, so this keeps viser out of the export path.
    """
    import importlib.util
    import lingbot_map
    sky_file = os.path.join(os.path.dirname(lingbot_map.__file__), "vis", "sky_segmentation.py")
    spec = importlib.util.spec_from_file_location("lingbot_sky_segmentation", sky_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.apply_sky_segmentation(
        conf, image_folder=image_folder, images=images, sky_mask_dir=sky_mask_dir)


def predictions_to_splat(
    predictions: dict,
    out_path: str,
    *,
    conf_threshold: float = 1.5,
    mask_sky: bool = True,
    image_folder=None,
    sky_mask_dir=None,
    dynamic_mask_dir=None,
    frame_paths=None,
    point_size=None,
    max_points: int = 2_000_000,
    clip_percentile: float = 99.0,
    ground_align: bool = True,
    up_axis: tuple = (0.0, 1.0, 0.0),
    outlier_removal: bool = True,
    use_point_map=None,
):
    """Assemble a global point cloud and write it as .splat.

    Returns (out_path, R, center): the transform applied to the cloud is
    p -> R @ p - center; apply the SAME (R, center) to ego/vehicle trajectories.
    `predictions` needs: images (S,3,H,W [0,1]), extrinsic (S,3,4 c2w),
    intrinsic (S,3,3); plus world_points/world_points_conf or depth/depth_conf.
    """
    images = predictions["images"]
    depth_conf = predictions.get("depth_conf")
    extrinsics_cam = predictions["extrinsic"]
    intrinsics_cam = predictions["intrinsic"]

    if use_point_map is None:
        use_point_map = predictions.get("world_points") is not None

    if use_point_map:
        world_points = predictions["world_points"]
        conf = predictions.get("world_points_conf", depth_conf)
    else:
        world_points = unproject_depth_map_to_point_map(
            predictions["depth"], extrinsics_cam, intrinsics_cam)
        conf = depth_conf

    if conf is None:
        conf = np.ones(world_points.shape[:3], dtype=np.float32)
    conf = np.asarray(conf, dtype=np.float32).copy()

    if mask_sky:
        conf = _apply_sky_mask(conf, image_folder, images, sky_mask_dir)

    if dynamic_mask_dir and frame_paths is not None:
        n_dyn = _apply_dynamic_masks(conf, dynamic_mask_dir, frame_paths)
        print(f"Dynamic masking: zeroed {n_dyn} pixels from {dynamic_mask_dir}")

    xyz = np.asarray(world_points).reshape(-1, 3).astype(np.float32)
    colors = np.asarray(images).transpose(0, 2, 3, 1).reshape(-1, 3)
    rgb = np.clip(colors * 255.0, 0, 255).astype(np.uint8)
    conf_flat = conf.reshape(-1)

    keep = (conf_flat > conf_threshold) & np.isfinite(xyz).all(axis=1)
    xyz, rgb = xyz[keep], rgb[keep]
    print(f"Confidence filter (conf>{conf_threshold}): {int(keep.sum())}/{keep.size} points kept")
    if len(xyz) == 0:
        raise RuntimeError("No points survived filtering — lower conf_threshold?")

    R = np.eye(3)
    if ground_align:
        cam_centers = np.asarray(extrinsics_cam, dtype=np.float64)[:, :3, 3]
        R = _ground_align_rotation(xyz.astype(np.float64), cam_centers, up=up_axis)
        xyz = (xyz @ R.T).astype(np.float32)
        print(f"Ground-aligned scene (road normal -> {tuple(up_axis)})")

    xyz, rgb, center = _clip_and_recenter(xyz, rgb, dist_percentile=clip_percentile)

    if outlier_removal:
        try:
            import open3d as o3d
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(xyz.astype(np.float64))
            pcd.colors = o3d.utility.Vector3dVector(rgb.astype(np.float64) / 255.0)
            n_before = len(pcd.points)
            pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
            xyz = np.asarray(pcd.points, dtype=np.float32)
            rgb = (np.asarray(pcd.colors) * 255.0).clip(0, 255).astype(np.uint8)
            print(f"Outlier removal: {n_before} -> {len(xyz)} points")
        except Exception as e:
            print(f"Outlier removal skipped ({e})")

    if len(xyz) > max_points:
        idx = np.random.default_rng(0).choice(len(xyz), size=max_points, replace=False)
        xyz, rgb = xyz[idx], rgb[idx]
        print(f"Subsampled to {max_points} points for web payload")

    if point_size is None:
        lo = np.percentile(xyz, 5, axis=0)
        hi = np.percentile(xyz, 95, axis=0)
        scene_scale = float(np.linalg.norm(hi - lo)) or 1.0
        point_size = scene_scale / 700.0
        print(f"Auto point_size={point_size:.5f} (scene_scale={scene_scale:.3f})")

    n = len(xyz)
    data = np.zeros(n, dtype=_SPLAT_DTYPE)
    data["x"], data["y"], data["z"] = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    data["sx"] = data["sy"] = data["sz"] = np.float32(point_size)
    data["r"], data["g"], data["b"] = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    data["a"] = 255
    data["qw"], data["qx"], data["qy"], data["qz"] = 255, 128, 128, 128

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(data.tobytes())
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"Wrote {out_path} ({size_mb:.1f} MB, {n} points as Gaussians)")
    return out_path, R.astype(np.float32), center
