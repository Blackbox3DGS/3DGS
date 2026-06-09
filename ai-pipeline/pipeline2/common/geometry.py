"""지오메트리: RANSAC 지면 평면 검출 → Y=0 정렬, 변환을 포인트/포즈에 적용.

핵심 규약
  - 월드 점:   (N,3)
  - 카메라 포즈: c2w 4x4 (camera-to-world). 카메라 중심 C = pose[:3, 3]
  - 정렬 변환 T(4x4): 월드 좌표에 좌측 적용.  p' = (T @ [p,1])[:3]
                       포즈도 좌측 적용.        c2w' = T @ c2w
정렬 목표: 지면 = Y=0 평면, 지면 법선 = +Y(위).
"""

from __future__ import annotations

import logging
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RANSAC 지면 평면
# ---------------------------------------------------------------------------
def fit_ground_plane(
    points: np.ndarray,
    distance_threshold: float = 0.05,
    ransac_n: int = 3,
    num_iterations: int = 2000,
) -> tuple[np.ndarray, np.ndarray]:
    """open3d RANSAC 으로 지배적 평면 검출.

    Returns:
        plane_model: (4,) [a,b,c,d],  a x + b y + c z + d = 0, |[a,b,c]|=1
        inlier_idx:  (M,) inlier 점 인덱스
    """
    import open3d as o3d

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(np.asarray(points, dtype=np.float64))
    plane_model, inliers = pcd.segment_plane(
        distance_threshold=distance_threshold,
        ransac_n=ransac_n,
        num_iterations=num_iterations,
    )
    plane_model = np.asarray(plane_model, dtype=np.float64)
    n = np.linalg.norm(plane_model[:3])
    if n > 0:
        plane_model = plane_model / n  # 법선 정규화 (d 도 함께 스케일)
    inlier_idx = np.asarray(inliers, dtype=np.int64)
    logger.info(
        "지면 평면: normal=[%.3f %.3f %.3f] d=%.3f, inliers=%d/%d",
        *plane_model[:3], plane_model[3], len(inlier_idx), len(points),
    )
    return plane_model, inlier_idx


# ---------------------------------------------------------------------------
# 회전 헬퍼
# ---------------------------------------------------------------------------
def _rotation_from_a_to_b(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """단위벡터 a 를 단위벡터 b 로 보내는 최소회전 3x3 (Rodrigues)."""
    a = a / (np.linalg.norm(a) + 1e-12)
    b = b / (np.linalg.norm(b) + 1e-12)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-8:
        # 평행: 같은 방향이면 단위, 반대면 180° 회전
        if c > 0:
            return np.eye(3)
        # a 에 수직인 임의 축으로 180°
        axis = np.array([1.0, 0.0, 0.0])
        if abs(a[0]) > 0.9:
            axis = np.array([0.0, 1.0, 0.0])
        axis = axis - a * np.dot(axis, a)
        axis /= np.linalg.norm(axis)
        K = _skew(axis)
        return np.eye(3) + 2.0 * (K @ K)  # 180° = I + 2 K^2
    K = _skew(v)
    return np.eye(3) + K + K @ K * (1.0 / (1.0 + c))


def _skew(v: np.ndarray) -> np.ndarray:
    return np.array(
        [[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]], dtype=np.float64
    )


# ---------------------------------------------------------------------------
# 정렬 변환 계산
# ---------------------------------------------------------------------------
def ground_alignment_transform(
    plane_model: np.ndarray,
    cam_centers: np.ndarray | None = None,
    ground_points: np.ndarray | None = None,
) -> np.ndarray:
    """지면 평면을 Y=0(법선 +Y)으로 보내는 4x4 변환을 만든다.

    법선 방향(위/아래)은 카메라 중심들이 지면 *위*에 있다는 사실로 결정.
    cam_centers 없으면 평면 법선이 +Y 와 이루는 각으로 부호 추정.
    """
    normal = plane_model[:3].astype(np.float64)
    d = float(plane_model[3])
    normal = normal / (np.linalg.norm(normal) + 1e-12)

    # --- 법선이 '위'를 향하도록 부호 결정 ---
    if cam_centers is not None and len(cam_centers) > 0:
        # 평면에서 카메라 중심들까지의 부호거리 평균이 양수가 되도록
        signed = cam_centers @ normal + d
        if np.mean(signed) < 0:
            normal, d = -normal, -d
    else:
        if normal[1] < 0:  # +Y 와 같은 반구로
            normal, d = -normal, -d

    # --- 회전: normal → +Y ---
    up = np.array([0.0, 1.0, 0.0])
    R = _rotation_from_a_to_b(normal, up)

    # --- 평행이동: 회전 후 지면이 Y=0 이 되도록 ---
    # 평면 위 한 점 p0 (= -d * normal) 를 회전한 뒤 Y 성분을 0 으로.
    p0 = -d * normal
    p0_rot = R @ p0
    t = np.array([0.0, -p0_rot[1], 0.0])

    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t

    # 검증 로그: 지면 점들의 잔차
    if ground_points is not None and len(ground_points) > 0:
        gp = apply_transform_points(ground_points, T)
        logger.info(
            "정렬 후 지면 Y: mean=%.4f std=%.4f (목표 0)",
            float(np.mean(gp[:, 1])), float(np.std(gp[:, 1])),
        )
    return T


# ---------------------------------------------------------------------------
# 변환 적용
# ---------------------------------------------------------------------------
def apply_transform_points(points: np.ndarray, T: np.ndarray) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float64)
    return (pts @ T[:3, :3].T) + T[:3, 3]


def apply_transform_poses(poses_c2w: np.ndarray, T: np.ndarray) -> np.ndarray:
    """c2w (N,4,4) 또는 (4,4) 에 좌측 변환 적용."""
    poses = np.asarray(poses_c2w, dtype=np.float64)
    single = poses.ndim == 2
    poses = poses.reshape(-1, 4, 4)
    out = np.einsum("ij,njk->nik", T, poses)
    return out[0] if single else out


def camera_centers(poses_c2w: np.ndarray) -> np.ndarray:
    """c2w (N,4,4) → 카메라 월드 중심 (N,3)."""
    poses = np.asarray(poses_c2w, dtype=np.float64).reshape(-1, 4, 4)
    return poses[:, :3, 3]
