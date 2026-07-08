"""Gravity-constrained similarity alignment between est and GT worlds.

The estimated trajectories live in LingBot's ground-aligned frame (y-up, road
plane at y=0, non-metric units); Waymo's global frame is z-up metric. Both are
gravity-aligned, so instead of a free 3D Umeyama we fit a *2D* similarity on
the ground plane plus a vertical offset:

    [gx, gy] = s * R2 @ [ex, ez] + t2        (R2: 2x2, det = +1 or -1)
    gz       = s * ey + tz

Why not 3D Umeyama: forward-driving ego paths are nearly straight, which makes
the 3D point set rank-1 — the rotation about the path axis (and the
handedness) is then unconstrained and the fitted rotation lands arbitrarily,
silently corrupting the dynamic-vehicle position errors. The gravity
constraint removes that degeneracy.

Handedness still matters: the viewer applies MIRROR_X to this data, so the est
ground plane may be mirrored vs GT. A *straight* ego path cannot distinguish
left from right, so we always return BOTH det(R2)=+1 and det(R2)=-1 fits; the
caller disambiguates with the matched dynamic tracks when the ego residuals
tie (see `choose_fit`).

The scale `s` doubles as a cross-check for the camera-height-prior
`meters_per_unit` used by the viewer HUD.
"""

from __future__ import annotations

import numpy as np


def _umeyama_2d(src: np.ndarray, dst: np.ndarray, force_det: int) -> tuple:
    """2D similarity dst ~= s*R2@src + t2 with det(R2) forced. Returns (s,R2,t2)."""
    n = len(src)
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    xs, xd = src - mu_s, dst - mu_d

    cov = xd.T @ xs / n
    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(2)
    if np.sign(np.linalg.det(U) * np.linalg.det(Vt)) != force_det:
        S[1, 1] = -1.0

    R2 = U @ S @ Vt
    var_s = (xs ** 2).sum() / n
    s = float(np.trace(np.diag(D) @ S) / var_s)
    t2 = mu_d - s * R2 @ mu_s
    return s, R2, t2


def _fit(est: np.ndarray, gt: np.ndarray, force_det: int) -> dict:
    """est (N,3) y-up units -> gt (N,3) z-up meters, one handedness."""
    src2 = est[:, [0, 2]]          # est ground plane (x, z)
    dst2 = gt[:, :2]               # GT ground plane (x, y)
    s, R2, t2 = _umeyama_2d(src2, dst2, force_det)
    tz = float((gt[:, 2] - s * est[:, 1]).mean())

    fit = {"s": s, "R2": R2, "t2": t2, "tz": tz, "det": force_det}
    res = apply_similarity(est, fit) - gt
    fit["rmse_m"] = float(np.sqrt((res ** 2).sum(axis=1).mean()))
    return fit


def align_ego_path(est_ego: np.ndarray, gt_cam: np.ndarray) -> dict:
    """Fit both handedness cases on the ego path.

    Returns {"fits": {+1: fit, -1: fit}, "n_points": N}. Each fit has
    s / R2 / t2 / tz / det / rmse_m. Use `choose_fit` to pick one.
    """
    est_ego = np.asarray(est_ego, dtype=np.float64)
    gt_cam = np.asarray(gt_cam, dtype=np.float64)
    return {
        "fits": {det: _fit(est_ego, gt_cam, det) for det in (+1, -1)},
        "n_points": int(len(est_ego)),
    }


def choose_fit(fits: dict, track_residual_fn=None, tie_ratio: float = 0.1) -> dict:
    """Pick a handedness. Ego residuals decide unless they tie (straight path);
    then `track_residual_fn(fit) -> float` (mean matched-track error) breaks it.
    """
    f_pos, f_neg = fits[+1], fits[-1]
    lo, hi = sorted((f_pos["rmse_m"], f_neg["rmse_m"]))
    ambiguous = hi == 0 or (hi - lo) <= tie_ratio * max(hi, 1e-12)

    if ambiguous and track_residual_fn is not None:
        r_pos, r_neg = track_residual_fn(f_pos), track_residual_fn(f_neg)
        chosen = f_pos if r_pos <= r_neg else f_neg
        chosen = dict(chosen)
        chosen["handedness_source"] = "dynamic-tracks"
        chosen["track_residual_m"] = {"+1": r_pos, "-1": r_neg}
    else:
        chosen = dict(f_pos if f_pos["rmse_m"] <= f_neg["rmse_m"] else f_neg)
        chosen["handedness_source"] = "ego-path"

    chosen["rmse_other_det_m"] = fits[-chosen["det"]]["rmse_m"]
    chosen["ego_path_ambiguous"] = bool(ambiguous)
    return chosen


def apply_similarity(points: np.ndarray, fit: dict) -> np.ndarray:
    """points (N,3) est y-up -> (N,3) GT global z-up."""
    p = np.asarray(points, dtype=np.float64)
    if p.ndim == 1:
        p = p[None, :]
    xy = fit["s"] * p[:, [0, 2]] @ np.asarray(fit["R2"]).T + np.asarray(fit["t2"])
    z = fit["s"] * p[:, 1] + fit["tz"]
    out = np.column_stack([xy, z])
    return out
