"""Export ego + dynamic-vehicle 3D trajectories from LingBot predictions.

Produces a `vehicles.json` in the SAME frame as the background .splat written by
`splat_export.predictions_to_splat` (apply its returned R + center), so the web
viewer can overlay 3D car models on the point-cloud background.

Dynamic-vehicle placement uses **ego-motion-aligned inverse perspective mapping
(IPM)** rather than the reconstructed camera rotation. LingBot's forward-driving
poses have unreliable yaw — the optical axis can come out anti-parallel to the
direction of travel — which (with a ground-ray or surface-depth method) drops
vehicles on the wrong side of the ego, so a lead car ends up behind it. IPM
instead relies only on signals that ARE reliable for this footage:

    * the smooth ego camera *path* (translation), and its motion direction;
    * the +Y ground alignment (road plane, cars upright);
    * each track's bbox-bottom image row.

A vehicle higher in the image (smaller v, nearer the horizon) is placed farther
ahead along the ego's motion direction — monotonic in v, so front/back ordering
is guaranteed. Lateral (lane) offset is approximate (monocular limit). The ego
(blackbox) car is the camera-centre path.

Output (matches 3DGS Stage-12 vehicles.json):
    {"vehicles": [{"id": "ego", "class": "ego", "points": [[x,y,z,frame_idx], ...]},
                  {"id": "15", "class": "car", "points": [...]}, ...]}
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import cv2
import numpy as np

# Horizon is taken at the principal point (dashcam assumed roughly level). A
# bbox bottom must be at least this far below the horizon to count as ground.
MIN_BELOW_HORIZON_PX = 1.0
# Forward distance D = h*fy/(v-cy) blows up (and jitters) as the bbox bottom
# approaches the horizon. Clamp (v-cy) to at least this fraction of the image
# height so far/near-horizon detections don't produce wiggly trajectories.
HORIZON_FLOOR_FRAC = 0.02
# Centered moving-average window (frames) for per-track xz smoothing.
SMOOTH_WIN = 5


def _smooth_xz(pts: list, win: int = SMOOTH_WIN) -> list:
    """Centered moving-average on the x,z of a track's [x,y,z,frame] points.

    Tames residual per-frame jitter (bbox-bottom noise amplified by 1/(v-cy));
    y and frame_idx are left untouched.
    """
    if len(pts) < 3 or win < 2:
        return pts
    arr = np.asarray(pts, dtype=np.float64)
    half = win // 2
    out = arr.copy()
    for i in range(len(arr)):
        a = max(0, i - half)
        b = min(len(arr), i + half + 1)
        out[i, 0] = arr[a:b, 0].mean()
        out[i, 2] = arr[a:b, 2].mean()
    return [[float(p[0]), float(p[1]), float(p[2]), int(p[3])] for p in out]


def _smoothed_forward(centers: np.ndarray, up: np.ndarray, win: int = 5) -> np.ndarray:
    """Per-frame horizontal motion direction from the ego camera path.

    `centers` are the ego camera centres in the aligned frame (S, 3). Returns
    (S, 3) unit forward vectors projected onto the ground plane (perpendicular
    to `up`). Local motion is windowed for stability and forced to agree in sign
    with the global start->end direction, so per-frame jitter (the ego barely
    moves between frames) can't flip the forward axis.
    """
    S = len(centers)
    gnet = centers[-1] - centers[0]
    gnet = gnet - up * float(gnet @ up)
    gn = float(np.linalg.norm(gnet))
    gnet = gnet / gn if gn > 1e-9 else np.array([0.0, 0.0, -1.0])
    fwd = np.zeros((S, 3))
    for i in range(S):
        a = max(0, i - win)
        b = min(S - 1, i + win)
        d = centers[b] - centers[a]
        d = d - up * float(d @ up)
        n = float(np.linalg.norm(d))
        fi = d / n if n > 1e-6 else gnet
        if float(fi @ gnet) < 0:   # keep consistent with travel direction
            fi = gnet
        fwd[i] = fi
    return fwd


def export_trajectories_json(
    predictions: dict,
    out_path: str,
    *,
    frame_paths: list,
    center=None,
    R=None,
    bbox_sequence_path=None,
    dynamic_mask_dir=None,        # unused by IPM placement (kept for API compat)
    ground_normal=None,          # unused by IPM placement (kept for API compat)
    ground_point=None,
    up_axis=(0.0, 1.0, 0.0),
    max_forward_factor: float = 12.0,
) -> str:
    """Write vehicles.json (ego + dynamic tracks) in the background's frame.

    `predictions` needs extrinsic (S,3,4 c2w) + intrinsic (S,3,3 at processed
    res) + depth (S,H,W) for the processed resolution. Apply the SAME (R,
    center) as the .splat export so everything shares one ground-aligned,
    recentered frame.
    """
    extr = np.asarray(predictions["extrinsic"], dtype=np.float64)   # (S,3,4) c2w
    intr = np.asarray(predictions["intrinsic"], dtype=np.float64)   # (S,3,3) processed
    depth = np.asarray(predictions["depth"])
    if depth.ndim == 4:
        depth = depth[..., 0]
    S, H_p, W_p = depth.shape

    shift = np.zeros(3) if center is None else np.asarray(center, dtype=np.float64)
    Rm = np.eye(3) if R is None else np.asarray(R, dtype=np.float64)
    up = np.asarray(up_axis, dtype=np.float64)
    up = up / (np.linalg.norm(up) + 1e-12)

    # Ego camera centres in the aligned + recentered frame (same as the .splat:
    # p -> R @ p - center). Road plane is y ~= 0 after recenter, so the camera
    # height above the road is just the aligned centre's up-component.
    cam_native = extr[:, :3, 3]
    C = cam_native @ Rm.T - shift               # (S, 3)
    road_y = 0.0
    path_len = float(np.linalg.norm(C[-1] - C[0])) or 1.0
    max_forward = max_forward_factor * path_len

    vehicles = []
    ego_pts = [[float(C[i, 0]), float(C[i, 1]), float(C[i, 2]), i] for i in range(S)]
    if ego_pts:
        vehicles.append({"id": "ego", "class": "ego", "points": ego_pts})

    if bbox_sequence_path and os.path.exists(bbox_sequence_path):
        with open(bbox_sequence_path) as f:
            bseq = json.load(f)
        tracks = bseq.get("tracks", {})
        dyn_ids = set(str(t) for t in bseq.get("metadata", {}).get("dynamic_track_ids", []))
        if not dyn_ids:
            dyn_ids = {tid for tid, t in tracks.items()
                       if t.get("state") == "dynamic" and tid != "-1"}

        # Original frame resolution -> processed-intrinsic pixel scaling.
        H_o = W_o = None
        if frame_paths:
            im0 = cv2.imread(str(frame_paths[0]))
            if im0 is not None:
                H_o, W_o = im0.shape[:2]

        fwd = _smoothed_forward(C, up)
        print("Dynamic vehicle placement: ego-motion IPM")

        per_track = {tid: [] for tid in dyn_ids}
        for i in range(S):
            if H_o is None or i >= len(frame_paths):
                break
            sx, sy = W_p / float(W_o), H_p / float(H_o)
            fx, fy = intr[i, 0, 0], intr[i, 1, 1]
            cx, cy = intr[i, 0, 2], intr[i, 1, 2]
            f = fwd[i]
            r = np.cross(up, f)
            rn = float(np.linalg.norm(r))
            r = r / rn if rn > 1e-9 else np.array([1.0, 0.0, 0.0])
            h_cam = float(C[i, 1] - road_y)
            if h_cam <= 1e-6:
                continue

            for tid in dyn_ids:
                fr = tracks.get(tid, {}).get("frames", {}).get(str(i))
                if fr is None:
                    continue
                bx = fr["bbox"]                       # original-res [x1,y1,x2,y2]
                u = 0.5 * (bx[0] + bx[2]) * sx        # bbox bottom-centre (processed px)
                v = bx[3] * sy
                dv = v - cy                           # below horizon = on the road ahead
                if dv <= MIN_BELOW_HORIZON_PX:
                    continue                          # at/above horizon -> skip
                dv_eff = max(dv, HORIZON_FLOOR_FRAC * H_p)  # clamp near-horizon jitter
                D = min(h_cam * fy / dv_eff, max_forward)   # forward distance (monotonic in v)
                L = (u - cx) / fx * D                 # lateral offset
                P = C[i] + D * f + L * r              # on the road, ahead of the ego
                per_track[tid].append([float(P[0]), road_y, float(P[2]), i])

        for tid in sorted(per_track, key=lambda s: int(s)):
            pts = _smooth_xz(per_track[tid])
            if len(pts) >= 2:
                cls = tracks.get(tid, {}).get("class_name", "car")
                vehicles.append({"id": str(tid), "class": cls, "points": pts})

    payload = {
        "coord_system": "lingbot-native, ground-aligned + recentered (same frame as background.splat)",
        "note": "points are [x, y, z, frame_idx]; 'ego' is the blackbox camera path; "
                "dynamic vehicles placed via ego-motion IPM (order-accurate, distance approximate)",
        "vehicles": vehicles,
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f)

    n_dyn = sum(1 for v in vehicles if v["id"] != "ego")
    print(f"Wrote {out_path}: {len(vehicles)} vehicles (ego + {n_dyn} dynamic)")
    return out_path
