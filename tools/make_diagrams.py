#!/usr/bin/env python3
"""Generate README architecture/flow diagrams into docs/figures/.

matplotlib-only (no graphviz dependency); ReScene brand palette.

    python3 tools/make_diagrams.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

DEEP = "#20543d"
TEAL = "#299283"
LIGHT = "#e8f2ee"
GRAY = "#5a665e"
RED = "#c0392b"

OUT = Path(__file__).resolve().parents[1] / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# 한글 폰트 (macOS: AppleGothic, Linux: NanumGothic 등 자동 탐색)
for f in ("AppleGothic", "NanumGothic", "Malgun Gothic"):
    if any(f.lower() in x.name.lower() for x in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break
plt.rcParams["axes.unicode_minus"] = False


def box(ax, x, y, w, h, title, sub="", fc=LIGHT, ec=DEEP, title_c=DEEP, fs=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                 fc=fc, ec=ec, lw=1.6))
    cy = y + h / 2
    if sub:
        ax.text(x + w / 2, cy + 0.13, title, ha="center", va="center",
                fontsize=fs, fontweight="bold", color=title_c)
        ax.text(x + w / 2, cy - 0.17, sub, ha="center", va="center",
                fontsize=fs - 2.5, color=GRAY)
    else:
        ax.text(x + w / 2, cy, title, ha="center", va="center",
                fontsize=fs, fontweight="bold", color=title_c)


def arrow(ax, x1, y1, x2, y2, color=DEEP, ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                  mutation_scale=16, color=color, lw=1.8, linestyle=ls))


def new_ax(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    return fig, ax


def save(fig, name):
    p = OUT / name
    fig.savefig(p, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", p)


# ── 1. 전체 시스템 아키텍처 ────────────────────────────────────────────────────
def architecture():
    fig, ax = new_ax(12, 6.2)
    ax.text(5, 9.7, "ReScene 시스템 아키텍처", ha="center", fontsize=15,
            fontweight="bold", color=DEEP)

    box(ax, 0.2, 7.6, 1.9, 1.2, "블랙박스 영상", "단안 mp4 / Waymo", fc="#ffffff")
    # AI pipeline lane
    ax.add_patch(FancyBboxPatch((0.15, 3.6), 7.6, 3.4, boxstyle="round,pad=0.02",
                                 fc="#f6faf8", ec=TEAL, lw=1.2, linestyle="--"))
    ax.text(0.4, 6.7, "AI Pipeline (Python · GPU)", fontsize=9.5, color=TEAL, fontweight="bold")

    box(ax, 0.5, 5.3, 1.9, 1.1, "02 프레임 추출", "ffmpeg / TFRecord")
    box(ax, 2.8, 5.3, 1.9, 1.1, "03 탐지·추적", "YOLOv8-seg + ByteTrack")
    box(ax, 5.1, 5.3, 2.4, 1.1, "04g LingBot-MAP", "feed-forward 포즈+깊이")
    box(ax, 0.5, 3.9, 2.9, 1.1, "씬 익스포트", ".splat + vehicles.json (m 스케일)")
    box(ax, 3.8, 3.9, 1.9, 1.1, "09 궤적", "IPM + Kalman")
    box(ax, 6.0, 3.9, 1.5, 1.1, "13 평가", "Waymo GT")

    arrow(ax, 1.2, 7.6, 1.4, 6.4)
    arrow(ax, 2.4, 5.85, 2.8, 5.85)
    arrow(ax, 4.7, 5.85, 5.1, 5.85)
    arrow(ax, 6.3, 5.3, 4.9, 5.0)      # lingbot -> trajectory
    arrow(ax, 3.8, 4.45, 3.4, 4.45)    # trajectory -> export
    arrow(ax, 5.7, 4.45, 6.0, 4.45)    # -> eval

    # Web lane
    box(ax, 8.2, 5.3, 1.6, 1.1, "Backend", "Spring Boot · 작업관리", ec=GRAY, title_c=GRAY)
    box(ax, 8.2, 3.9, 1.6, 1.1, "웹 뷰어", "React + Three.js", ec=RED, title_c=RED)
    arrow(ax, 3.4, 4.2, 8.2, 4.3, color=TEAL)
    ax.text(5.7, 3.6, ".splat + vehicles.json", fontsize=8, color=TEAL, ha="center")

    # Viewer features
    box(ax, 1.0, 1.4, 8.0, 1.5, "사고 재현 뷰어", "BEV 탑다운 · 충돌(최근접) 시점 마커 · 차간거리(m) · 속도(km/h) · 타임라인",
        fc="#fdf3f2", ec=RED, title_c=RED, fs=12)
    arrow(ax, 9.0, 3.9, 7.0, 2.9, color=RED)
    save(fig, "architecture.png")


# ── 2. 정량 평가 데이터 흐름 ──────────────────────────────────────────────────
def eval_flow():
    fig, ax = new_ax(12, 4.4)
    ax.text(5, 9.5, "정량 평가(Stage 13) 데이터 흐름 — Waymo GT 대비", ha="center",
            fontsize=14, fontweight="bold", color=DEEP)

    box(ax, 0.2, 6.2, 1.9, 1.6, "Waymo TFRecord", "GT 포즈·3D박스·속도", fc="#ffffff")
    box(ax, 2.6, 6.2, 1.7, 1.6, "extract-gt", "순수 파이썬 파서\n(TF 불필요)")
    box(ax, 4.8, 6.2, 1.5, 1.6, "gt.json", "199프레임", fc="#fff9e8", ec="#b8860b", title_c="#b8860b")
    box(ax, 0.2, 3.4, 2.1, 1.6, "vehicles.json", "추정 궤적 (뷰어와 동일)", fc="#ffffff")
    box(ax, 2.6, 3.4, 2.1, 1.6, "트랙 매칭", "2D IoU>0.3 다수결")
    box(ax, 5.1, 3.4, 2.3, 1.6, "좌표 정렬", "중력구속 2D Umeyama\n± 좌우반사 해소")
    box(ax, 7.9, 4.6, 1.9, 2.4, "4대 지표", "① 위치 오차(BEV)\n② 상대거리 오차\n③ ADE/FDE\n④ 속도 오차", fc="#fdf3f2", ec=RED, title_c=RED)

    arrow(ax, 2.1, 7.0, 2.6, 7.0)
    arrow(ax, 4.3, 7.0, 4.8, 7.0)
    arrow(ax, 5.5, 6.2, 5.9, 5.0)
    arrow(ax, 2.3, 4.2, 2.6, 4.2)
    arrow(ax, 4.7, 4.2, 5.1, 4.2)
    arrow(ax, 7.4, 4.2, 7.9, 4.9)
    box(ax, 7.9, 1.8, 1.9, 1.4, "report.md + plots", "metrics.json · BEV overlay", fc="#ffffff")
    arrow(ax, 8.85, 4.6, 8.85, 3.2)
    save(fig, "eval_flow.png")


# ── 3. 스케일 보정 원리 ───────────────────────────────────────────────────────
def scale_calibration():
    fig, ax = new_ax(10, 4.6)
    ax.text(5, 9.5, "미터 스케일 보정 — 카메라 높이 prior", ha="center",
            fontsize=14, fontweight="bold", color=DEEP)

    # 도로 + 차량 그림
    ax.plot([0.5, 6.5], [2.5, 2.5], color=GRAY, lw=3)
    ax.text(3.5, 2.0, "노면 (y = 0, 지면 정렬 후)", fontsize=9, color=GRAY, ha="center")
    # car body
    ax.add_patch(FancyBboxPatch((2.2, 2.6), 2.4, 1.1, boxstyle="round,pad=0.02", fc=LIGHT, ec=DEEP, lw=1.6))
    ax.add_patch(FancyBboxPatch((2.8, 3.6), 1.2, 0.7, boxstyle="round,pad=0.02", fc=LIGHT, ec=DEEP, lw=1.6))
    ax.plot([3.4], [4.5], marker="o", ms=8, color=RED)
    ax.text(3.75, 4.55, "블랙박스 카메라", fontsize=9, color=RED)
    ax.annotate("", xy=(1.6, 2.5), xytext=(1.6, 4.5),
                arrowprops=dict(arrowstyle="<->", color=TEAL, lw=2))
    ax.text(1.45, 3.5, "ego_y\n(scene units)", fontsize=9, color=TEAL, ha="right")

    ax.text(7.9, 6.4, "meters_per_unit", fontsize=13, fontweight="bold", color=DEEP, ha="center")
    ax.text(7.9, 5.5, "= 실제 카메라 높이 (m)\n   ÷ median(ego_y)", fontsize=11, color=GRAY, ha="center")
    ax.text(7.9, 4.0, "블랙박스 ≈ 1.4 m\nWaymo FRONT ≈ 2.115 m", fontsize=10, color=TEAL, ha="center")
    ax.text(7.9, 2.4, "검증: Waymo GT Umeyama 스케일과\n오차 1.9% (sample1, 199프레임)",
            fontsize=9.5, color=RED, ha="center",
            bbox=dict(boxstyle="round", fc="#fdf3f2", ec=RED, lw=1))
    save(fig, "scale_calibration.png")


# ── 4. 뷰어 기능 구조 ─────────────────────────────────────────────────────────
def viewer_features():
    fig, ax = new_ax(11, 5)
    ax.text(5, 9.5, "사고 재현 뷰어 구조", ha="center", fontsize=14,
            fontweight="bold", color=DEEP)

    box(ax, 0.3, 6.6, 2.2, 1.7, "vehicles.json", "궤적 + meters_per_unit\n+ fps", fc="#ffffff")
    box(ax, 0.3, 4.2, 2.2, 1.7, "background.splat", "포인트클라우드 배경", fc="#ffffff")

    box(ax, 3.2, 5.4, 2.6, 2.2, "analysis.ts", "스케일 환산\n속도 시계열(중앙차분)\n최근접 시점 탐색", fc=LIGHT)
    box(ax, 6.4, 7.0, 3.2, 1.3, "BEV 탑다운", "직교 카메라 · 회전 잠금", fc="#fdf3f2", ec=RED, title_c=RED)
    box(ax, 6.4, 5.4, 3.2, 1.3, "충돌 시점 마커", "노면 링 + 타임라인 ⚠ + 점프", fc="#fdf3f2", ec=RED, title_c=RED)
    box(ax, 6.4, 3.8, 3.2, 1.3, "거리·속도 HUD", "차량쌍 선택 · ≈m / ≈km/h", fc="#fdf3f2", ec=RED, title_c=RED)
    box(ax, 6.4, 2.2, 3.2, 1.3, "타임라인 스크러버", "시킹 · 재생/정지", fc="#fdf3f2", ec=RED, title_c=RED)
    box(ax, 3.2, 2.2, 2.6, 1.7, "Three.js 씬", "차량 GLB · 지면 높이맵\n궤적 라인", fc=LIGHT)

    arrow(ax, 2.5, 7.2, 3.2, 6.7)
    arrow(ax, 2.5, 5.0, 3.4, 3.6)
    arrow(ax, 5.8, 6.5, 6.4, 7.4)
    arrow(ax, 5.8, 6.2, 6.4, 6.0)
    arrow(ax, 5.8, 5.8, 6.4, 4.4)
    arrow(ax, 5.8, 3.0, 6.4, 2.9)
    save(fig, "viewer_features.png")


if __name__ == "__main__":
    architecture()
    eval_flow()
    scale_calibration()
    viewer_features()
