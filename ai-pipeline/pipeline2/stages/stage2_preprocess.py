"""Stage 2 — 전처리: 빡센 노이즈 제거 + 지면 기준 축 보정.

입력 (Stage 1 산출물):
    <in_ply>     point_cloud.ply        (XYZ + RGB, 월드좌표)
    <in_poses>   camera_poses.json      (c2w 4x4)

처리:
    1) Statistical Outlier Removal   (nb_neighbors, std_ratio)
    2) Radius Outlier Removal        (nb_points, radius)
    3) Voxel Downsampling            (voxel_size)
    4) RANSAC 지면 평면 → Y=0 정렬   (포인트 + 카메라 포즈 동일 변환)

출력:
    <out_dir>/point_cloud_clean.ply
    <out_dir>/camera_poses_aligned.json
    <out_dir>/transform.json          (적용한 4x4 T)
    <out_dir>/preview_topdown.png     (선택)

실행 환경: conda env `3dgs_pipeline` (open3d 0.19).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

# pipeline2 루트를 path 에 추가 (standalone 실행 대비)
_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from common import geometry as geo  # noqa: E402
from common import logio  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 필터 단계
# ---------------------------------------------------------------------------
def _statistical_outlier_removal(pcd, nb_neighbors: int, std_ratio: float):
    import open3d as o3d  # noqa: F401

    before = len(pcd.points)
    pcd_f, _ = pcd.remove_statistical_outlier(
        nb_neighbors=nb_neighbors, std_ratio=std_ratio
    )
    logger.info("SOR: %d → %d (제거 %d)", before, len(pcd_f.points), before - len(pcd_f.points))
    return pcd_f


def _radius_outlier_removal(pcd, nb_points: int, radius: float):
    before = len(pcd.points)
    pcd_f, _ = pcd.remove_radius_outlier(nb_points=nb_points, radius=radius)
    logger.info("Radius: %d → %d (제거 %d)", before, len(pcd_f.points), before - len(pcd_f.points))
    return pcd_f


def _voxel_downsample(pcd, voxel_size: float):
    before = len(pcd.points)
    pcd_d = pcd.voxel_down_sample(voxel_size=voxel_size)
    logger.info("Voxel(%.3f): %d → %d", voxel_size, before, len(pcd_d.points))
    return pcd_d


def _crop_far_from_cameras(pcd, cam_centers: np.ndarray, max_dist: float):
    """가장 가까운 카메라까지 거리가 max_dist 초과인 점 제거 (먼 노이즈/하늘 streak 컷)."""
    from scipy.spatial import cKDTree
    pts = np.asarray(pcd.points)
    if len(pts) == 0 or cam_centers is None or len(cam_centers) == 0:
        return pcd
    tree = cKDTree(cam_centers)
    dist, _ = tree.query(pts, k=1)
    keep = dist <= max_dist
    before = len(pts)
    pcd_c = pcd.select_by_index(np.where(keep)[0])
    logger.info("Camera-crop(<%.1fm): %d → %d (제거 %d)",
                max_dist, before, len(pcd_c.points), before - int(keep.sum()))
    return pcd_c


# ---------------------------------------------------------------------------
# 메인 처리
# ---------------------------------------------------------------------------
def run(in_ply: Path, in_poses: Path, out_dir: Path, cfg: dict) -> dict:
    """전처리 실행. 반환: 산출물 경로 dict."""
    import open3d as o3d

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pcd = logio.read_ply(in_ply)
    n0 = len(pcd.points)
    if n0 == 0:
        raise RuntimeError(f"입력 포인트클라우드가 비어있음: {in_ply}")
    logger.info("입력 포인트: %d (%s)", n0, in_ply)

    # 포즈 로드 (없어도 정렬은 +Y 가정으로 진행)
    poses_c2w = None
    intrinsics, names = {}, None
    if in_poses and Path(in_poses).exists():
        poses_c2w, intrinsics, names = logio.read_poses_json(in_poses)
        logger.info("포즈 로드: %d", len(poses_c2w))
    else:
        logger.warning("포즈 파일 없음 → 카메라 기반 up 추정 불가, +Y 가정 사용: %s", in_poses)

    # 순서: Voxel → SOR → Radius
    # (원래 스펙은 SOR→Radius→Voxel 이지만, SOR/Radius 의 이웃탐색이 O(N·k) 라
    #  수백만 포인트에선 수 시간 소요. 먼저 Voxel 로 줄인 뒤 필터링하면 ~100배 빠르고
    #  품질은 거의 동일 — voxel 은 점별 독립이라 outlier 에 거의 영향 안 받음.)

    # --- 1) Voxel ---
    if cfg.get("voxel", {}).get("enabled", True):
        v = cfg["voxel"]
        pcd = _voxel_downsample(pcd, v["voxel_size"])

    # --- 2) SOR ---
    if cfg.get("sor", {}).get("enabled", True):
        s = cfg["sor"]
        pcd = _statistical_outlier_removal(pcd, s["nb_neighbors"], s["std_ratio"])

    # --- 3) Radius ---
    if cfg.get("radius", {}).get("enabled", True):
        r = cfg["radius"]
        pcd = _radius_outlier_removal(pcd, r["nb_points"], r["radius"])

    # --- 4) 카메라 거리 크롭 (먼 노이즈/하늘 streak 제거) ---
    ccfg = cfg.get("crop", {})
    if ccfg.get("enabled", False) and poses_c2w is not None:
        pcd = _crop_far_from_cameras(
            pcd, geo.camera_centers(poses_c2w),
            ccfg.get("max_dist_from_camera", 15.0),
        )

    if len(pcd.points) == 0:
        raise RuntimeError("필터 후 포인트가 0개. 파라미터를 완화하세요.")

    # --- 5) 지면 정렬 ---
    T = np.eye(4)
    gcfg = cfg.get("ground", {})
    if gcfg.get("enabled", True):
        pts = np.asarray(pcd.points)
        plane_model, inlier_idx = geo.fit_ground_plane(
            pts,
            distance_threshold=gcfg.get("distance_threshold", 0.05),
            ransac_n=gcfg.get("ransac_n", 3),
            num_iterations=gcfg.get("num_iterations", 2000),
        )
        cam_centers = (
            geo.camera_centers(poses_c2w)
            if (poses_c2w is not None and gcfg.get("up_from_cameras", True))
            else None
        )
        T = geo.ground_alignment_transform(
            plane_model,
            cam_centers=cam_centers,
            ground_points=pts[inlier_idx],
        )
        # 포인트 변환
        pcd.points = o3d.utility.Vector3dVector(geo.apply_transform_points(pts, T))
        # 포즈 변환
        if poses_c2w is not None:
            poses_c2w = geo.apply_transform_poses(poses_c2w, T)

    # --- 저장 ---
    out_ply = out_dir / "point_cloud_clean.ply"
    logio.write_ply(pcd, out_ply)

    out_poses = out_dir / "camera_poses_aligned.json"
    if poses_c2w is not None:
        logio.write_poses_json(out_poses, poses_c2w, intrinsics, names)

    out_T = out_dir / "transform.json"
    with open(out_T, "w", encoding="utf-8") as f:
        json.dump({"transform_matrix": T.tolist(), "note": "ground→Y=0 align, applied to points & poses"}, f, indent=2)

    # --- 미리보기 (실패해도 무시) ---
    preview = out_dir / "preview_topdown.png"
    try:
        _save_topdown(np.asarray(pcd.points), np.asarray(pcd.colors), preview,
                      cam_centers=geo.camera_centers(poses_c2w) if poses_c2w is not None else None)
    except Exception as e:  # pragma: no cover
        logger.warning("미리보기 생성 실패(무시): %s", e)
        preview = None

    logger.info("Stage 2 완료: %d pts → %s", len(pcd.points), out_ply)
    return {
        "clean_ply": str(out_ply),
        "aligned_poses": str(out_poses) if poses_c2w is not None else None,
        "transform": str(out_T),
        "preview": str(preview) if preview else None,
        "num_points": len(pcd.points),
    }


def _save_topdown(points, colors, path, cam_centers=None):
    """XZ 평면 top-down 산점도 (Y 가 높이)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 8), dpi=100)
    c = colors if (colors is not None and len(colors) == len(points)) else None
    ax.scatter(points[:, 0], points[:, 2], s=0.3, c=c, marker=".", linewidths=0)
    if cam_centers is not None and len(cam_centers) > 0:
        ax.plot(cam_centers[:, 0], cam_centers[:, 2], "-", color="red", linewidth=1.5, label="camera path")
        ax.legend()
    ax.set_xlabel("X"); ax.set_ylabel("Z")
    ax.set_title("Top-down (Y=up, ground aligned)")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    logger.info("미리보기 저장 → %s", path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Stage 2: 전처리(노이즈 제거 + 지면 정렬)")
    ap.add_argument("--in_ply", required=True)
    ap.add_argument("--in_poses", default=None)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--config", required=True, help="config.yaml 경로")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    logio.setup_logging(out_dir, name="stage2")
    cfg = logio.load_config(args.config)["stage2_preprocess"]

    result = run(Path(args.in_ply),
                 Path(args.in_poses) if args.in_poses else None,
                 out_dir, cfg)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
