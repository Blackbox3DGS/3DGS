"""Evaluation outputs: metrics.json + Korean report.md + BEV/error plots."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Brand palette (ReScene_concept.md)
DEEP_GREEN = "#20543d"
TEAL = "#299283"


def _strip_series(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "_series"}


def write_metrics_json(out_dir: Path, payload: dict) -> Path:
    out = out_dir / "metrics.json"

    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items() if k != "_series"}
        if isinstance(obj, (list, tuple)):
            return [_clean(v) for v in obj]
        if isinstance(obj, (np.floating, np.integer)):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    with open(out, "w") as f:
        json.dump(_clean(payload), f, indent=2, ensure_ascii=False)
    return out


# --------------------------------------------------------------------------
# Plots
# --------------------------------------------------------------------------

def plot_bev_overlay(
    out_dir: Path,
    gt_cam_xy: np.ndarray,
    gt_tracks: dict,          # est_tid -> (F,2) GT near-face xy
    est_ego_xy: np.ndarray,   # aligned est ego, (N,2)
    est_tracks: dict,         # est_tid -> (F,2) aligned est xy
) -> Path:
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.plot(gt_cam_xy[:, 0], gt_cam_xy[:, 1], "-", color=DEEP_GREEN, lw=2.5,
            label="GT ego (camera)")
    ax.plot(est_ego_xy[:, 0], est_ego_xy[:, 1], "--", color=TEAL, lw=2,
            label="Est ego (aligned)")

    cmap = plt.cm.tab10
    for i, tid in enumerate(sorted(gt_tracks, key=lambda s: int(s))):
        c = cmap(i % 10)
        g = gt_tracks[tid]
        e = est_tracks[tid]
        ax.plot(g[:, 0], g[:, 1], "-", color=c, lw=1.8, label=f"GT #{tid}")
        ax.plot(e[:, 0], e[:, 1], "--", color=c, lw=1.4, alpha=0.8,
                label=f"Est #{tid}")

    ax.set_aspect("equal")
    ax.set_xlabel("global x (m)")
    ax.set_ylabel("global y (m)")
    ax.set_title("BEV trajectory overlay — GT (solid) vs Estimated (dashed)")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=0.3)
    out = out_dir / "plots" / "bev_overlay.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_error_series(out_dir: Path, track_results: dict, fps: float) -> list:
    outs = []
    cmap = plt.cm.tab10

    # Position error over time
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for i, (tid, res) in enumerate(sorted(track_results.items(), key=lambda kv: int(kv[0]))):
        s = res.get("_series")
        if not s:
            continue
        t = np.asarray(s["frames"]) / fps
        ax.plot(t, s["position_error_m"], color=cmap(i % 10), label=f"#{tid}")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("BEV position error (m)")
    ax.set_title("Vehicle position error (near-face, BEV)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    out = out_dir / "plots" / "position_error.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    outs.append(out)

    # Relative distance est vs gt
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for i, (tid, res) in enumerate(sorted(track_results.items(), key=lambda kv: int(kv[0]))):
        s = res.get("_series")
        if not s:
            continue
        arr = np.asarray(s["relative_distance"])   # (F, 3): frame, est, gt
        t = arr[:, 0] / fps
        c = cmap(i % 10)
        ax.plot(t, arr[:, 2], "-", color=c, label=f"#{tid} GT")
        ax.plot(t, arr[:, 1], "--", color=c, alpha=0.8, label=f"#{tid} Est")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("ego↔vehicle distance (m)")
    ax.set_title("Relative distance — GT (solid) vs Estimated (dashed)")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=0.3)
    out = out_dir / "plots" / "relative_distance.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    outs.append(out)

    return outs


def plot_speed_comparison(out_dir: Path, track_results: dict, ego_result: dict, fps: float) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    cmap = plt.cm.tab10

    s = ego_result.get("_series")
    if s and s.get("speed_pairs"):
        arr = np.asarray(s["speed_pairs"])         # (F,3): frame, est, gt (m/s)
        t = arr[:, 0] / fps
        ax.plot(t, arr[:, 2] * 3.6, "-", color=DEEP_GREEN, lw=2, label="ego GT")
        ax.plot(t, arr[:, 1] * 3.6, "--", color=TEAL, lw=1.8, label="ego Est")

    for i, (tid, res) in enumerate(sorted(track_results.items(), key=lambda kv: int(kv[0]))):
        s = res.get("_series")
        if not s or not s.get("speed_pairs"):
            continue
        arr = np.asarray(s["speed_pairs"])
        t = arr[:, 0] / fps
        c = cmap(i % 10)
        ax.plot(t, arr[:, 2] * 3.6, "-", color=c, alpha=0.9, label=f"#{tid} GT")
        ax.plot(t, arr[:, 1] * 3.6, "--", color=c, alpha=0.7, label=f"#{tid} Est")

    ax.set_xlabel("time (s)")
    ax.set_ylabel("speed (km/h)")
    ax.set_title("Speed — GT (solid) vs Estimated (dashed)")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=0.3)
    out = out_dir / "plots" / "speed_comparison.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


# --------------------------------------------------------------------------
# Markdown report (Korean)
# --------------------------------------------------------------------------

def _fmt(stats: dict, unit: str = "m") -> str:
    if not stats:
        return "—"
    return (f"평균 {stats['mean']:.2f}{unit} / 중앙값 {stats['median']:.2f}{unit} / "
            f"RMSE {stats['rmse']:.2f}{unit} / 최대 {stats['max']:.2f}{unit}")


def write_report_md(out_dir: Path, payload: dict) -> Path:
    al = payload["alignment"]
    assoc = payload["association"]
    tracks = payload["tracks"]
    ego = payload["ego"]
    meta = payload["meta"]

    lines = [
        "# ReScene 정량 평가 리포트 (Waymo GT 대비)",
        "",
        f"- 장면: `{meta['scene_name']}` / 평가 프레임 {meta['num_frames']}개 "
        f"(≈{meta['num_frames'] / meta['fps']:.1f}초, {meta['fps']:.0f} fps)",
        f"- 추정 대상: `{meta['vehicles_path']}`",
        "",
        "## 1. 좌표 정렬 (중력 구속 2D 유사변환, ego 경로 기반)",
        "",
        "추정 좌표계(y-up, 지면 정렬)와 Waymo global(z-up)이 모두 중력 정렬이라는 사실을 이용해 "
        "지면 2D 유사변환 + 수직 오프셋으로 정렬. 직진 주행 경로는 좌우 반사(handedness)를 "
        "결정하지 못하므로 동적 트랙 잔차로 해소.",
        "",
        f"- 스케일 s = **{al['s']:.3f} m/unit** (det(R₂) = {al['det']:+d}"
        f"{', 좌우 반사 포함' if al['det'] < 0 else ''})",
        f"- handedness 결정: {al['handedness_source']}"
        f"{' (ego 경로 직진성으로 모호 → 트랙 잔차로 해소)' if al['ego_path_ambiguous'] else ''}",
        f"- ego 경로 정렬 잔차 RMSE = **{al['rmse_m']:.2f} m** "
        f"(반대 handedness 시 {al['rmse_other_det_m']:.2f} m)",
        f"- 카메라 높이 prior 기반 추정 스케일 = {meta['mpu_prior']:.3f} m/unit "
        f"(Umeyama 대비 오차 {abs(al['s'] - meta['mpu_prior']) / al['s'] * 100:.1f}%) — "
        "뷰어 HUD가 쓰는 근사 스케일의 교차 검증",
        "",
        "## 2. 트랙 매칭 (YOLO/ByteTrack ↔ Waymo GT)",
        "",
        "| est 트랙 | GT id | 매칭 프레임 | 평균 IoU |",
        "|---|---|---|---|",
    ]
    for tid, m in sorted(assoc.items(), key=lambda kv: int(kv[0])):
        lines.append(f"| #{tid} | `{m['gt_id'][:12]}…` | {m['matched_frames']} | {m['mean_iou']:.2f} |")

    lines += [
        "",
        "## 3. 지표 결과",
        "",
        "IPM 배치 특성상 **전후 순서는 정확, 횡방향은 근사**임 — 전방/횡방향 분해를 함께 표기. "
        "추정점은 bbox 하단(카메라를 향한 면의 지면점)이므로 GT도 근접면(near-face) 기준으로 비교, "
        "괄호 안은 GT 중심 기준.",
        "",
        "### 3.1 차량 중심 위치 오차 (BEV)",
        "",
        "| 트랙 | 프레임 | 위치 오차 (near-face) | (중심 기준 평균) | 전방 성분 | 횡방향 성분 |",
        "|---|---|---|---|---|---|",
    ]
    for tid, res in sorted(tracks.items(), key=lambda kv: int(kv[0])):
        if res.get("n_frames", 0) < 2:
            continue
        pc = res["position_error_center_m"]
        lines.append(
            f"| #{tid} | {res['n_frames']} | {_fmt(res['position_error_m'])} "
            f"| {pc['mean']:.2f}m | {res['position_error_forward_m']['mean']:.2f}m "
            f"| {res['position_error_lateral_m']['mean']:.2f}m |"
        )

    lines += [
        "",
        "### 3.2 상대거리 오차 (ego↔차량, 정렬 불변 지표)",
        "",
        "| 트랙 | 절대 오차 | 상대 오차(%) |",
        "|---|---|---|",
    ]
    for tid, res in sorted(tracks.items(), key=lambda kv: int(kv[0])):
        if res.get("n_frames", 0) < 2:
            continue
        pct = res["relative_distance_error_pct"]
        lines.append(f"| #{tid} | {_fmt(res['relative_distance_error_m'])} "
                     f"| 평균 {pct['mean']:.1f}% / 중앙값 {pct['median']:.1f}% |")

    lines += [
        "",
        "### 3.3 궤적 오차 (ADE / FDE)",
        "",
        "| 트랙 | ADE | FDE |",
        "|---|---|---|",
    ]
    for tid, res in sorted(tracks.items(), key=lambda kv: int(kv[0])):
        if res.get("n_frames", 0) < 2:
            continue
        lines.append(f"| #{tid} | {res['ade_m']:.2f} m | {res['fde_m']:.2f} m |")

    ego_se = ego.get("speed_error_mps", {})
    lines += [
        "",
        "### 3.4 속도 추정 오차",
        "",
        "| 대상 | 속도 오차 (m/s) | 속도 오차 (km/h 평균) |",
        "|---|---|---|",
        (f"| ego | {_fmt(ego_se, ' m/s')} | {ego.get('speed_error_kmh_mean', 0):.1f} km/h |"
         if ego_se else "| ego | — | — |"),
    ]
    for tid, res in sorted(tracks.items(), key=lambda kv: int(kv[0])):
        if res.get("n_frames", 0) < 2 or not res.get("speed_error_mps"):
            continue
        lines.append(f"| #{tid} | {_fmt(res['speed_error_mps'], ' m/s')} "
                     f"| {res['speed_error_kmh']['mean']:.1f} km/h |")

    if ego.get("gt_speed_range_kmh"):
        lo, hi = ego["gt_speed_range_kmh"]
        lines += ["", f"- GT ego 속도 범위: {lo:.0f}–{hi:.0f} km/h"]

    lines += [
        "",
        "## 4. 플롯",
        "",
        "![BEV overlay](plots/bev_overlay.png)",
        "![Position error](plots/position_error.png)",
        "![Relative distance](plots/relative_distance.png)",
        "![Speed comparison](plots/speed_comparison.png)",
        "",
    ]

    out = out_dir / "report.md"
    with open(out, "w") as f:
        f.write("\n".join(lines))
    return out
