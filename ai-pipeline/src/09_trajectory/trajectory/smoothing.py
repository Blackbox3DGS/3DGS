"""Gap-aware temporal smoothing for per-track 3D trajectories."""

import copy


def _smooth_run(run_pts: list[dict]) -> list[dict]:
    """Centred 3-frame moving average within a single contiguous run.

    Endpoints retained as-is; interior points replaced by xyz mean of
    [i-1, i, i+1]. Other fields (frame_idx, frame_name, depth_m) preserved.
    """
    n = len(run_pts)
    if n <= 2:
        return [copy.deepcopy(p) for p in run_pts]
    out = [copy.deepcopy(run_pts[0])]
    for i in range(1, n - 1):
        a = run_pts[i - 1]["xyz"]
        b = run_pts[i]["xyz"]
        c = run_pts[i + 1]["xyz"]
        smoothed = copy.deepcopy(run_pts[i])
        smoothed["xyz"] = [
            (a[0] + b[0] + c[0]) / 3.0,
            (a[1] + b[1] + c[1]) / 3.0,
            (a[2] + b[2] + c[2]) / 3.0,
        ]
        out.append(smoothed)
    out.append(copy.deepcopy(run_pts[-1]))
    return out


def smooth_xyz_track(
    points: list[dict],
    window: int = 3,
    max_gap: int = 2,
) -> list[dict]:
    """Apply gap-aware centred moving average to a sorted-by-frame_idx point list.

    Splits into runs where consecutive frame_idx differ by ≤ `max_gap` and
    smooths each run independently so we never average across occlusion gaps.

    Currently only `window == 3` is implemented (the only value used by Stage 09).
    """
    if window != 3:
        raise NotImplementedError("Only window=3 is supported.")
    if not points:
        return []

    runs: list[list[dict]] = []
    current = [points[0]]
    for prev, cur in zip(points, points[1:]):
        if cur["frame_idx"] - prev["frame_idx"] <= max_gap:
            current.append(cur)
        else:
            runs.append(current)
            current = [cur]
    runs.append(current)

    out: list[dict] = []
    for run in runs:
        out.extend(_smooth_run(run))
    return out
