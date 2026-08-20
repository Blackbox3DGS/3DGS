#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""발표(PPT/포스터)용 핵심 정리 Word 문서 생성.

matplotlib로 구조 다이어그램(PNG)을 그리고 python-docx로 .docx에 삽입한다.
내용: (1) 설계 변경(원래→문제→수정, 구조적) (2) LingBot-MAP 이해 (3) 최종 시스템 구조.

환경변수:
  REPORT_OUT_DIR   .docx 와 figs/ 를 쓸 디렉터리. 기본값 ./report_out
  LINGBOT_MAP_DIR  "Pipeline of LingBot-Map.webp" 가 있는 디렉터리.
                   지정하지 않으면 논문 그림 없이 생성한다(선택 항목).

사용 예:
  REPORT_OUT_DIR=~/Documents/졸업작품 python3 tools/make_report.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib import font_manager


def _env_path(name, default=""):
    """환경변수에서 경로를 읽는다. 미설정/빈 값이면 default 를 쓴다."""
    return os.path.expanduser(os.environ.get(name, "").strip() or default)


OUT_DIR = os.path.abspath(_env_path("REPORT_OUT_DIR", "report_out"))
FIG_DIR = os.path.join(OUT_DIR, "figs")
os.makedirs(FIG_DIR, exist_ok=True)

# 논문 그림은 선택 항목이므로 기본값 없음(미설정 시 건너뜀).
LINGBOT_DIR = _env_path("LINGBOT_MAP_DIR")


# ── 한글 폰트 ────────────────────────────────────────────────
def set_korean_font():
    for name in ["AppleGothic", "Apple SD Gothic Neo", "AppleSDGothicNeo",
                 "NanumGothic", "Malgun Gothic", "NanumBarunGothic"]:
        try:
            font_manager.findfont(name, fallback_to_default=False)
            matplotlib.rcParams["font.family"] = name
            matplotlib.rcParams["axes.unicode_minus"] = False
            print(f"[font] using {name}")
            return name
        except Exception:
            continue
    print("[font] 한글 폰트 못 찾음 — 그림 라벨이 깨질 수 있음")
    return None


KFONT = set_korean_font()

# 팔레트
C_IN = "#e3eefc"     # 입력
C_PROC = "#e6f3ea"   # 처리
C_BAD = "#fde7e4"    # 문제(빨강)
C_OUT = "#fff2e0"    # 결과/웹
C_LB = "#ece5f7"     # LingBot
C_NEU = "#eef1f3"    # 중립
EC = "#5b6b76"
TC = "#15242e"


def box(ax, x, y, w, h, text, fc=C_NEU, tc=TC, fs=11, ec=EC, lw=1.4, bold=False, rs=0.03):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.012,rounding_size={rs}",
                       fc=fc, ec=ec, lw=lw, mutation_aspect=1)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color=tc, weight="bold" if bold else "normal", linespacing=1.3)


def arrow(ax, x1, y1, x2, y2, color=EC, lw=2.2, ls="-"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, linestyle=ls,
                                mutation_scale=18, shrinkA=0, shrinkB=0))


def label(ax, x, y, text, fs=10.5, color="#444", ha="center", weight="normal", style="normal"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=fs, color=color, weight=weight, style=style)


def new_ax(w, h, xlim, ylim):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.axis("off")
    return fig, ax


