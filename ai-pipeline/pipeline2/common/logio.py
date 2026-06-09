"""공통: 설정 로딩, 로깅 설정, 산출물 I/O 헬퍼.

pipeline2 의 모든 stage 가 공유한다. 외부 의존성은 numpy 만 필수,
open3d 는 ply 헬퍼에서만 lazy import.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# repo 루트 = pipeline2/common/logio.py 기준 parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
def load_config(path: str | Path) -> dict:
    """YAML 설정 로드. pyyaml 미설치 시 명확한 에러."""
    try:
        import yaml
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "pyyaml 가 필요합니다: pip install pyyaml"
        ) from e
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg or {}


def resolve_path(p: str | Path) -> Path:
    """상대경로면 repo 루트 기준으로, 절대경로면 그대로 해석."""
    p = Path(p)
    return p if p.is_absolute() else (REPO_ROOT / p)


# ---------------------------------------------------------------------------
# 로깅
# ---------------------------------------------------------------------------
def setup_logging(out_dir: Path, name: str = "pipeline") -> None:
    """콘솔(INFO) + 파일(DEBUG) 핸들러 구성. 중복 호출 안전."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    # 기존 핸들러 제거(재실행 시 중복 방지)
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    out_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(out_dir / f"{name}.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)


# ---------------------------------------------------------------------------
# 포인트클라우드 I/O (open3d lazy import)
# ---------------------------------------------------------------------------
def read_ply(path: str | Path):
    """ply → open3d PointCloud."""
    import open3d as o3d

    pcd = o3d.io.read_point_cloud(str(path))
    if len(pcd.points) == 0:
        logger.warning("빈 포인트클라우드: %s", path)
    return pcd


def write_ply(pcd, path: str | Path) -> None:
    import open3d as o3d

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    o3d.io.write_point_cloud(str(path), pcd)
    logger.info("저장 %d pts → %s", len(pcd.points), path)


def write_ply_numpy(
    path: str | Path,
    points: np.ndarray,
    colors: np.ndarray | None = None,
) -> None:
    """open3d 없이 binary little-endian PLY 저장 (Stage 1, lingbot env 용).

    points: (N,3) float, colors: (N,3) 0~1 또는 0~255 (없으면 회색).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 3)
    n = len(pts)
    if colors is None:
        cols = np.full((n, 3), 180, dtype=np.uint8)
    else:
        c = np.asarray(colors, dtype=np.float32).reshape(-1, 3)
        if c.max() <= 1.0 + 1e-6:
            c = c * 255.0
        cols = np.clip(c, 0, 255).astype(np.uint8)

    # 구조화 배열로 묶어 한 번에 기록
    vert = np.empty(
        n,
        dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
               ("red", "u1"), ("green", "u1"), ("blue", "u1")],
    )
    vert["x"], vert["y"], vert["z"] = pts[:, 0], pts[:, 1], pts[:, 2]
    vert["red"], vert["green"], vert["blue"] = cols[:, 0], cols[:, 1], cols[:, 2]

    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {n}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    )
    with open(path, "wb") as f:
        f.write(header.encode("ascii"))
        f.write(vert.tobytes())
    logger.info("저장 %d pts → %s", n, path)


def points_to_pcd(points: np.ndarray, colors: np.ndarray | None = None):
    """(N,3) xyz [+ (N,3) rgb 0~1] → open3d PointCloud."""
    import open3d as o3d

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(np.asarray(points, dtype=np.float64))
    if colors is not None and len(colors) == len(points):
        c = np.asarray(colors, dtype=np.float64)
        if c.max() > 1.0 + 1e-6:  # 0~255 → 0~1
            c = c / 255.0
        pcd.colors = o3d.utility.Vector3dVector(c)
    return pcd


# ---------------------------------------------------------------------------
# 카메라 포즈 I/O
# ---------------------------------------------------------------------------
def write_poses_json(
    path: str | Path,
    poses_c2w: np.ndarray,
    intrinsics: dict[str, Any] | None = None,
    frame_names: list[str] | None = None,
) -> None:
    """카메라 포즈를 표준 JSON 으로 저장.

    스키마:
      {
        "convention": "c2w",      # camera-to-world 4x4
        "coordinate": "opencv",   # +x right, +y down, +z forward
        "intrinsics": {fx,fy,cx,cy,width,height},
        "frames": [{"name","transform_matrix"(4x4)}...]
      }
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    poses_c2w = np.asarray(poses_c2w, dtype=np.float64)
    n = len(poses_c2w)
    names = frame_names or [f"{i:06d}" for i in range(n)]
    frames = [
        {"name": names[i], "transform_matrix": poses_c2w[i].tolist()}
        for i in range(n)
    ]
    data = {
        "convention": "c2w",
        "coordinate": "opencv",
        "intrinsics": intrinsics or {},
        "frames": frames,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info("저장 %d poses → %s", n, path)


def read_poses_json(path: str | Path) -> tuple[np.ndarray, dict, list[str]]:
    """write_poses_json 으로 저장한 JSON 로드 → (poses_c2w (N,4,4), intrinsics, names)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    frames = data.get("frames", [])
    poses = np.array(
        [f["transform_matrix"] for f in frames], dtype=np.float64
    ).reshape(-1, 4, 4)
    names = [f.get("name", f"{i:06d}") for i, f in enumerate(frames)]
    return poses, data.get("intrinsics", {}), names
