"""Associate estimated tracks (Stage-03 YOLO/ByteTrack ids) with Waymo GT ids.

Both sides carry per-frame 2D boxes in the FRONT image: the estimate from
`bbox_sequence.json` (original resolution), the GT from the projected LiDAR
labels stored in `gt.json`. Per frame we greedily match boxes by IoU, then a
track-level majority vote turns frame matches into a single est-id -> gt-id
mapping. Numpy-only (runs locally without TF).
"""

from __future__ import annotations

from collections import Counter, defaultdict


IOU_THRESHOLD = 0.3
MIN_MATCHED_FRAMES = 10


def _iou(a: list, b: list) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def associate_tracks(
    bbox_sequence: dict,
    gt: dict,
    track_ids: list,
    iou_threshold: float = IOU_THRESHOLD,
    min_matched_frames: int = MIN_MATCHED_FRAMES,
) -> dict:
    """Map est track id -> {gt_id, matched_frames, mean_iou}.

    `track_ids` restricts matching to the tracks we actually evaluate (the
    dynamic vehicles exported to vehicles.json).
    """
    tracks = bbox_sequence.get("tracks", {})
    gt_by_frame = {fr["index"]: fr.get("projected_boxes", []) for fr in gt["frames"]}

    votes = defaultdict(Counter)          # est_id -> Counter(gt_id)
    ious = defaultdict(lambda: defaultdict(list))  # est_id -> gt_id -> [iou]

    frame_indices = sorted(gt_by_frame.keys())
    for fi in frame_indices:
        gt_boxes = gt_by_frame[fi]
        if not gt_boxes:
            continue

        # Collect est boxes present in this frame.
        est_boxes = []
        for tid in track_ids:
            fr = tracks.get(str(tid), {}).get("frames", {}).get(str(fi))
            if fr is not None:
                est_boxes.append((str(tid), fr["bbox"]))

        # Greedy IoU matching (highest IoU pair first, one-to-one).
        pairs = []
        for tid, ebox in est_boxes:
            for g in gt_boxes:
                v = _iou(ebox, g["bbox"])
                if v >= iou_threshold:
                    pairs.append((v, tid, g["id"]))
        pairs.sort(reverse=True)
        used_est, used_gt = set(), set()
        for v, tid, gid in pairs:
            if tid in used_est or gid in used_gt:
                continue
            used_est.add(tid)
            used_gt.add(gid)
            votes[tid][gid] += 1
            ious[tid][gid].append(v)

    mapping = {}
    claimed_gt = set()
    # Assign confident tracks first so two est tracks can't share one GT id.
    ranked = sorted(votes.items(), key=lambda kv: -kv[1].most_common(1)[0][1])
    for tid, counter in ranked:
        for gid, n in counter.most_common():
            if n < min_matched_frames:
                break
            if gid in claimed_gt:
                continue
            iou_list = ious[tid][gid]
            mapping[tid] = {
                "gt_id": gid,
                "matched_frames": n,
                "mean_iou": sum(iou_list) / len(iou_list),
            }
            claimed_gt.add(gid)
            break

    return mapping