# ── 그림 1: Before / After ──────────────────────────────────
def fig1():
    fig, ax = new_ax(12.6, 6.4, (0, 25.2), (0, 12.8))
    bw, bh = 4.2, 1.7

    # 제목
    label(ax, 0.3, 12.2, "[변경 전]  COLMAP + 3D Gaussian Splatting", fs=13, ha="left", weight="bold", color="#7a2520")
    xs = [0.3, 5.2, 10.1, 15.0, 19.9]
    texts = ["블랙박스\n영상", "카메라 포즈·깊이\n·스케일 추정\n(COLMAP+단안Depth)",
             "Dense\n포인트클라우드", "3D Gaussian\nSplatting 배경", "웹 뷰어"]
    fcs = [C_IN, C_PROC, C_PROC, C_BAD, C_OUT]
    y = 8.9
    for i, (x, t, fc) in enumerate(zip(xs, texts, fcs)):
        box(ax, x, y, bw, bh, t, fc=fc, fs=10.5)
        if i < len(xs) - 1:
            arrow(ax, x + bw, y + bh / 2, xs[i + 1], y + bh / 2)
    # 문제 주석
    label(ax, 15.0 + bw / 2, 8.2, "▲ 전방 주행 단안영상 = 낮은 시차(parallax)\n→ 포즈 부정확 · 3DGS는 고정밀 포즈 요구 → 배경 복원 실패",
          fs=10, color="#b3261e", weight="bold")

    # 화살표(아래로, 전환)
    arrow(ax, 12.6, 7.7, 12.6, 6.5, color="#888", lw=2.4)
    label(ax, 13.0, 7.1, "설계 변경", fs=11, ha="left", color="#555", style="italic")

    # 변경 후
    label(ax, 0.3, 5.6, "[변경 후]  LingBot-MAP 포인트클라우드 배경", fs=13, ha="left", weight="bold", color="#274f2e")
    xs2 = [0.3, 5.2, 10.1, 15.0, 19.9]
    texts2 = ["블랙박스\n영상", "동적 객체\n마스킹·추적\n(YOLO+ByteTrack)",
              "LingBot-MAP\n3D 재구성\n(feed-forward)", "포인트클라우드 배경\n+ 차량 배치(IPM)", "웹 뷰어"]
    fcs2 = [C_IN, C_PROC, C_LB, C_PROC, C_OUT]
    y2 = 2.3
    for i, (x, t, fc) in enumerate(zip(xs2, texts2, fcs2)):
        box(ax, x, y2, bw, bh, t, fc=fc, fs=10.5)
        if i < len(xs2) - 1:
            arrow(ax, x + bw, y2 + bh / 2, xs2[i + 1], y2 + bh / 2)
    label(ax, 10.1 + bw / 2, 1.55, "▲ 포즈 노이즈에 강건한 단일 신경망 → 점 구름으로 안정적 배경 복원",
          fs=10, color="#274f2e", weight="bold")

    fig.tight_layout()
    p = os.path.join(FIG_DIR, "fig1_before_after.png")
    fig.savefig(p, dpi=170, bbox_inches="tight"); plt.close(fig)
    return p


# ── 그림 2: LingBot 내부 구조 + 3 컨텍스트 ──────────────────
def fig2():
    fig, ax = new_ax(12.6, 6.6, (0, 25.2), (0, 13.2))

    # 좌측: 파이프라인 (세로)
    cx, w, h = 1.2, 7.6, 1.45
    ys = [11.0, 8.9, 6.8, 4.7, 2.0]
    texts = ["입력: 영상 프레임 (스트림)",
             "ViT 백본 (DINOv2 초기화)\n→ 프레임별 토큰",
             "토큰: 이미지(M) + 카메라 + register×4 + anchor",
             "Frame Attention(프레임 내)\n+ GCA(프레임 간)  ×L 레이어",
             "카메라 Head → 포즈   |   Depth Head → 깊이\n( → 포인트클라우드 )"]
    fcs = [C_IN, C_LB, C_NEU, C_LB, C_OUT]
    for i, (yy, t, fc) in enumerate(zip(ys, texts, fcs)):
        bb = h if i != 3 else h
        box(ax, cx, yy, w, bb, t, fc=fc, fs=10.5, bold=(i == 3))
        if i < len(ys) - 1:
            arrow(ax, cx + w / 2, yy, cx + w / 2, ys[i + 1] + bb, lw=2.2)
    label(ax, cx + w / 2, 12.7, "LingBot-MAP 내부 (한 번의 forward, 최적화 없음)",
          fs=12, weight="bold", color="#2a2150")

    # 우측: GCA 3 컨텍스트
    rx, rw, rh = 16.8, 7.8, 2.0
    label(ax, rx + rw / 2, 12.7, "핵심: Geometric Context Attention (GCA)",
          fs=12, weight="bold", color="#2a2150")
    label(ax, rx + rw / 2, 11.85, "스트리밍 상태를 3가지 맥락으로 압축 유지", fs=10, color="#555", style="italic")
    ctx = [
        ("① Anchor (앵커)", "첫 몇 프레임을 고정 기준으로 사용\n→ 좌표·스케일 grounding\n(단안 스케일 모호성 해결)", "#e7eefc"),
        ("② Local Window (지역 창)", "최근 k개 프레임의 전체 토큰 유지\n→ 정밀한 프레임 정합", "#e6f3ea"),
        ("③ Trajectory Memory (궤적 기억)", "그 외 과거는 6토큰만 압축 보관\n→ 장기 누적 드리프트 보정", "#fff2e0"),
    ]
    yy = 9.2
    for title, body, fc in ctx:
        box(ax, rx, yy, rw, rh, "", fc=fc, fs=10)
        ax.text(rx + 0.3, yy + rh - 0.45, title, ha="left", va="center", fontsize=10.5, weight="bold", color=TC)
        ax.text(rx + 0.3, yy + rh / 2 - 0.35, body, ha="left", va="center", fontsize=9.6, color="#333", linespacing=1.3)
        yy -= 2.55
    label(ax, rx + rw / 2, 1.4, "→ 긴 영상에서도 거의 일정한 연산량 / ~20FPS",
          fs=10, color="#274f2e", weight="bold")

    fig.tight_layout()
    p = os.path.join(FIG_DIR, "fig2_lingbot.png")
    fig.savefig(p, dpi=170, bbox_inches="tight"); plt.close(fig)
    return p


