"""Collision-moment detection + ego role classification from frame evidence.

Two detection paths:

  * **ego collision (당사자)** — a global camera shake spike coinciding (±window)
    with a vehicle very close to the ego (large bbox area). Shake alone is NOT
    enough: wipers and compilation scene-cuts also spike, but they have no
    nearby vehicle (validated on real crash footage: crash4's wiper spike has
    max bbox area 0.000, its real impact 0.14).

  * **observed collision (목격자)** — two dynamic tracks' bboxes overlap while
    at least one of them shows a kinematic discontinuity (sharp speed drop or
    the track ends right after the overlap away from the frame edge). Overlap
    alone is normal traffic (occlusions/passing) — the discontinuity
    requirement suppresses those, including the Waymo demo scene.

If neither path fires, the scene has **no detected collision** — the viewer
then shows only a clearly-labelled closest-approach marker, not a collision.
"""

from __future__ import annotations

import numpy as np

from . import signals

# ego collision
SHAKE_Z_MIN = 4.0        # 강건 z-score 임계 (충격 스파이크)
PROXIMITY_MIN = 0.04     # 근접 차량 게이트: bbox 면적/프레임 면적
PROXIMITY_WINDOW = 3     # 스파이크 ± N 프레임 안에서 근접 차량 탐색

# observed collision
PAIR_IOU_MIN = 0.03        # 트랙쌍 겹침 최소 IoU
SPEED_DROP_FRAC = 0.6      # 겹침 직후 속도 60% 이상 감소
SPEED_MIN_REL = 0.12       # 이벤트 전 최소 속도 = 자기 bbox 폭의 이 비율/frame
                           # (원거리 차의 픽셀 노이즈 감속 배제 — Waymo 거짓양성 대응)
SPEED_MIN_ABS = 2.0        # px/frame 하한
SUSTAIN_FRAC = 0.4         # k+3..k+10 평균 속도가 v_before의 이 비율 미만 유지(진짜 멈춤)
END_WINDOW = 5             # 겹침 후 N프레임 내 트랙 소멸도 불연속으로 인정
EDGE_MARGIN_FRAC = 0.08    # 프레임 가장자리 소멸(화면 밖 이동)은 제외


def detect_ego_collision(shake_z: np.ndarray, area: np.ndarray, which: list) -> dict | None:
    n = len(shake_z)
    best = None
    for k in range(1, n):
        if shake_z[k] < SHAKE_Z_MIN:
            continue
        lo, hi = max(0, k - PROXIMITY_WINDOW), min(n, k + PROXIMITY_WINDOW + 1)
        w = int(np.argmax(area[lo:hi])) + lo
        prox = float(area[w])
        if prox < PROXIMITY_MIN:
            continue
        score = float(shake_z[k]) * prox
        if best is None or score > best["_score"]:
            best = {
                "_score": score,
                "frame_idx": int(k),
                "type": "ego",
                "track_ids": [which[w]] if which[w] else [],
                "evidence": {
                    "shake_z": round(float(shake_z[k]), 2),
                    "proximity_area_ratio": round(prox, 3),
                },
            }
    if best:
        # confidence: z 4→0.5, 8+→~0.9 스케일 + 근접 보정
        z = best["evidence"]["shake_z"]
        best["confidence"] = round(min(0.95, 0.5 + 0.05 * (z - SHAKE_Z_MIN) +
                                       2.0 * best["evidence"]["proximity_area_ratio"]), 2)
        best.pop("_score")
    return best


