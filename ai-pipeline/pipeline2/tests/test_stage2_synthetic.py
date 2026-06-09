"""Stage 2 합성 데이터 검증.

기울어진 지면 + 노이즈 + 원거리 outlier + 지면 위 카메라를 만들어
정렬 후 (1) 지면 Y≈0, (2) 카메라 Y>0, (3) outlier 제거를 확인.
실행: conda run -n 3dgs_pipeline python tests/test_stage2_synthetic.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common import geometry as geo
from common import logio
from stages import stage2_preprocess as s2


def _make_scene(rng):
    # --- 기울어진 지면 (원래 XZ 평면을 임의 회전) ---
    gx, gz = np.meshgrid(np.linspace(-5, 5, 120), np.linspace(-5, 5, 120))
    ground = np.stack([gx.ravel(), np.zeros(gx.size), gz.ravel()], axis=1)
    ground += rng.normal(0, 0.01, ground.shape)  # 얇은 두께
    # 지면 위 구조물(벽) 약간
    wall = np.stack([
        np.full(400, 4.0),
        rng.uniform(0, 2, 400),
        rng.uniform(-5, 5, 400),
    ], axis=1)
    pts = np.vstack([ground, wall])

    # 임의 회전 + 평행이동으로 '월드'를 기울임
    angle = np.deg2rad(20)
    axis = np.array([0.3, 0.2, 1.0]); axis /= np.linalg.norm(axis)
    K = geo._skew(axis)
    R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)
    offset = np.array([2.0, 3.0, -1.0])
    pts_world = pts @ R.T + offset

    # --- 카메라: 지면 위 1.5m, 경로 ---
    cam_local = np.stack([
        np.linspace(-3, 3, 12),
        np.full(12, 1.5),
        np.zeros(12),
    ], axis=1)
    cam_world = cam_local @ R.T + offset
    poses = np.tile(np.eye(4), (12, 1, 1))
    poses[:, :3, :3] = R
    poses[:, :3, 3] = cam_world

    # --- 원거리 outlier (제거 대상) ---
    outliers = rng.uniform(-50, 50, (300, 3))
    pts_all = np.vstack([pts_world, outliers])
    colors = rng.uniform(0.2, 0.9, (len(pts_all), 3))

    return pts_all, colors, poses, R, offset


def main():
    rng = np.random.default_rng(0)
    pts, colors, poses, R, offset = _make_scene(rng)

    tmp = Path(tempfile.mkdtemp(prefix="s2test_"))
    in_ply = tmp / "in.ply"
    in_poses = tmp / "poses.json"
    logio.write_ply_numpy(in_ply, pts, colors)
    logio.write_poses_json(in_poses, poses, {"fx": 500, "fy": 500, "cx": 256, "cy": 256, "width": 512, "height": 512})

    cfg = {
        "sor": {"enabled": True, "nb_neighbors": 30, "std_ratio": 2.0},
        "radius": {"enabled": True, "nb_points": 8, "radius": 0.5},
        "voxel": {"enabled": True, "voxel_size": 0.05},
        "ground": {"enabled": True, "distance_threshold": 0.05, "ransac_n": 3,
                   "num_iterations": 2000, "up_from_cameras": True},
    }
    out = tmp / "out"
    res = s2.run(in_ply, in_poses, out, cfg)

    # --- 검증 ---
    clean = logio.read_ply(res["clean_ply"])
    cpts = np.asarray(clean.points)
    poses_aligned, _, _ = logio.read_poses_json(res["aligned_poses"])
    cam_y = poses_aligned[:, 1, 3]

    # 지면 점 = Y 가 0 근처에 모인 점들 (가장 낮은 밀도 대역)
    ground_mask = np.abs(cpts[:, 1]) < 0.1
    ground_frac = ground_mask.mean()

    print("\n===== 검증 =====")
    print(f"입력 {len(pts)} → 정제 {len(cpts)} pts (outlier 300개 포함 입력)")
    print(f"|Y|<0.1 지면대역 비율: {ground_frac:.2%}")
    print(f"카메라 Y: min={cam_y.min():.3f} max={cam_y.max():.3f} mean={cam_y.mean():.3f}")
    print(f"포인트 Y 범위: [{cpts[:,1].min():.3f}, {cpts[:,1].max():.3f}]")

    ok = True
    # 1) 멀리 있던 outlier 제거 → 좌표 범위가 합리적
    if np.abs(cpts).max() > 20:
        print("✗ outlier 가 남음 (|coord|>20)"); ok = False
    else:
        print("✓ 원거리 outlier 제거됨")
    # 2) 카메라가 지면 위 (Y>0), 1.5m 근처
    if cam_y.min() > 0.5 and abs(cam_y.mean() - 1.5) < 0.5:
        print("✓ 카메라가 지면 위 ~1.5m")
    else:
        print(f"✗ 카메라 높이 이상 (mean={cam_y.mean():.3f})"); ok = False
    # 3) 지면이 Y≈0 에 정렬
    if ground_frac > 0.3:
        print("✓ 지면이 Y≈0 에 정렬됨")
    else:
        print(f"✗ 지면 정렬 약함 (ground_frac={ground_frac:.2%})"); ok = False

    print("\n" + ("PASS ✅" if ok else "FAIL ❌"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
