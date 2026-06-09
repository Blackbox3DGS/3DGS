"""오케스트레이션 통합 검증 (LingBot/학습 제외).

합성 Stage1 산출물(ply+poses+images)을 만들고
run.py --stages 2,3,4 --skip_train 을 구동해 전체 연결을 확인.
실행: conda run -n 3dgs_pipeline python tests/test_pipeline_integration.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import logio, geometry as geo  # noqa: E402


def make_stage1_outputs(s1: Path, n_frames=10):
    s1.mkdir(parents=True, exist_ok=True)
    import cv2
    rng = np.random.default_rng(3)
    # 기울어진 지면 + 벽
    gx, gz = np.meshgrid(np.linspace(-4, 4, 80), np.linspace(-4, 4, 80))
    ground = np.stack([gx.ravel(), np.zeros(gx.size), gz.ravel()], 1)
    pts = np.vstack([ground, np.column_stack([np.full(300, 3.0), rng.uniform(0, 2, 300), rng.uniform(-4, 4, 300)])])
    angle = np.deg2rad(15); axis = np.array([0.2, 0.1, 1.0]); axis /= np.linalg.norm(axis)
    K = geo._skew(axis); R = np.eye(3) + np.sin(angle)*K + (1-np.cos(angle))*(K@K)
    off = np.array([1.0, 2.0, 0.5])
    pts_w = pts @ R.T + off
    pts_w = np.vstack([pts_w, rng.uniform(-30, 30, (200, 3))])  # outliers
    cols = rng.uniform(0.2, 0.9, (len(pts_w), 3))
    logio.write_ply_numpy(s1 / "point_cloud.ply", pts_w, cols)

    cam = np.stack([np.linspace(-2, 2, n_frames), np.full(n_frames, 1.5), np.zeros(n_frames)], 1) @ R.T + off
    poses = np.tile(np.eye(4), (n_frames, 1, 1)); poses[:, :3, :3] = R; poses[:, :3, 3] = cam
    names = [f"{i:06d}.jpg" for i in range(n_frames)]
    logio.write_poses_json(s1 / "camera_poses.json", poses,
                           {"fx": 400, "fy": 400, "cx": 256, "cy": 192, "width": 512, "height": 384}, names)
    img_dir = s1 / "images"; img_dir.mkdir(exist_ok=True)
    for nm in names:
        cv2.imwrite(str(img_dir / nm), (rng.uniform(0, 255, (384, 512, 3))).astype(np.uint8))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="p2_intg_"))
    make_stage1_outputs(tmp / "01_mapping")

    cmd = [sys.executable, str(ROOT / "run.py"),
           "--out_root", str(tmp), "--stages", "2,3,4", "--skip_train",
           "--config", str(ROOT / "config.yaml")]
    print("실행:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout[-1500:])
    if r.returncode != 0:
        print("STDERR:\n", r.stderr[-2000:]); print("FAIL ❌"); sys.exit(1)

    checks = {
        "Stage2 clean ply": tmp / "02_preprocess/point_cloud_clean.ply",
        "Stage2 aligned poses": tmp / "02_preprocess/camera_poses_aligned.json",
        "Stage2 transform": tmp / "02_preprocess/transform.json",
        "Stage3 cameras.txt": tmp / "03_3dgs/colmap/sparse/0/cameras.txt",
        "Stage3 images.txt": tmp / "03_3dgs/colmap/sparse/0/images.txt",
        "Stage3 points3D.txt": tmp / "03_3dgs/colmap/sparse/0/points3D.txt",
        "Stage3 colmap images": tmp / "03_3dgs/colmap/images",
        "Stage4 index.html": tmp / "04_viewer/viewer/index.html",
        "Stage4 config.json": tmp / "04_viewer/viewer/config.json",
        "Stage4 poses copied": tmp / "04_viewer/viewer/camera_poses.json",
    }
    ok = True
    print("\n===== 산출물 점검 =====")
    for name, p in checks.items():
        exists = p.exists()
        print(f"{'✓' if exists else '✗'} {name}: {p.relative_to(tmp)}")
        ok &= exists

    # COLMAP images.txt 줄 수 = 프레임 수 검증
    img_txt = (tmp / "03_3dgs/colmap/sparse/0/images.txt").read_text().splitlines()
    data_lines = [l for l in img_txt if l and not l.startswith("#")]
    n_cam = len([l for l in data_lines if l.strip()])  # 빈 track 줄 포함 처리
    print(f"images.txt 데이터 줄(빈줄 제외): {len(data_lines)}")

    # 정렬 검증: aligned poses 의 카메라 Y > 0
    poses_a, _, _ = logio.read_poses_json(tmp / "02_preprocess/camera_poses_aligned.json")
    cam_y = poses_a[:, 1, 3]
    print(f"정렬 후 카메라 Y: min={cam_y.min():.3f} mean={cam_y.mean():.3f}")
    if not (cam_y.min() > 0.3):
        print("✗ 카메라가 지면 위로 정렬되지 않음"); ok = False
    else:
        print("✓ 카메라 지면 위 정렬 확인")

    print("\n" + ("INTEGRATION PASS ✅" if ok else "FAIL ❌"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
