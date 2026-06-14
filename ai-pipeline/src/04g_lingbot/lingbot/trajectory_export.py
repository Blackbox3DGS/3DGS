"""Export ego + dynamic-vehicle 3D trajectories from LingBot predictions.

Produces a `vehicles.json` in the SAME frame as the background .splat written by
`splat_export.predictions_to_splat` (apply its returned R + center), so the web
viewer can overlay 3D car models on the point-cloud background.

Vehicle trajectories use the Stage-09 method at LingBot's processed resolution:
per dynamic track, per frame, take the lower-40% of the bbox ∩ dynamic-mask ROI,
sample the P20–P30 depth percentile (rear-bumper surface), and unproject
(u, v, depth) to world via the per-frame c2w + intrinsic. The ego (blackbox) car
is the camera centre path.

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

# Stage-09 sampling params.
LOWER_FRAC = 0.40
PCT_LOW = 20.0
PCT_HIGH = 30.0
MIN_ROI_PIXELS = 20
MIN_PCT_PIXELS = 5


def _sample_track_frame(mask_img, depth_map, bbox, *,
                        lower_frac=LOWER_FRAC, pct_low=PCT_LOW, pct_high=PCT_HIGH,
                        min_roi_pixels=MIN_ROI_PIXELS, min_pct_pixels=MIN_PCT_PIXELS):
    """Robust (u, v, depth) from one track's ROI. None if too small."""
    H, W = depth_map.shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(W, int(x1))); y1 = max(0, min(H, int(y1)))
    x2 = max(0, min(W, int(x2))); y2 = max(0, min(H, int(y2)))
    if x2 <= x1 or y2 <= y1:
        return None
    bh = y2 - y1
    y_lower = y1 + int(round((1.0 - lower_frac) * bh))
    if y_lower >= y2:
        return None
    mask_crop = mask_img[y_lower:y2, x1:x2] > 127
    if not mask_crop.any():
        return None
    if int(mask_crop.sum()) < min_roi_pixels:
        return None
    depth_crop = depth_map[y_lower:y2, x1:x2]
    vs_local, us_local = np.nonzero(mask_crop)
    depths = depth_crop[vs_local, us_local]
    finite = np.isfinite(depths) & (depths > 0)
    if int(finite.sum()) < min_roi_pixels:
        return None
    vs_local, us_local, depths = vs_local[finite], us_local[finite], depths[finite]
    p_lo, p_hi = np.percentile(depths, [pct_low, pct_high])
    keep = (depths >= p_lo) & (depths <= p_hi)
    if int(keep.sum()) < min_pct_pixels:
        return None
    u = float(np.median(us_local[keep])) + x1
    v = float(np.median(vs_local[keep])) + y_lower
    d = float(np.median(depths[keep]))
    return u, v, d


def _pixel_to_world(u, v, depth, c2w, fx, fy, cx, cy):
    """Unproject one pixel to world coords (c2w is 4x4)."""
    x = (u - cx) / fx * depth
    y = (v - cy) / fy * depth
    pt_cam = np.array([x, y, depth, 1.0], dtype=np.float64)
    pw = c2w @ pt_cam
    return float(pw[0]), float(pw[1]), float(pw[2])


def _ray_ground_intersect(origin, dir_world, n, p0):
    """Intersect a camera ray with the ground plane n·(P-p0)=0. None if behind/parallel.

    More reliable than surface depth for ordering ground vehicles: the contact
    point distance is monotonic in the bbox-bottom image row, so front/back order
    is preserved even when monocular depth is noisy.
    """
    denom = float(n @ dir_world)
    if abs(denom) < 1e-9:
        return None
    t = float(n @ (p0 - origin)) / denom
    if t <= 0:
        return None
    return origin + t * dir_world