# ── 그림 3: 최종 시스템 전체 파이프라인 ─────────────────────
def fig3():
    fig, ax = new_ax(12.6, 5.8, (0, 25.2), (0, 11.6))
    bw, bh = 3.7, 1.7
    xs = [0.3, 4.6, 8.9, 13.2]
    texts = ["블랙박스\n영상", "Stage 02\n프레임 추출",
             "Stage 03\n동적객체 분할·추적\n(YOLOv8-seg+ByteTrack\n+ego-motion 보정)",
             "LingBot-MAP\n3D 재구성"]
    fcs = [C_IN, C_PROC, C_PROC, C_LB]
    y = 7.6
    for i, (x, t, fc) in enumerate(zip(xs, texts, fcs)):
        box(ax, x, y, bw, bh, t, fc=fc, fs=9.8)
        if i < len(xs) - 1:
            arrow(ax, x + bw, y + bh / 2, xs[i + 1], y + bh / 2)

    # LingBot → 두 산출물
    ox = 17.6
    box(ax, ox, 9.1, 3.6, 1.2, "배경 .splat\n(점 구름)", fc=C_OUT, fs=9.8)
    box(ax, ox, 6.9, 3.6, 1.2, "vehicles.json\n(ego + 동적차량)", fc=C_OUT, fs=9.8)
    arrow(ax, xs[3] + bw, y + bh / 2, ox, 9.7)
    arrow(ax, xs[3] + bw, y + bh / 2, ox, 7.5)

    # 산출물 → 웹뷰어
    box(ax, 9.5, 2.0, 6.2, 2.0, "웹 뷰어 (React + Three.js)\n점구름 배경 + ego + 동적차량\n재생 · 타깃차량 선택 · 원본프레임",
        fc="#e7eefc", fs=10.2, bold=True)
    arrow(ax, ox, 9.1, 12.6, 4.0, color="#9a7b3a")
    arrow(ax, ox, 6.9, 13.4, 4.0, color="#9a7b3a")

    # 배경 생성 주석
    label(ax, ox + 1.8, 10.7, "배경: sky/동적 마스킹 + 신뢰도 필터\n+ 지면정렬(+Y) + 원점정렬",
          fs=8.8, color="#555")
    label(ax, ox + 1.8, 6.0, "차량: IPM(역원근) — 아래 그림4",
          fs=8.8, color="#555")
    label(ax, 12.6, 0.7, "* 인증·대시보드·업로드 = 웹 백엔드(Spring)에서 잡 관리",
          fs=9, color="#777", style="italic")
    label(ax, 12.6, 11.1, "최종 시스템 데이터 흐름", fs=13, weight="bold", color="#15242e")

    fig.tight_layout()
    p = os.path.join(FIG_DIR, "fig3_system.png")
    fig.savefig(p, dpi=170, bbox_inches="tight"); plt.close(fig)
    return p


