"""Stage 3 검증: (1) c2w→w2c 쿼터니언 정확성, (2) 3DGS ply→.splat 바이너리.
실행: conda run -n 3dgs_pipeline python tests/test_stage3_splat.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stages import stage3_train as s3


def test_quaternion():
    from scipy.spatial.transform import Rotation
    rng = np.random.default_rng(1)
    max_err = 0.0
    for _ in range(200):
        R = Rotation.random(random_state=rng).as_matrix()
        q = s3._rotmat_to_qvec(R)                       # (w,x,y,z)
        R_back = Rotation.from_quat([q[1], q[2], q[3], q[0]]).as_matrix()
        max_err = max(max_err, np.abs(R - R_back).max())
    print(f"[quaternion] 최대 복원오차 = {max_err:.2e}")
    assert max_err < 1e-6, "쿼터니언 변환 오차 큼"
    return True


def test_splat_export():
    n = 5000
    rng = np.random.default_rng(2)
    # 3DGS point_cloud.ply 형식 합성 (필수 필드)
    from plyfile import PlyData, PlyElement
    fields = ["x", "y", "z", "nx", "ny", "nz",
              "f_dc_0", "f_dc_1", "f_dc_2",
              "opacity", "scale_0", "scale_1", "scale_2",
              "rot_0", "rot_1", "rot_2", "rot_3"]
    data = np.zeros(n, dtype=[(f, "f4") for f in fields])
    data["x"], data["y"], data["z"] = rng.normal(size=(3, n))
    for f in ["f_dc_0", "f_dc_1", "f_dc_2"]:
        data[f] = rng.uniform(-1, 1, n)
    data["opacity"] = rng.uniform(-3, 3, n)
    for f in ["scale_0", "scale_1", "scale_2"]:
        data[f] = rng.uniform(-6, -2, n)
    q = rng.normal(size=(n, 4)); q /= np.linalg.norm(q, axis=1, keepdims=True)
    data["rot_0"], data["rot_1"], data["rot_2"], data["rot_3"] = q.T

    tmp = Path(tempfile.mkdtemp(prefix="s3test_"))
    in_ply = tmp / "point_cloud.ply"
    PlyData([PlyElement.describe(data, "vertex")]).write(str(in_ply))

    out_splat = tmp / "out.splat"
    s3.export_splat(in_ply, out_splat, sort=True)

    size = out_splat.stat().st_size
    print(f"[splat] {n} gaussians → {size} bytes (기대 {n*32})")
    assert size == n * 32, "splat 크기 != n*32"

    # 첫 가우시안 디코드 검증 (가장 중요도 높은 것)
    raw = np.frombuffer(out_splat.read_bytes(), dtype=np.uint8).reshape(n, 32)
    pos = raw[:, 0:12].view("<f4").reshape(n, 3)
    scale = raw[:, 12:24].view("<f4").reshape(n, 3)
    rgba = raw[:, 24:28]
    rot = raw[:, 28:32]
    assert np.isfinite(pos).all() and (scale > 0).all(), "pos/scale 이상"
    assert rgba.shape == (n, 4) and rot.shape == (n, 4)
    print(f"[splat] pos범위 {pos.min():.2f}~{pos.max():.2f}, "
          f"scale범위 {scale.min():.4f}~{scale.max():.4f}, "
          f"alpha평균 {rgba[:,3].mean():.1f}")
    return True


if __name__ == "__main__":
    ok = True
    try:
        test_quaternion()
        print("✓ 쿼터니언 PASS")
    except Exception as e:
        print(f"✗ 쿼터니언 FAIL: {e}"); ok = False
    try:
        test_splat_export()
        print("✓ splat export PASS")
    except Exception as e:
        print(f"✗ splat FAIL: {e}"); ok = False
    print("\n" + ("ALL PASS ✅" if ok else "FAIL ❌"))
    sys.exit(0 if ok else 1)