def detect_observed_collision(bbox_sequence: dict, n_frames: int) -> dict | None:
    centers = signals.track_centers(bbox_sequence)
    W, H = signals.frame_size_from_bboxes(bbox_sequence)
    ids = sorted(centers.keys(), key=lambda s: int(s))
    best = None

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = centers[ids[i]], centers[ids[j]]
            common = sorted(set(a) & set(b))
            if len(common) < 3:
                continue
            for k in common:
                iou = signals.bbox_iou(a[k], b[k])
                if iou < PAIR_IOU_MIN:
                    continue
                # 겹침 직전 접근 중이었는지 (중심 거리 감소)
                prev = [f for f in common if f < k][-3:]
                if len(prev) >= 2:
                    d0 = np.hypot(a[prev[0]][0] - b[prev[0]][0], a[prev[0]][1] - b[prev[0]][1])
                    d1 = np.hypot(a[k][0] - b[k][0], a[k][1] - b[k][1])
                    if d1 >= d0:
                        continue

                # 운동학 불연속: 속도 급감(지속) or 직후 트랙 소멸(가장자리 아님).
                # 속도 측정 창은 겹침 구간에서 떨어뜨림 — bbox가 겹치는 동안은
                # 탐지 박스가 붙어 속도가 오염됨.
                disc = None
                for tid, c in ((ids[i], a), (ids[j], b)):
                    v_before = signals.speed_px(c, max(min(c), k - 4))
                    v_after = signals.speed_px(c, min(max(c), k + 5))
                    bbox_w = c[k][2]
                    v_min = max(SPEED_MIN_ABS, SPEED_MIN_REL * bbox_w)
                    if (v_before is not None and v_after is not None
                            and v_before >= v_min
                            and v_after <= v_before * (1 - SPEED_DROP_FRAC)):
                        # 지속 정지 확인: 이후 수 프레임 평균도 낮게 유지
                        later = [signals.speed_px(c, f) for f in range(k + 3, k + 11) if f in c]
                        later = [v for v in later if v is not None]
                        if later and float(np.mean(later)) <= v_before * SUSTAIN_FRAC:
                            disc = {"track": tid, "kind": "speed_drop",
                                    "v_before": round(v_before, 1), "v_after": round(v_after, 1),
                                    "v_min_used": round(v_min, 1)}
                            break
                    last = max(c)
                    # 영상 끝에서의 트랙 종료는 소멸 증거가 아님 (시퀀스가 끝났을 뿐)
                    if k <= last <= k + END_WINDOW and last < n_frames - END_WINDOW - 1:
                        cx, cy = c[last][0], c[last][1]
                        # 소멸 시점 bbox가 충분히 크고(원거리 가림 배제) 가장자리가 아니어야
                        if (c[last][2] >= 0.06 * W
                                and EDGE_MARGIN_FRAC * W < cx < (1 - EDGE_MARGIN_FRAC) * W
                                and cy < (1 - EDGE_MARGIN_FRAC) * H):
                            disc = {"track": tid, "kind": "track_end"}
                            break
                if disc is None:
                    continue

                score = iou + (0.3 if disc["kind"] == "speed_drop" else 0.15)
                if best is None or score > best["_score"]:
                    best = {
                        "_score": score,
                        "frame_idx": int(k),
                        "type": "observed",
                        "track_ids": [ids[i], ids[j]],
                        "evidence": {"pair_iou": round(iou, 3), "discontinuity": disc},
                    }

    if best:
        best["confidence"] = round(min(0.9, 0.4 + best["_score"]), 2)
        best.pop("_score")
    return best


def detect(bbox_sequence: dict, frame_paths: list, fps: float = 10.0) -> dict:
    """Full detection. Returns the collision.json payload (collision may be null)."""
    n = len(frame_paths)
    shake_z = signals.shake_series(frame_paths)
    area, which = signals.proximity_series(bbox_sequence, n)

    ego_hit = detect_ego_collision(shake_z, area, which)
    obs_hit = detect_observed_collision(bbox_sequence, n)

    # ego 충돌은 물리 증거(카메라 충격)가 있으므로 우선.
    collision = ego_hit or obs_hit
    if collision:
        collision["time_s"] = round(collision["frame_idx"] / fps, 2)

    ego_role = "none"
    if collision:
        ego_role = "party" if collision["type"] == "ego" else "witness"

    return {
        "collision": collision,
        "ego_role": ego_role,   # party=당사자, witness=목격자, none=충돌 미검출
        "fps": fps,
        "n_frames": n,
        "params": {
            "shake_z_min": SHAKE_Z_MIN, "proximity_min": PROXIMITY_MIN,
            "pair_iou_min": PAIR_IOU_MIN, "speed_drop_frac": SPEED_DROP_FRAC,
        },
        "series": {"shake_z": [round(float(v), 2) for v in shake_z]},
    }
