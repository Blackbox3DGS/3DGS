#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""README 다이어그램 생성 — SVG 작성 후 PNG 래스터화.

설계 규칙
  · 연결선은 직교(가로/세로)와 r=8 둥근 코너만 사용. 대각선 금지.
  · 존(zone)은 화살표·노드보다 먼저 그려 z-order 를 뒤로 보냄.
  · 강조색은 다이어그램당 1~2개 노드에만. 그 이상은 위계 소실.
  · 모든 좌표와 간격은 4의 배수.
  · 글자 크기는 두 가지(LARGE/SMALL). 위계는 굵기와 색으로 표현.
  · 작은 사각형 안의 작은 글씨(배지) 사용 금지. 존 라벨도 평문.

색은 발표자료 팔레트에서 가져온다 — 딥그린 배경, 틸 강조, 흰 본문.

사용법
    python3 tools/make_diagrams.py            # SVG + PNG
    python3 tools/make_diagrams.py --svg-only # SVG 만
PNG 래스터화에는 playwright(chromium) 가 필요하다:
    pip install playwright && playwright install chromium
Pretendard 가 시스템에 설치되어 있어야 의도한 서체로 렌더된다.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "figures"

# ── 토큰 ────────────────────────────────────────────────────────────────────
PAPER = "#0F2E1F"          # 배경
PAPER_2 = "#17402D"        # 노드 면
INK = "#FFFFFF"            # 본문
MUTED = "#A8C6B8"          # 보조 텍스트, 화살표
SOFT = "#8FB2A1"           # 서브라벨
RULE = "rgba(255,255,255,0.16)"
ACCENT = "#5CBFAE"         # 강조 (1~2개 노드)
ACCENT_TINT = "rgba(92,191,174,0.13)"
ZONE_FILL = "rgba(255,255,255,0.030)"
ZONE_RULE = "rgba(255,255,255,0.10)"

FONT = "Pretendard, -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', sans-serif"
LARGE = 18                 # 제목, 노드 이름
SMALL = 13                 # 서브라벨, 존 라벨, 화살표 라벨

R = 8                      # 코너 반경
LH = 17                    # 서브라벨 줄간격


# ── 텍스트 폭 검사 ──────────────────────────────────────────────────────────
_FONTS: dict = {}
_WARN: list = []


_FONT_DIRS = ("~/Library/Fonts", "/Library/Fonts", "/System/Library/Fonts",
              "~/.local/share/fonts", "/usr/share/fonts", "/usr/local/share/fonts")


def _font_file(weight: int):
    """설치된 Pretendard 파일 경로. 없으면 None."""
    face = "SemiBold" if weight == 600 else ("Bold" if weight >= 700 else "Regular")
    for d in _FONT_DIRS:
        base = Path(d).expanduser()
        if not base.is_dir():
            continue
        for ext in ("otf", "ttf"):
            hit = sorted(base.rglob(f"Pretendard-{face}.{ext}"))
            if hit:
                return hit[0]
    return None


def _font(size: int, weight: int):
    """폭 측정용 PIL 폰트. Pretendard 나 PIL 이 없으면 None (검사 생략)."""
    key = (size, weight)
    if key not in _FONTS:
        try:
            from PIL import ImageFont
            f = _font_file(weight)
            _FONTS[key] = ImageFont.truetype(str(f), size) if f else None
        except Exception:
            _FONTS[key] = None
    return _FONTS[key]


def measure(s: str, size: int, weight: int = 400):
    f = _font(size, weight)
    return None if f is None else f.getlength(s)


def check(s: str, avail: float, size: int, weight: int, where: str):
    w = measure(s, size, weight)
    if w is not None and w > avail:
        _WARN.append(f"{where}: {w:.0f}px > {avail:.0f}px  \u2014  {s!r}")


# ── 프리미티브 ──────────────────────────────────────────────────────────────
def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text(x, y, s, size=SMALL, fill=MUTED, weight=400, anchor="start", spacing=None):
    ls = f' letter-spacing="{spacing}"' if spacing else ""
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{ls}>{esc(s)}</text>')


def title(x, y, s):
    return text(x, y, s, size=LARGE, fill=INK, weight=700)


