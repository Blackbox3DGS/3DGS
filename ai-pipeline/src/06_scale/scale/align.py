"""Scale alignment: two-pass depth map calibration.

Pass 1 — Linear regression between COLMAP sparse depths and relative depth maps.
Pass 2 — Ground plane prior correction (camera height = 1.5 m).
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

CAMERA_HEIGHT_PRIOR = {
    "video": 1.5,   # typical dashcam
    "waymo": 2.05,  # Waymo top-mounted camera
}
DEFAULT_CAMERA_HEIGHT = 1.5


class ScaleAlignmentError(Exception):
    """Irrecoverable failure in scale alignment."""


# ---------------------------------------------------------------------------
# Sparse point cloud helpers
# ---------------------------------------------------------------------------

def load_sparse_points(ply_path: Path) -> np.ndarray:
    """Load sparse PLY as (N, 3) float64 array."""
    # 지연 임포트 — open3d는 이 로더에서만 쓰이는데 arm64 mac(py3.14)엔 휠이
    # 없어, 모듈 레벨 임포트면 fit_ground_plane까지 못 쓰게 된다.
    import open3d as o3d
    pcd = o3d.io.read_point_cloud(str(ply_path))
    pts = np.asarray(pcd.points)
    if pts.size == 0:
        logger.warning("Sparse PLY has zero points: %s", ply_path)
        return np.zeros((0, 3), dtype=np.float64)
    logger.info("Loaded %d sparse points from %s", len(pts), ply_path)
    return pts


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def project_points_to_frame(
    points_world: np.ndarray,
    c2w: np.ndarray,
    fx: float, fy: float, cx: float, cy: float,
    width: int, height: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Project world points into a camera frame.

    Returns
    -------
    pixel_coords : (K, 2)  integer (u, v) coordinates of valid projections
    cam_depths   : (K,)    corresponding depths in camera space
    """
    N = len(points_world)
    if N == 0:
        return np.zeros((0, 2), dtype=int), np.zeros(0)

    w2c = np.linalg.inv(c2w)
    hom = np.hstack([points_world, np.ones((N, 1))])  # (N, 4)
    p_cam = (w2c @ hom.T).T  # (N, 4)

    z = p_cam[:, 2]
    valid = z > 0.01
    p_cam = p_cam[valid]
    z = z[valid]

    u = (fx * p_cam[:, 0] / z + cx).astype(int)
    v = (fy * p_cam[:, 1] / z + cy).astype(int)

    in_bounds = (u >= 0) & (u < width) & (v >= 0) & (v < height)
    return np.stack([u[in_bounds], v[in_bounds]], axis=1), z[in_bounds]


