"""trajectories.json serialiser for Stage 09."""

import json
from pathlib import Path


def write_trajectories(
    tracks_out: dict,
    frame_count_total: int,
    skipped: dict,
    out_path: Path,
    *,
    params: dict,
) -> str:
    """Serialise trajectories to JSON.

    Tracks are sorted by integer track_id ascending (string-keyed in JSON).
    Points within a track preserve their incoming order (caller sorts by
    frame_idx).
    """
    sorted_keys = sorted(tracks_out.keys(), key=lambda s: int(s))
    tracks_sorted = {tid: tracks_out[tid] for tid in sorted_keys}

    payload = {
        "metadata": {
            "num_tracks": len(tracks_sorted),
            "frame_count": frame_count_total,
            "coord_system": "colmap_world",
            "source": "stage_09_trajectory",
            "params": params,
            "skipped": skipped,
        },
        "tracks": tracks_sorted,
    }

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    return str(out_path)