def zone(x, y, w, h, label, align="left"):
    """존 사각형 + 평문 라벨. 라벨 배경 마스크(배지) 없음.

    라벨은 존 상단 여백(32px)에 놓이므로 첫 노드와 겹치지 않는다.
    align="right" 는 라벨이 진입 화살표와 충돌할 때 쓴다.
    """
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{R}" '
           f'fill="{ZONE_FILL}" stroke="{ZONE_RULE}" stroke-width="1"/>']
    if label:
        lx, anchor = (x + w - 16, "end") if align == "right" else (x + 16, "start")
        out.append(text(lx, y + 21, label, size=SMALL, fill=SOFT, weight=600,
                        anchor=anchor, spacing="0.06em"))
    return "\n".join(out)


def node(x, y, w, h, name, subs=(), focal=False):
    """노드 한 칸. subs 는 서브라벨 줄 목록."""
    stroke = ACCENT if focal else RULE
    fill = ACCENT_TINT if focal else PAPER_2
    name_fill = ACCENT if focal else INK
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{R}" '
           f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>']
    subs = [s for s in subs if s]
    check(name, w - 32, LARGE, 600, f"node {name!r}")
    for s_ in subs:
        check(s_, w - 32, SMALL, 400, f"sub of {name!r}")
    block = LARGE + (LH * len(subs) if subs else 0)
    top = y + (h - block) / 2 + LARGE - 4
    out.append(text(x + 16, top, name, size=LARGE, fill=name_fill, weight=600))
    for i, s in enumerate(subs):
        out.append(text(x + 16, top + 6 + LH * (i + 1), s, size=SMALL, fill=SOFT))
    return "\n".join(out)


def _stroke(color, dashed):
    d = ' stroke-dasharray="4,3"' if dashed else ""
    w = 1 if dashed else 1.2
    return f'stroke="{color}" stroke-width="{w}"{d}'


def harrow(x1, x2, y, color=MUTED, dashed=False, label=None, label_dy=-8):
    """수평 화살표."""
    out = [f'<path d="M {x1},{y} H {x2}" fill="none" {_stroke(color, dashed)} '
           f'marker-end="url(#tip)"/>']
    if label:
        out.append(text((x1 + x2) / 2, y + label_dy, label, size=SMALL, fill=SOFT, anchor="middle"))
    return "\n".join(out)


def varrow(x, y1, y2, color=MUTED, dashed=False, label=None, label_dx=10):
    """수직 화살표."""
    out = [f'<path d="M {x},{y1} V {y2}" fill="none" {_stroke(color, dashed)} '
           f'marker-end="url(#tip)"/>']
    if label:
        out.append(text(x + label_dx, (y1 + y2) / 2 + 4, label, size=SMALL, fill=SOFT))
    return "\n".join(out)


def elbow_dv(x1, y1, ych, x2, y2, color=MUTED, dashed=False, label=None):
    """아래로 → 수평 채널 → 아래로. 세 구간 모두 직교, 코너는 r=8."""
    sx = 1 if x2 > x1 else -1
    d = (f"M {x1},{y1} V {ych - R} "
         f"Q {x1},{ych} {x1 + sx * R},{ych} "
         f"H {x2 - sx * R} "
         f"Q {x2},{ych} {x2},{ych + R} "
         f"V {y2}")
    out = [f'<path d="{d}" fill="none" {_stroke(color, dashed)} marker-end="url(#tip)"/>']
    if label:
        out.append(text((x1 + x2) / 2, ych - 8, label, size=SMALL, fill=SOFT, anchor="middle"))
    return "\n".join(out)


def elbow_hv(x1, y1, x2, y2, color=MUTED, dashed=False):
    """수평 → 코너 → 수직. 도착 노드의 위/아래 면으로 진입."""
    sy = 1 if y2 > y1 else -1
    d = (f"M {x1},{y1} H {x2 - R} "
         f"Q {x2},{y1} {x2},{y1 + sy * R} "
         f"V {y2}")
    return (f'<path d="{d}" fill="none" {_stroke(color, dashed)} marker-end="url(#tip)"/>')


def rule_h(x1, x2, y, color=RULE, w=1):
    return f'<path d="M {x1},{y} H {x2}" stroke="{color}" stroke-width="{w}" fill="none"/>'


