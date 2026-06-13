"""Stage 12: deploy a self-contained web viewer for one pipeline run.

Copies the static viewer template (`static/`) into the run's output dir and
drops the run-specific artifacts (Gaussian .splat background, vehicle
trajectories, optional camera path) into `data/` next to it. Open
`out_root/12_viewer/index.html` via any static HTTP server to see the result.
"""

from __future__ import annotations

import json
import logging
import shutil
import traceback
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _build_vehicles_json(trajectories_path: Path | None,
                         poses_path: Path | None) -> dict:
    """Adapt Stage 09 trajectories.json + camera poses into a flat, frontend-ready
    structure.

    The React viewer (Viewer3D.tsx) parses per-vehicle point arrays of the form
    [x, y, z, t] — it cannot read Stage 09's nested {tracks: {tid: {points:
    [{xyz: [...]}]}}}. This converts each track to {id, class, points:[[x,y,z,
    frame_idx], ...]} and adds the ego (blackbox) camera as a synthetic vehicle
    derived from the camera centres poses[:, :3, 3]. All coordinates stay in the
    same world frame as background.splat so overlays and splat align.
    """
    vehicles: list[dict] = []

    # Ego (blackbox) car follows the camera trajectory.
    if poses_path and poses_path.exists():
        poses = np.load(poses_path)  # (S, 4, 4)
        ego_pts = [[float(x), float(y), float(z), i]
                   for i, (x, y, z) in enumerate(poses[:, :3, 3])]
        if ego_pts:
            vehicles.append({"id": "ego", "class": "ego", "points": ego_pts})

    # Dynamic vehicles from Stage 09.
    if trajectories_path and trajectories_path.exists():
        with open(trajectories_path) as f:
            traj = json.load(f)
        for tid, tinfo in traj.get("tracks", {}).items():
            pts = []
            for p in tinfo.get("points", []):
                xyz = p.get("xyz")
                if not xyz or len(xyz) < 3:
                    continue
                pts.append([float(xyz[0]), float(xyz[1]), float(xyz[2]),
                            int(p.get("frame_idx", len(pts)))])
            if pts:
                vehicles.append({
                    "id": str(tid),
                    "class": tinfo.get("class_name", "car"),
                    "points": pts,
                })

    return {
        "coord_system": "world (same frame as background.splat)",
        "note": "points are [x, y, z, frame_idx]; 'ego' is the blackbox camera path",
        "vehicles": vehicles,
    }


def run(context: dict) -> dict:
    """Stage 12 entry point."""
    try:
        return _run_impl(context)
    except Exception:
        logger.error("Stage 12 failed:\n%s", traceback.format_exc())
        raise


def _run_impl(context: dict) -> dict:
    out_root = Path(context["out_root"])
    workspace = out_root / "12_viewer"
    workspace.mkdir(parents=True, exist_ok=True)
    data_dir = workspace / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy the static viewer template (index.html + JS modules + model assets).
    if not _STATIC_DIR.is_dir():
        raise RuntimeError(f"Viewer template missing: {_STATIC_DIR}")
    for src in _STATIC_DIR.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(_STATIC_DIR)
        dst = workspace / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    logger.info("Viewer template deployed -> %s", workspace)

    # 2. Drop run artifacts into data/.
    artifacts = context["artifacts"]
    copied = []

    splat_src = artifacts.get("output_splat")
    if splat_src and Path(splat_src).exists():
        shutil.copy(splat_src, data_dir / "background.splat")
        copied.append("background.splat")
    else:
        logger.warning("Stage 12: output_splat artifact missing — viewer will have no background.")

    traj_src = artifacts.get("trajectories")
    if traj_src and Path(traj_src).exists():
        shutil.copy(traj_src, data_dir / "trajectories.json")
        copied.append("trajectories.json")
    else:
        logger.warning("Stage 12: trajectories artifact missing — no vehicle meshes will animate.")

    bbox_src = artifacts.get("bbox_sequence")
    if bbox_src and Path(bbox_src).exists():
        shutil.copy(bbox_src, data_dir / "bbox_sequence.json")
        copied.append("bbox_sequence.json")

    # 3. Emit camera path as a flat JSON for the viewer to draw as a polyline.
    poses_src = artifacts.get("poses")
    if poses_src and Path(poses_src).exists():
        poses = np.load(poses_src)
        cam_path = poses[:, :3, 3].tolist()  # (S, 3)
        with open(data_dir / "camera_path.json", "w") as f:
            json.dump({"positions": cam_path}, f)
        copied.append("camera_path.json")

    # 4. Frontend-ready vehicles.json (per-vehicle [x,y,z,frame_idx] arrays +
    #    ego blackbox path). This is what the React Viewer3D / backend serves;
    #    trajectories.json (raw Stage 09) is kept alongside for debugging.
    traj_path = Path(traj_src) if traj_src else None
    poses_path = Path(poses_src) if poses_src else None
    vehicles = _build_vehicles_json(traj_path, poses_path)
    with open(data_dir / "vehicles.json", "w") as f:
        json.dump(vehicles, f)
    copied.append("vehicles.json")
    logger.info("vehicles.json: %d vehicles (incl. ego=%s)",
                len(vehicles["vehicles"]),
                any(v["id"] == "ego" for v in vehicles["vehicles"]))

    # 5. Manifest so the viewer can self-describe what data exists.
    manifest = {
        "run_id": out_root.name,
        "files": copied,
        "vehicle_model": "models/car.glb",  # placeholder — user supplies asset
        "ego_model": "models/car.glb",      # blackbox car follows camera path
    }
    with open(data_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Stage 12 complete: data files = %s", copied)
    logger.info("Serve with:  cd %s && python3 -m http.server 8000", workspace)

    context["artifacts"]["viewer_dir"] = str(workspace)
    return context
