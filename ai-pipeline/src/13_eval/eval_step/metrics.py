"""Quantitative accident-reconstruction metrics vs Waymo GT.

Implements the four advisor-requested metrics (지도보고서 2026-06-24):

  1. 차량 중심 위치 오차   — BEV position error of each dynamic vehicle,
                             with forward/lateral decomposition (IPM placement
                             is order-accurate but laterally approximate, so
                             the split is reported honestly)
  2. 상대거리 오차         — |est ego↔vehicle distance − GT distance|;
                             invariant to rotation/reflection/translation of
                             the alignment, hence the most trustworthy number
  3. 궤적 오차             — ADE / FDE per track
  4. 속도 추정 오차        — finite-difference est speed vs GT label speed
                             (`metadata.speed_x/y`), plus ego speed vs GT
                             camera-pose differences

Estimated dynamic points come from ego-motion IPM at the bbox *bottom centre*,
i.e. the rear (camera-facing) face on the ground — not the object centre. GT
centres are therefore also shifted to the camera-facing face of the GT box
("near-face") for the primary numbers; raw-centre errors are reported alongside.

All computation is numpy-only.
"""

from __future__ import annotations

import numpy as np

SPEED_SMOOTH_HALF = 2   # +-frames for finite-difference speed smoothing


# --------------------------------------------------------------------------
# GT accessors
# --------------------------------------------------------------------------

def gt_camera_positions(gt: dict) -> dict:
    """frame index -> FRONT camera position in the Waymo global frame (3,)."""
    ext = np.asarray(gt["camera_extrinsic"], dtype=np.float64)  # camera->vehicle
    cam_in_vehicle = ext[:3, 3]
    out = {}
    for fr in gt["frames"]:
        pose = np.asarray(fr["pose"], dtype=np.float64)         # vehicle->global
        out[fr["index"]] = pose[:3, :3] @ cam_in_vehicle + pose[:3, 3]
    return out


def gt_label_states(gt: dict, gt_id: str) -> dict:
    """frame index -> {center, near_face, speed_mps} for one GT object.

    `near_face` is the centre of the box face closest to the ego camera,
    projected on the box's heading axis (matches what IPM actually measures).
    """
    ext = np.asarray(gt["camera_extrinsic"], dtype=np.float64)
    cam_in_vehicle = ext[:3, 3]
    out = {}
    for fr in gt["frames"]:
        lab = next((l for l in fr["labels"] if l["id"] == gt_id), None)
        if lab is None:
            continue
        pose = np.asarray(fr["pose"], dtype=np.float64)
        R, t = pose[:3, :3], pose[:3, 3]

        center_v = np.asarray(lab["center"], dtype=np.float64)
        center_g = R @ center_v + t

        h = lab["heading"]
        axis_v = np.array([np.cos(h), np.sin(h), 0.0])
        axis_g = R @ axis_v
        half_l = lab["size"][0] / 2.0
        cam_g = R @ cam_in_vehicle + t
        f1 = center_g + half_l * axis_g
        f2 = center_g - half_l * axis_g
        near = f1 if np.linalg.norm(f1 - cam_g) < np.linalg.norm(f2 - cam_g) else f2

        out[fr["index"]] = {
            "center": center_g,
            "near_face": near,
            "speed_mps": float(np.hypot(lab["speed"][0], lab["speed"][1])),
        }
    return out


# --------------------------------------------------------------------------
# Estimated-side helpers
# --------------------------------------------------------------------------

def track_points_by_frame(vehicle: dict) -> dict:
    """vehicles.json entry -> {frame_idx: np.array([x,y,z])}."""
    return {int(p[3]): np.asarray(p[:3], dtype=np.float64) for p in vehicle["points"]}


def finite_diff_speed(frames: list, positions: np.ndarray, fps: float) -> dict:
    """frame -> speed (m/s) via central differences over already-metric coords."""
    out = {}
    n = len(frames)
    for i in range(n):
        a = max(0, i - SPEED_SMOOTH_HALF)
        b = min(n - 1, i + SPEED_SMOOTH_HALF)
        df = frames[b] - frames[a]
        if df <= 0:
            continue
        dist = float(np.linalg.norm(positions[b] - positions[a]))
        out[frames[i]] = dist / df * fps
    return out


def _ego_forward_xy(cam_by_frame: dict) -> dict:
    """frame -> unit forward direction of the ego in GT global BEV (xy)."""
    frames = sorted(cam_by_frame.keys())
    out = {}
    for i, f in enumerate(frames):
        a = frames[max(0, i - 2)]
        b = frames[min(len(frames) - 1, i + 2)]
        d = (cam_by_frame[b] - cam_by_frame[a])[:2]
        n = float(np.linalg.norm(d))
        out[f] = d / n if n > 1e-9 else np.array([1.0, 0.0])
    return out


# --------------------------------------------------------------------------
# Per-track metrics
# --------------------------------------------------------------------------