# ── 그림 4: IPM 차량 배치 개념 ──────────────────────────────
def fig4():
    fig, ax = new_ax(11.0, 5.2, (0, 22), (0, 10.4))
    # 도로(지면)
    ax.plot([1, 21], [2.0, 2.0], color="#7a7a7a", lw=2)
    label(ax, 21, 1.55, "도로(지면)", fs=10, ha="right", color="#555")
    # 카메라(ego)
    camx, camy = 2.0, 4.6
    box(ax, 1.0, 4.0, 2.4, 1.3, "ego 카메라\n(블랙박스)", fc=C_IN, fs=9.5)
    label(ax, 2.2, 3.2, "높이 H", fs=10, color="#444")
    ax.plot([camx, camx], [2.0, camy], color="#bbb", lw=1, ls=":")
    # 광선 두 개 (앞차/뒤차)
    targets = [(17.0, "앞차\n(이미지 위쪽, v 작음 → 먼 거리)", "#274f2e"),
               (9.5, "뒤차\n(이미지 아래쪽, v 큼 → 가까움)", "#7a2520")]
    for tx, ttl, col in targets:
        ax.plot([camx, tx], [camy, 2.0], color=col, lw=1.6, ls="--")
        # 차량 박스(지면 위)
        box(ax, tx - 0.9, 2.0, 1.8, 1.1, "", fc="#fde9c8", ec=col, lw=1.6)
        label(ax, tx, 3.7, ttl, fs=9.2, color=col)
    # 수식/설명
    label(ax, 11, 9.3, "차량 배치: 이미지 박스 '바닥 행(v)'으로 거리 결정",
          fs=12.5, weight="bold", color="#15242e")
    label(ax, 11, 8.45, "D = H · fy / (v - v0)   ·   ego 진행방향으로 D만큼, 옆으로 L만큼 배치",
          fs=10.5, color="#333")
    label(ax, 11, 7.7, "v가 작을수록(이미지 위) 거리 D 큼 → 앞뒤 순서 보장",
          fs=10, color="#274f2e", style="italic")
    label(ax, 11, 0.7, "※ LingBot 전방주행 포즈의 회전(yaw)은 신뢰도 낮음 → 신뢰 가능한 'ego 경로+지면+이미지'만 사용",
          fs=9.2, color="#777", style="italic")
    fig.tight_layout()
    p = os.path.join(FIG_DIR, "fig4_ipm.png")
    fig.savefig(p, dpi=170, bbox_inches="tight"); plt.close(fig)
    return p


def convert_paper_fig():
    """논문 공식 파이프라인 그림(webp)을 png로 변환(있으면)."""
    if not LINGBOT_DIR:
        print("[skip] LINGBOT_MAP_DIR 미설정 — 논문 파이프라인 그림 생략")
        return None
    src = os.path.join(LINGBOT_DIR, "Pipeline of LingBot-Map.webp")
    if not os.path.exists(src):
        print(f"[skip] 논문 그림 없음: {src}")
        return None
    try:
        from PIL import Image
        im = Image.open(src).convert("RGB")
        p = os.path.join(FIG_DIR, "fig_paper_pipeline.png")
        im.save(p)
        return p
    except Exception as e:
        print("paper fig 변환 실패:", e)
        return None