def export_trajectories_json(
    predictions: dict,
    out_path: str,
    *,
    frame_paths: list,
    center=None,
    R=None,
    bbox_sequence_path=None,
    dynamic_mask_dir=None,
    ground_normal=None,
    ground_point=None,
) -> str:
    """Write vehicles.json (ego + dynamic tracks) in the background's frame.

    `predictions` needs depth (S,H,W[,1]), extrinsic (S,3,4 c2w), intrinsic
    (S,3,3 at processed res). Apply the SAME (R, center) as the .splat export.
    """
    depth = np.asarray(predictions["depth"])
    if depth.ndim == 4:
        depth = depth[..., 0]
    extr = np.asarray(predictions["extrinsic"], dtype=np.float64)
    intr = np.asarray(predictions["intrinsic"], dtype=np.float64)
    S, H_p, W_p = depth.shape
    shift = np.zeros(3, dtype=np.float64) if center is None else np.asarray(center, dtype=np.float64)
    Rm = np.eye(3) if R is None else np.asarray(R, dtype=np.float64)

    def _xform(p):
        q = Rm @ np.asarray(p, dtype=np.float64) - shift
        return [float(q[0]), float(q[1]), float(q[2])]

    c2w4 = np.tile(np.eye(4), (S, 1, 1))
    c2w4[:, :3, :4] = extr

    vehicles = []

    # Ego (blackbox) car = camera centre path.
    ego_pts = []
    for i in range(S):
        x, y, z = _xform(c2w4[i, :3, 3])
        ego_pts.append([x, y, z, i])
    if ego_pts:
        vehicles.append({"id": "ego", "class": "ego", "points": ego_pts})

    # Dynamic vehicles from Stage-03 bbox_sequence.
    if bbox_sequence_path and os.path.exists(bbox_sequence_path):
        with open(bbox_sequence_path) as f:
            bseq = json.load(f)
        tracks = bseq.get("tracks", {})
        dyn_ids = set(str(t) for t in bseq.get("metadata", {}).get("dynamic_track_ids", []))
        if not dyn_ids:
            dyn_ids = {tid for tid, t in tracks.items()
                       if t.get("state") == "dynamic" and tid != "-1"}

        # Preferred: ground-plane ray intersection (correct front/back ordering).
        use_ground = ground_normal is not None and ground_point is not None
        gN = np.asarray(ground_normal, dtype=np.float64) if use_ground else None
        gP = np.asarray(ground_point, dtype=np.float64) if use_ground else None
        print(f"Dynamic vehicle placement: {'ground-ray' if use_ground else 'surface-depth'}")

        # Original frame resolution (bbox -> processed-intrinsic scaling).
        H_o = W_o = None
        if frame_paths:
            im0 = cv2.imread(str(frame_paths[0]))
            if im0 is not None:
                H_o, W_o = im0.shape[:2]
        mdir = Path(dynamic_mask_dir) if dynamic_mask_dir else None

        per_track = {tid: [] for tid in dyn_ids}
        for i in range(S):
            if H_o is None or i >= len(frame_paths):
                break
            sx, sy = W_p / float(W_o), H_p / float(H_o)
            fx, fy = intr[i, 0, 0], intr[i, 1, 1]
            cx, cy = intr[i, 0, 2], intr[i, 1, 2]
            origin = c2w4[i, :3, 3]
            Rc = c2w4[i, :3, :3]

            # Surface-depth fallback needs the per-frame mask.
            mask_i = None
            if not use_ground and mdir is not None:
                stem = Path(frame_paths[i]).stem
                for ext in (".png", ".jpg"):
                    cand = mdir / f"{stem}{ext}"
                    if cand.exists():
                        mm = cv2.imread(str(cand), cv2.IMREAD_GRAYSCALE)
                        if mm is not None:
                            if mm.shape[0] != H_p or mm.shape[1] != W_p:
                                mm = cv2.resize(mm, (W_p, H_p), interpolation=cv2.INTER_NEAREST)
                            mask_i = mm
                        break

            for tid in dyn_ids:
                fr = tracks.get(tid, {}).get("frames", {}).get(str(i))
                if fr is None:
                    continue
                bx = fr["bbox"]  # original-res [x1,y1,x2,y2]
                if use_ground:
                    # bbox 바닥중심(접지점) → 광선 → 도로평면 교차
                    u = 0.5 * (bx[0] + bx[2]) * sx
                    v = bx[3] * sy
                    dir_cam = np.array([(u - cx) / fx, (v - cy) / fy, 1.0], dtype=np.float64)
                    P = _ray_ground_intersect(origin, Rc @ dir_cam, gN, gP)
                    if P is None:
                        continue
                    x, y, z = _xform(P)
                    per_track[tid].append([x, y, z, i])
                else:
                    if mask_i is None:
                        continue
                    bbox_p = (bx[0] * sx, bx[1] * sy, bx[2] * sx, bx[3] * sy)
                    s = _sample_track_frame(mask_i, depth[i], bbox_p)
                    if s is None:
                        continue
                    uu, vv, dd = s
                    wx, wy, wz = _pixel_to_world(uu, vv, dd, c2w4[i], fx, fy, cx, cy)
                    x, y, z = _xform((wx, wy, wz))
                    per_track[tid].append([x, y, z, i])

        for tid in sorted(per_track, key=lambda s: int(s)):
            pts = per_track[tid]
            if len(pts) >= 2:
                cls = tracks.get(tid, {}).get("class_name", "car")
                vehicles.append({"id": str(tid), "class": cls, "points": pts})

    payload = {
        "coord_system": "lingbot-native, ground-aligned + recentered (same frame as background.splat)",
        "note": "points are [x, y, z, frame_idx]; 'ego' is the blackbox camera path",
        "vehicles": vehicles,
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f)

    n_dyn = sum(1 for v in vehicles if v["id"] != "ego")
    print(f"Wrote {out_path}: {len(vehicles)} vehicles (ego + {n_dyn} dynamic)")
    return out_path