def svg(w, h, body, desc):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"
     viewBox="0 0 {w} {h}" role="img" aria-label="{esc(desc)}">
  <title>{esc(desc)}</title>
  <defs>
    <marker id="tip" viewBox="0 0 8 8" refX="7" refY="4"
            markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0,1 L 7,4 L 0,7 z" fill="{MUTED}"/>
    </marker>
    <marker id="tipa" viewBox="0 0 8 8" refX="7" refY="4"
            markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0,1 L 7,4 L 0,7 z" fill="{ACCENT}"/>
    </marker>
  </defs>
  <rect width="{w}" height="{h}" fill="{PAPER}"/>
{body}
</svg>
"""


# ── 1. 시스템 아키텍처 ──────────────────────────────────────────────────────
def architecture():
    W, H = 860, 616
    c1, c2, c3, cw = 48, 308, 568, 244
    m1, m2, m3 = c1 + cw / 2, c2 + cw / 2, c3 + cw / 2
    p = [title(32, 44, "ReScene 시스템 아키텍처")]

    # 존을 먼저 그려 z-order 를 뒤로 보낸다.
    # 라벨을 오른쪽에 두어 진입 화살표(m1)와 겹치지 않게 한다.
    p.append(zone(32, 200, 796, 232, "AI Pipeline · Python · GPU", align="right"))
    p.append(zone(32, 464, 536, 116, "Web Service"))

    p.append(varrow(m1, 164, 232))
    p.append(harrow(c1 + cw, c2, 268))
    p.append(harrow(c2 + cw, c3, 268))
    p.append(elbow_dv(m3, 304, 324, m1, 344))
    p.append(harrow(c1 + cw, c2, 380))
    p.append(harrow(c2 + cw, c3, 380))
    p.append(varrow(m2, 416, 496, color=ACCENT, label=".splat + vehicles.json"))
    p.append(harrow(c1 + cw, c2, 530))

    p.append(node(c1, 96, cw, 68, "블랙박스 영상", ["단안 mp4 · Waymo TFRecord"]))
    p.append(node(c1, 232, cw, 72, "02 프레임 추출", ["ffmpeg · TFRecord"]))
    p.append(node(c2, 232, cw, 72, "03 탐지·추적", ["YOLOv8-seg + ByteTrack"]))
    p.append(node(c3, 232, cw, 72, "04g LingBot-MAP", ["feed-forward 포즈·깊이"], focal=True))
    p.append(node(c1, 344, cw, 72, "09 궤적", ["IPM + Kalman"]))
    p.append(node(c2, 344, cw, 72, "씬 익스포트", ["m 스케일 환산"]))
    p.append(node(c3, 344, cw, 72, "13 평가", ["Waymo GT 대비"]))
    p.append(node(c1, 496, cw, 68, "Backend", ["Spring Boot · 작업 관리"]))
    p.append(node(c2, 496, cw, 68, "웹 뷰어", ["React + Three.js"], focal=True))

    return svg(W, H, "\n".join(p), "ReScene 시스템 아키텍처")


# ── 2. 미터 스케일 보정 ─────────────────────────────────────────────────────
def scale_calibration():
    W, H = 720, 384
    p = [title(32, 44, "미터 스케일 보정 — 카메라 높이 prior")]
    p.append(zone(32, 72, 312, 280, "씬 좌표계"))
    p.append(zone(376, 72, 312, 280, "환산식"))

    # 왼쪽 — 노면 위의 차량과 카메라, 그리고 씬 단위 높이
    road, cam = 276, 172
    p.append(rule_h(64, 312, road, color=MUTED, w=2))
    p.append(text(188, road + 26, "노면 · y = 0 (지면 정렬 후)", fill=SOFT, anchor="middle"))
    p.append(f'<rect x="140" y="224" width="120" height="52" rx="{R}" '
             f'fill="{PAPER_2}" stroke="{RULE}" stroke-width="1"/>')
    p.append(f'<rect x="164" y="192" width="72" height="32" rx="6" '
             f'fill="{PAPER_2}" stroke="{RULE}" stroke-width="1"/>')
    for wx in (168, 232):
        p.append(f'<circle cx="{wx}" cy="{road}" r="9" fill="{PAPER}" '
                 f'stroke="{MUTED}" stroke-width="1.4"/>')
    # 카메라 → 높이 화살표를 잇는 안내선
    p.append(f'<path d="M 196,{cam} H 104" fill="none" stroke="{ACCENT}" '
             f'stroke-width="1" stroke-dasharray="4,3"/>')
    p.append(f'<circle cx="200" cy="{cam}" r="5" fill="{ACCENT}"/>')
    p.append(text(212, cam + 5, "블랙박스 카메라", fill=ACCENT, weight=600))
    p.append(f'<path d="M 104,{cam} V {road}" fill="none" stroke="{ACCENT}" '
             f'stroke-width="1.2" marker-start="url(#tipa)" marker-end="url(#tipa)"/>')
    p.append(text(92, 216, "ego_y", fill=ACCENT, weight=600, anchor="end"))
    p.append(text(92, 234, "(scene units)", fill=SOFT, anchor="end"))

    # 오른쪽 — 전부 왼쪽 정렬로 통일
    tx = 408
    p.append(text(tx, 140, "meters_per_unit", size=LARGE, fill=ACCENT, weight=700))
    p.append(text(tx, 176, "실제 카메라 높이 (m)", fill=INK))
    p.append(rule_h(tx, 656, 190, color=RULE))
    p.append(text(tx, 212, "median(ego_y)", fill=INK))
    p.append(text(tx, 252, "블랙박스 ≈ 1.4 m", fill=SOFT))
    p.append(text(tx, 272, "Waymo FRONT ≈ 2.115 m", fill=SOFT))
    # 검증 — 배지 대신 왼쪽 강조 규칙선
    p.append(f'<path d="M 392,300 V 336" stroke="{ACCENT}" stroke-width="2" fill="none"/>')
    p.append(text(tx, 314, "Waymo GT Umeyama 스케일 대비", fill=INK))
    p.append(text(tx, 332, "오차 1.9% · sample1 199프레임", fill=SOFT))

    for t, wt in [("실제 카메라 높이 (m)", 400), ("median(ego_y)", 400),
                  ("Waymo GT Umeyama 스케일 대비", 400),
                  ("오차 1.9% · sample1 199프레임", 400),
                  ("Waymo FRONT ≈ 2.115 m", 400)]:
        check(t, 672 - tx, SMALL, wt, "scale 우측")
    check("meters_per_unit", 672 - tx, LARGE, 700, "scale 우측")
    return svg(W, H, "\n".join(p), "미터 스케일 보정 — 카메라 높이 prior")


# ── 3. 사고 재현 뷰어 구조 ──────────────────────────────────────────────────
def viewer_features():
    W, H = 800, 472
    a, aw = 32, 192
    b, bw = 256, 208
    fx, fw = 512, 240
    p = [title(32, 44, "사고 재현 뷰어 구조")]
    p.append(zone(496, 72, 272, 352, "뷰어 기능", align="right"))

    p.append(harrow(a + aw, b, 148))
    p.append(harrow(a + aw, b, 292))
    p.append(harrow(b + bw, 496, 148, color=ACCENT))
    p.append(harrow(b + bw, 496, 292))

    p.append(node(a, 112, aw, 72, "vehicles.json", ["궤적 · meters_per_unit · fps"]))
    p.append(node(a, 256, aw, 72, "background.splat", ["포인트클라우드 배경"]))
    p.append(node(b, 104, bw, 88, "analysis.ts",
                  ["스케일 환산 · 속도 시계열", "최근접 시점 탐색"], focal=True))
    p.append(node(b, 256, bw, 72, "Three.js 씬", ["차량 GLB · 지면 높이맵 · 궤적 라인"]))

    p.append(node(fx, 104, fw, 64, "BEV 탑다운", ["직교 카메라 · 회전 잠금"]))
    p.append(node(fx, 184, fw, 64, "충돌 시점 마커", ["노면 링 · 타임라인 표식"], focal=True))
    p.append(node(fx, 264, fw, 64, "거리·속도 HUD", ["차량쌍 선택 · m / km/h"]))
    p.append(node(fx, 344, fw, 64, "타임라인 스크러버", ["시킹 · 재생/정지"]))

    return svg(W, H, "\n".join(p), "사고 재현 뷰어 구조")


# ── 4. 정량 평가 데이터 흐름 ────────────────────────────────────────────────
def eval_flow():
    W, H = 860, 464
    cw = 192
    c1, c2, c3 = 40, 248, 456
    m2, m3 = c2 + cw / 2, c3 + cw / 2
    c4, c4w = 688, 148
    m4 = c4 + c4w / 2
    p = [title(32, 44, "정량 평가(Stage 13) 데이터 흐름 — Waymo GT 대비")]
    p.append(zone(24, 72, 640, 120, "정답 데이터", align="right"))
    p.append(zone(24, 200, 640, 120, "추정 데이터", align="right"))

    p.append(harrow(c1 + cw, c2, 140))
    p.append(harrow(c2 + cw, c3, 140))
    p.append(harrow(c1 + cw, c2, 268))
    p.append(harrow(c2 + cw, c3, 268))
    p.append(varrow(m3, 176, 232))
    # GT 는 트랙 매칭에도 쓰인다 — 부차 경로이므로 점선, 실선과 겹치지 않게 왼쪽으로 우회
    p.append(elbow_dv(c3 + 40, 176, 204, m2, 232, dashed=True, label="2D IoU 대응"))
    p.append(harrow(c3 + cw, c4, 268, color=ACCENT))
    p.append(elbow_dv(m4, 320, 344, 152, 368))

    p.append(node(c1, 104, cw, 72, "Waymo TFRecord", ["GT 포즈·3D박스·속도"]))
    p.append(node(c2, 104, cw, 72, "extract-gt", ["순수 파이썬 파서"]))
    p.append(node(c3, 104, cw, 72, "gt.json", ["199프레임"]))
    p.append(node(c1, 232, cw, 72, "vehicles.json", ["추정 궤적 · 뷰어 동일"]))
    p.append(node(c2, 232, cw, 72, "트랙 매칭", ["IoU 0.3 초과 다수결"]))
    p.append(node(c3, 232, cw, 72, "좌표 정렬", ["중력구속 2D Umeyama"]))
    p.append(node(c4, 104, c4w, 216, "4대 지표",
                  ["① 위치 오차 (BEV)", "② 상대거리 오차",
                   "③ ADE / FDE", "④ 속도 오차"], focal=True))
    p.append(node(24, 368, 256, 72, "report.md + plots", ["metrics.json · BEV overlay"]))

    return svg(W, H, "\n".join(p), "정량 평가 데이터 흐름 — Waymo GT 대비")


# ── 래스터화 ────────────────────────────────────────────────────────────────
_WRAP = """<!doctype html><meta charset="utf-8">
<style>html,body{{margin:0;padding:0;background:{paper}}}svg{{display:block}}</style>
{svg}"""


def rasterize(svg_path: Path, w: int, h: int, scale: int = 2) -> bool:
    """헤드리스 Chromium 으로 정확히 (w*scale)x(h*scale) PNG 를 만든다.

    Pretendard 는 시스템에 설치되어 있어야 한다 (없으면 대체 폰트로 렌더).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    html = _WRAP.format(paper=PAPER, svg=svg_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        page_file = Path(td) / "page.html"
        page_file.write_text(html, encoding="utf-8")
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": w, "height": h},
                                    device_scale_factor=scale)
            page.goto(page_file.as_uri())
            page.wait_for_timeout(250)          # 웹폰트/레이아웃 안정화
            page.screenshot(path=str(svg_path.with_suffix(".png")))
            browser.close()
    return True


FIGURES = [
    ("architecture", architecture, 860, 616),
    ("scale_calibration", scale_calibration, 720, 392),
    ("viewer_features", viewer_features, 800, 472),
    ("eval_flow", eval_flow, 860, 464),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg-only", action="store_true", help="PNG 래스터화 생략")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    missing_raster = False
    for name, fn, w, h in FIGURES:
        sp = OUT / f"{name}.svg"
        sp.write_text(fn(), encoding="utf-8")
        line = f"  {sp.relative_to(OUT.parents[1])}"
        if not args.svg_only:
            if rasterize(sp, w, h):
                line += f"  →  {name}.png ({w * 2}×{h * 2})"
            else:
                missing_raster = True
        print(line)
    if _WARN:
        print("\n  텍스트 넘침 경고:", file=sys.stderr)
        for w in _WARN:
            print(f"    {w}", file=sys.stderr)
    if missing_raster:
        print("\n  PNG 래스터화 불가 — `pip install playwright && playwright install chromium` 필요.\n  SVG 는 생성되었다.", file=sys.stderr)


if __name__ == "__main__":
    main()