# ── Word 문서 ───────────────────────────────────────────────
def build_docx(figs):
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    doc = Document()
    # 기본 폰트(한글 포함)
    normal = doc.styles["Normal"]
    normal.font.size = Pt(11)
    try:
        normal.font.name = "Apple SD Gothic Neo"
        normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Apple SD Gothic Neo")
    except Exception:
        pass

    def cap(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        r.italic = True; r.font.size = Pt(9.5); r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    def pic(path, width=6.4):
        if path and os.path.exists(path):
            doc.add_picture(path, width=Inches(width))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    def bullet(text):
        doc.add_paragraph(text, style="List Bullet")

    doc.add_heading("교통사고 3D 재현 시스템 — 시스템 구조 및 설계 정리", 0)
    doc.add_paragraph("단안(블랙박스/스마트폰) 사고 영상으로부터 3D 장면과 차량 궤적을 복원해 웹에서 재생하는 시스템의 내부 구조와 설계 변경 과정을 정리한다.")

    # 1
    doc.add_heading("1. 시스템 설계의 변화 (원래 → 문제 → 수정)", 1)
    doc.add_heading("1.1 원래 계획", 2)
    doc.add_paragraph("단안 영상에서 카메라 포즈(COLMAP)·단안 깊이·스케일을 추정해 조밀한 포인트클라우드를 만들고, 이를 초기값으로 3D Gaussian Splatting(3DGS) 으로 사진 같은 배경을 복원한 뒤, 그 위에 동적 차량 3D 모델을 궤적대로 올려 웹에서 보여주는 구조였다.")
    doc.add_heading("1.2 문제점 (구조적)", 2)
    doc.add_paragraph("전방 주행 블랙박스 영상은 카메라가 보는 방향으로 거의 직진하기 때문에 시점 간 시차(parallax)가 매우 작다. 이런 입력에서는 다음이 구조적으로 성립한다.")
    bullet("COLMAP 같은 기하 기반 포즈 추정의 정확도가 떨어진다(직진 = 삼각측량 정보 부족).")
    bullet("3DGS는 mm·sub-degree 수준의 정밀한 카메라 포즈를 요구한다 → 포즈 오차가 곧바로 배경 붕괴로 이어진다.")
    bullet("결과적으로 배경이 형체를 알아볼 수 없는 뾰족한 잡음(스파이크) 으로 무너졌고, 학습 반복(iteration)을 늘려도 해결되지 않았다.")
    doc.add_heading("1.3 수정 계획", 2)
    doc.add_paragraph("배경 생성 부분만 단일 feed-forward 신경망인 LingBot-MAP의 포인트클라우드로 교체했다. LingBot은 포즈 노이즈에 강건해 직진 영상에서도 안정적인 점 구름 배경을 만든다. 동적 객체 마스킹, 차량 3D 오버레이, 웹 뷰어라는 전체 골격은 그대로 유지했다(=배경 엔진만 교체).")
    pic(figs["f1"]); cap("그림 1. 변경 전(COLMAP+3DGS) vs 변경 후(LingBot 포인트클라우드) 파이프라인 비교")

    # 2
    doc.add_heading("2. LingBot-MAP 이해", 1)
    doc.add_paragraph("LingBot-MAP은 “Geometric Context Transformer for Streaming 3D Reconstruction”으로 발표된 단안 영상용 3D 재구성 파운데이션 모델이다. 영상 스트림을 입력하면 프레임마다 카메라 포즈 + 조밀한 깊이(depth) + 포인트클라우드를 한 번의 forward로 예측한다. 장면별 추가 최적화나 test-time 학습이 없어 빠르고(약 20FPS), 1만 프레임 이상 긴 영상도 안정적으로 처리한다.")
    doc.add_paragraph("핵심 아이디어는 사람이 길을 기억하는 방식과 비슷하다. 모든 장면을 똑같이 저장하지 않고 “꼭 필요한 맥락만” 선택적으로 유지한다. 이를 Geometric Context Attention(GCA)이라 하며, 스트리밍 상태를 세 가지 맥락으로 나눠 압축한다.")
    bullet("Anchor(앵커): 맨 앞 몇 프레임을 고정 기준으로 삼아 전체 좌표계와 스케일을 잡아준다(단안 영상의 크기 모호성 해결).")
    bullet("Local Window(지역 창): 최근 몇 프레임은 정보를 전부 유지해, 새 프레임을 정밀하게 끼워 맞춘다.")
    bullet("Trajectory Memory(궤적 기억): 그보다 오래된 과거는 프레임당 6개 토큰으로만 압축 보관해, 오래 누적되는 위치 오차(드리프트)를 바로잡는다.")
    doc.add_paragraph("구조적으로는 ViT 백본(DINOv2로 초기화)이 각 프레임을 토큰으로 바꾸고, Frame Attention(프레임 내부)과 GCA(프레임 사이)가 번갈아 작동한 뒤, 카메라 Head가 포즈를, Depth Head가 깊이를 예측한다. 이 “필요한 맥락만 유지” 설계 덕분에 영상이 길어져도 프레임당 연산량이 거의 일정하게 유지된다.")
    pic(figs["f2"]); cap("그림 2. LingBot-MAP 내부 구조와 GCA의 3가지 맥락")
    if figs.get("fp"):
        pic(figs["fp"], width=6.4); cap("그림 2-1. (참고) LingBot-MAP 논문의 공식 파이프라인 그림")
    doc.add_paragraph("본 프로젝트에서는 LingBot을 자체 뷰어가 아니라 배경 지도 생성 엔진으로만 사용한다. 공개된 long 체크포인트는 포즈와 깊이를 출력하므로, 깊이를 역투영(back-projection)해 포인트클라우드 배경을 얻는다.")

    # 3
    doc.add_heading("3. 최종 시스템 구조", 1)
    doc.add_paragraph("전체 데이터 흐름은 다음과 같다. 입력 영상 → 프레임 추출 → 동적 객체 분할·추적 → LingBot 3D 재구성 → 배경(.splat)과 차량(vehicles.json) 산출 → 웹 뷰어 재생.")
    doc.add_heading("3.1 전처리 — 동적 객체 마스킹·추적", 2)
    doc.add_paragraph("Stage 02에서 영상을 프레임으로 추출하고, Stage 03에서 YOLOv8-seg로 차량 등 동적 객체를 분할하고 ByteTrack으로 추적한다. 카메라 자체 움직임(ego-motion)을 보정해, 같은 속도로 함께 움직이는 앞차를 배경으로 오인하지 않도록 한다. 결과로 프레임별 동적 마스크와 추적 ID·박스 시퀀스를 만든다.")
    doc.add_heading("3.2 배경 생성", 2)
    doc.add_paragraph("LingBot 결과에 하늘·동적객체 마스킹과 신뢰도 필터를 적용하고, 도로 평면을 추정해 위쪽(+Y)으로 정렬한 뒤 원점에 맞춘다. 최종 산출물은 웹에서 바로 그릴 수 있는 .splat 점 구름이다.")
    doc.add_heading("3.3 차량 배치 — 역원근(IPM)", 2)
    doc.add_paragraph("LingBot의 직진 영상 포즈는 위치(경로)는 안정적이지만 회전(특히 진행방향/yaw)의 신뢰도가 낮다. 따라서 회전에 의존하는 깊이 기반 배치 대신, 신뢰 가능한 정보(ego 카메라 경로 + 지면 + 이미지 박스의 바닥 행)만으로 차량을 배치하는 역원근 매핑(IPM)을 사용한다. 박스의 바닥 행 v가 위쪽일수록(=멀수록) 진행방향으로 더 멀리 놓이므로, 차량의 앞뒤 순서가 보장된다. ego(블랙박스) 차량은 카메라 경로에 그대로 배치한다.")
    pic(figs["f4"], width=5.6); cap("그림 4. 역원근(IPM) 기반 차량 배치 — 이미지 박스 바닥 행으로 거리 결정")
    doc.add_heading("3.4 웹 뷰어", 2)
    doc.add_paragraph("React + Three.js 뷰어가 점 구름 배경 위에 ego와 동적 차량 N대를 올려 시간축으로 재생한다. 사용자는 원본 프레임 패널에서 추적 ID를 보고, 보고 싶은 사고 당사자 차량만 선택해 볼 수 있다. 로그인·대시보드·영상 업로드 등 잡(job) 관리는 별도 웹 백엔드(Spring)가 담당한다.")
    pic(figs["f3"]); cap("그림 3. 최종 시스템 전체 데이터 흐름")

    out = os.path.join(OUT_DIR, "사고재현_시스템구조_정리.docx")
    doc.save(out)
    return out


def main():
    figs = {"f1": fig1(), "f2": fig2(), "f3": fig3(), "f4": fig4(), "fp": convert_paper_fig()}
    out = build_docx(figs)
    print("\n=== 완료 ===")
    print("DOCX :", out)
    for k, v in figs.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