def select_ground_sparse_points(
    points_world: np.ndarray,
    poses: np.ndarray,
    registered_frames: list[str],
    intrinsics: dict,
    bottom_frac: float = 0.40,
    min_frame_hits: int = 1,
) -> np.ndarray:
    """Select sparse points likely on the ground by projecting to bottom of frames.

    Returns the subset of *points_world* that project into the bottom
    *bottom_frac* of the image in at least *min_frame_hits* sampled frames.
    """
    fx, fy = intrinsics["fx"], intrinsics["fy"]
    cx, cy = intrinsics["cx"], intrinsics["cy"]
    w, h = intrinsics["width"], intrinsics["height"]
    v_thresh = int(h * (1 - bottom_frac))

    N = len(points_world)
    hit_counts = np.zeros(N, dtype=int)

    step = max(1, len(registered_frames) // 20)
    n_sampled = 0
    for i in range(0, len(registered_frames), step):
        c2w = poses[i]
        w2c = np.linalg.inv(c2w)
        hom = np.hstack([points_world, np.ones((N, 1))])
        p_cam = (w2c @ hom.T).T

        z = p_cam[:, 2]
        valid = z > 0.01

        u = np.full(N, -1, dtype=int)
        v = np.full(N, -1, dtype=int)
        u[valid] = (fx * p_cam[valid, 0] / z[valid] + cx).astype(int)
        v[valid] = (fy * p_cam[valid, 1] / z[valid] + cy).astype(int)

        in_bottom = valid & (u >= 0) & (u < w) & (v >= v_thresh) & (v < h)
        hit_counts[in_bottom] += 1
        n_sampled += 1

    mask = hit_counts >= min(min_frame_hits, n_sampled)
    ground_pts = points_world[mask]

    if len(ground_pts) < 10:
        logger.warning(
            "Only %d ground candidates from sparse points (need ≥10). "
            "Falling back to full sparse cloud.", len(ground_pts),
        )
        return points_world

    logger.info(
        "Selected %d / %d sparse points as ground candidates "
        "(bottom_frac=%.0f%%, min_hits=%d, sampled %d frames)",
        len(ground_pts), N, bottom_frac * 100, min_frame_hits, n_sampled,
    )
    return ground_pts


# ---------------------------------------------------------------------------
# Pass 1 — Collect depth pairs & fit scale/shift
# ---------------------------------------------------------------------------

def collect_depth_pairs(
    points_world: np.ndarray,
    depth_maps_dir: Path,
    poses: np.ndarray,
    registered_frames: list[str],
    intrinsics: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Gather (relative_depth, colmap_depth) pairs across all registered frames."""
    fx, fy = intrinsics["fx"], intrinsics["fy"]
    cx, cy = intrinsics["cx"], intrinsics["cy"]
    w, h = intrinsics["width"], intrinsics["height"]

    rel_list, col_list = [], []

    for idx, fname in enumerate(registered_frames):
        stem = Path(fname).stem
        npy_path = depth_maps_dir / f"{stem}.npy"
        if not npy_path.exists():
            continue

        depth_map = np.load(npy_path)
        pixels, cam_depths = project_points_to_frame(
            points_world, poses[idx], fx, fy, cx, cy, w, h,
        )
        if len(pixels) == 0:
            continue

        sampled = depth_map[pixels[:, 1], pixels[:, 0]]
        good = (sampled > 0.01) & (sampled < 0.99)
        rel_list.append(sampled[good])
        col_list.append(cam_depths[good])

    if not rel_list:
        raise ScaleAlignmentError("No valid depth pairs collected.")

    return np.concatenate(rel_list), np.concatenate(col_list)


def fit_scale_shift(
    rel_depths: np.ndarray,
    colmap_depths: np.ndarray,
    ransac_iters: int = 1000,
    inlier_thresh: float = 2.0,
) -> tuple[float, float]:
    """RANSAC linear fit: colmap_depth = scale * rel_depth + shift."""
    n = len(rel_depths)
    if n < 2:
        raise ScaleAlignmentError(f"Too few depth pairs ({n}) for regression.")

    if n < 50:
        logger.warning("Only %d pairs — using simple regression (no RANSAC).", n)
        coeffs = np.polyfit(rel_depths, colmap_depths, 1)
        return float(coeffs[0]), float(coeffs[1])

    best_inliers = 0
    best_s, best_t = 0.0, 0.0

    rng = np.random.default_rng(42)
    for _ in range(ransac_iters):
        i, j = rng.choice(n, size=2, replace=False)
        dx = rel_depths[i] - rel_depths[j]
        if abs(dx) < 1e-9:
            continue
        s = (colmap_depths[i] - colmap_depths[j]) / dx
        t = colmap_depths[i] - s * rel_depths[i]
        residuals = np.abs(colmap_depths - (s * rel_depths + t))
        inliers = int(np.sum(residuals < inlier_thresh))
        if inliers > best_inliers:
            best_inliers = inliers
            best_s, best_t = s, t

    # Refit on inliers
    residuals = np.abs(colmap_depths - (best_s * rel_depths + best_t))
    mask = residuals < inlier_thresh
    coeffs = np.polyfit(rel_depths[mask], colmap_depths[mask], 1)
    scale, shift = float(coeffs[0]), float(coeffs[1])

    logger.info(
        "Pass 1 fit: scale=%.4f shift=%.4f  (%d/%d inliers)",
        scale, shift, int(mask.sum()), n,
    )
    return scale, shift


# ---------------------------------------------------------------------------
# Pass 2 — Ground plane prior
# ---------------------------------------------------------------------------

def road_pixel_coords(height: int, width: int, bottom_frac: float = 0.25, step: int = 8):
    """Return (R, 2) array of (v, u) pixel indices in the bottom region."""
    v_start = int(height * (1 - bottom_frac))
    vs = np.arange(v_start, height, step)
    us = np.arange(0, width, step)
    vv, uu = np.meshgrid(vs, us, indexing="ij")
    return np.stack([vv.ravel(), uu.ravel()], axis=1)


def backproject_pixels(
    vu: np.ndarray,
    depth_map: np.ndarray,
    c2w: np.ndarray,
    fx: float, fy: float, cx: float, cy: float,
) -> np.ndarray:
    """Back-project (v, u) pixels to 3D world coords. Returns (K, 3)."""
    depths = depth_map[vu[:, 0], vu[:, 1]]
    valid = depths > 0.01
    vu = vu[valid]
    depths = depths[valid]

    u = vu[:, 1].astype(np.float64)
    v = vu[:, 0].astype(np.float64)
    x_cam = (u - cx) / fx * depths
    y_cam = (v - cy) / fy * depths
    z_cam = depths

    pts_cam = np.stack([x_cam, y_cam, z_cam, np.ones_like(z_cam)], axis=1)  # (K, 4)
    pts_world = (c2w @ pts_cam.T).T[:, :3]
    # Filter NaN/Inf
    finite = np.all(np.isfinite(pts_world), axis=1)
    return pts_world[finite]


def fit_ground_plane(
    points: np.ndarray,
    ransac_iters: int = 1000,
    inlier_thresh: float | None = None,
    max_points: int = 50000,
) -> tuple[np.ndarray, float]:
    """RANSAC plane fit. Returns (normal, d) where normal · x + d = 0.

    When *inlier_thresh* is None (default), a threshold is computed as 1% of the
    scene extent (90th-percentile diameter).  This scales with COLMAP's arbitrary
    coordinate system and is tight enough to separate ground from non-ground.
    """
    n = len(points)
    if n < 10:
        raise ScaleAlignmentError(f"Too few road points ({n}) for plane fit.")

    # Compute scene-extent-based threshold when not explicitly given.
    if inlier_thresh is None:
        centroid = np.median(points, axis=0)
        dists_to_centroid = np.linalg.norm(points - centroid, axis=1)
        scene_extent = float(np.percentile(dists_to_centroid, 90)) * 2
        inlier_thresh = 0.01 * scene_extent
        logger.info(
            "  ground plane RANSAC: scene_extent=%.4f, inlier_thresh=%.6f",
            scene_extent, inlier_thresh,
        )

    # Subsample for speed
    if n > max_points:
        rng_sub = np.random.default_rng(0)
        idx_sub = rng_sub.choice(n, size=max_points, replace=False)
        points = points[idx_sub]
        n = max_points
        logger.info("  subsampled road points to %d for RANSAC", n)

    rng = np.random.default_rng(42)
    best_count = 0
    best_normal = np.array([0, 1, 0], dtype=np.float64)
    best_d = 0.0

    for _ in range(ransac_iters):
        idx = rng.choice(n, size=3, replace=False)
        p0, p1, p2 = points[idx]
        normal = np.cross(p1 - p0, p2 - p0)
        norm = np.linalg.norm(normal)
        if norm < 1e-9:
            continue
        normal /= norm
        d = -normal @ p0
        dists = np.abs(points @ normal + d)
        count = int(np.sum(dists < inlier_thresh))
        if count > best_count:
            best_count = count
            best_normal = normal
            best_d = d

    # SVD refit on inliers
    dists = np.abs(points @ best_normal + best_d)
    inlier_mask = dists < inlier_thresh
    inlier_pts = points[inlier_mask]
    if len(inlier_pts) >= 3:
        centroid = inlier_pts.mean(axis=0)
        # full_matrices=False (economy SVD): we only need Vt (3x3); the default
        # full U is (N, N) — at N=50k that's ~20 GB and triggers a RAM OOM kill.
        _, _, Vt = np.linalg.svd(inlier_pts - centroid, full_matrices=False)
        best_normal = Vt[-1]
        best_d = -best_normal @ centroid

    logger.info(
        "Ground plane: normal=[%.3f,%.3f,%.3f] d=%.3f  (%d/%d inliers, thresh=%.6f)",
        *best_normal, best_d, int(inlier_mask.sum()), n, inlier_thresh,
    )
    return best_normal, best_d


def compute_ground_correction(
    poses: np.ndarray,
    plane_normal: np.ndarray,
    plane_d: float,
    target_height: float = DEFAULT_CAMERA_HEIGHT,
) -> float:
    """Return multiplicative correction k = target_height / measured_height."""
    cam_centers = poses[:, :3, 3]  # (M, 3)
    dists = np.abs(cam_centers @ plane_normal + plane_d)
    measured = float(np.median(dists))

    # Threshold relative to scene scale (camera spread), not absolute metres.
    scene_scale = float(np.median(np.linalg.norm(
        cam_centers - cam_centers.mean(axis=0), axis=1,
    )))
    if measured < 1e-4 * max(scene_scale, 1e-12):
        logger.error(
            "Measured camera height ≈ 0 (%.6f, scene_scale=%.6f) — skipping correction.",
            measured, scene_scale,
        )
        return 1.0

    k = target_height / measured
    if k < 0.1 or k > 500:
        logger.warning("Correction k=%.2f outside expected range [0.1, 500].", k)
    logger.info(
        "Pass 2: measured_height=%.6f (COLMAP units), target=%.2f m, correction k=%.4f",
        measured, target_height, k,
    )
    return k


def orient_normal_toward_cameras(
    normal: np.ndarray,
    plane_d: float,
    poses: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Ensure the plane normal points from ground toward cameras."""
    cam_mean = poses[:, :3, 3].mean(axis=0)
    if normal @ cam_mean + plane_d < 0:
        normal = -normal
        plane_d = -plane_d
    return normal, plane_d