def evaluate_track(
    est_by_frame: dict,
    ego_by_frame: dict,
    gt_states: dict,
    cam_by_frame: dict,
    aligned_est: dict,
    fit_s: float,
    fps: float,
) -> dict:
    """Compute the four metric families for one matched track.

    est_by_frame / ego_by_frame: raw estimated coords (non-metric units)
    aligned_est: frame -> est point mapped into the GT global frame
    fit_s: Umeyama scale (units -> meters)
    """
    frames = sorted(set(est_by_frame) & set(gt_states) & set(cam_by_frame))
    if len(frames) < 2:
        return {"n_frames": len(frames)}

    fwd = _ego_forward_xy(cam_by_frame)

    pos_err, pos_err_center = [], []
    err_fwd, err_lat = [], []
    rel_err_abs, rel_err_pct = [], []
    rel_series = []   # (frame, d_est, d_gt)

    for f in frames:
        q = aligned_est[f][:2]
        g_near = gt_states[f]["near_face"][:2]
        g_cent = gt_states[f]["center"][:2]

        e = q - g_near
        pos_err.append(float(np.linalg.norm(e)))
        pos_err_center.append(float(np.linalg.norm(q - g_cent)))

        fw = fwd[f]
        rt = np.array([fw[1], -fw[0]])
        err_fwd.append(abs(float(e @ fw)))
        err_lat.append(abs(float(e @ rt)))

        # Relative distance in each native frame (alignment-invariant).
        d_est = float(np.linalg.norm(est_by_frame[f] - ego_by_frame[f])) * fit_s
        d_gt = float(np.linalg.norm(g_near - cam_by_frame[f][:2]))
        rel_series.append((f, d_est, d_gt))
        rel_err_abs.append(abs(d_est - d_gt))
        if d_gt > 1e-6:
            rel_err_pct.append(abs(d_est - d_gt) / d_gt * 100.0)

    # Speed: metric est positions (scale only — rotation preserves magnitude).
    est_pos = np.array([est_by_frame[f] for f in frames]) * fit_s
    est_speed = finite_diff_speed(frames, est_pos, fps)
    speed_pairs = [
        (f, est_speed[f], gt_states[f]["speed_mps"])
        for f in frames if f in est_speed
    ]
    speed_err = [abs(e - g) for _, e, g in speed_pairs]

    def _stats(vals: list) -> dict:
        if not vals:
            return {}
        a = np.asarray(vals)
        return {
            "mean": float(a.mean()),
            "median": float(np.median(a)),
            "rmse": float(np.sqrt((a ** 2).mean())),
            "max": float(a.max()),
        }

    return {
        "n_frames": len(frames),
        "position_error_m": _stats(pos_err),
        "position_error_center_m": _stats(pos_err_center),
        "position_error_forward_m": _stats(err_fwd),
        "position_error_lateral_m": _stats(err_lat),
        "relative_distance_error_m": _stats(rel_err_abs),
        "relative_distance_error_pct": _stats(rel_err_pct),
        "ade_m": float(np.mean(pos_err)),
        "fde_m": float(pos_err[-1]),
        "speed_error_mps": _stats(speed_err),
        "speed_error_kmh": _stats([v * 3.6 for v in speed_err]),
        "_series": {
            "frames": frames,
            "position_error_m": pos_err,
            "relative_distance": rel_series,           # (frame, est, gt)
            "speed_pairs": speed_pairs,                # (frame, est, gt) m/s
        },
    }


def evaluate_ego_speed(
    ego_by_frame: dict,
    cam_by_frame: dict,
    fit_s: float,
    fps: float,
) -> dict:
    """Ego (blackbox car) speed: est path diff vs GT camera-pose diff."""
    frames = sorted(set(ego_by_frame) & set(cam_by_frame))
    if len(frames) < 2:
        return {"n_frames": len(frames)}

    est_pos = np.array([ego_by_frame[f] for f in frames]) * fit_s
    gt_pos = np.array([cam_by_frame[f] for f in frames])
    est_speed = finite_diff_speed(frames, est_pos, fps)
    gt_speed = finite_diff_speed(frames, gt_pos, fps)

    pairs = [(f, est_speed[f], gt_speed[f]) for f in frames
             if f in est_speed and f in gt_speed]
    err = [abs(e - g) for _, e, g in pairs]
    a = np.asarray(err)
    return {
        "n_frames": len(frames),
        "speed_error_mps": {
            "mean": float(a.mean()), "median": float(np.median(a)),
            "rmse": float(np.sqrt((a ** 2).mean())), "max": float(a.max()),
        },
        "speed_error_kmh_mean": float(a.mean() * 3.6),
        "gt_speed_range_kmh": [
            float(min(g for _, _, g in pairs) * 3.6),
            float(max(g for _, _, g in pairs) * 3.6),
        ],
        "_series": {"speed_pairs": pairs},
    }
