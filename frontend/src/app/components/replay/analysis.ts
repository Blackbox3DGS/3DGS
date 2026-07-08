// 사고 재현 분석 — 순수 함수 모음 (Three.js/React 비의존, 단위 테스트 가능).
//
// 좌표는 Viewer3D 엔진이 쓰는 스무딩+미러 적용 후의 [x, y, z, frame_idx] 배열.
// 거리·속도는 미러/회전 불변이라 어느 쪽을 넣어도 결과가 같다.
//
// 미터 환산: vehicles.json의 `meters_per_unit`(파이프라인이 기록) 우선, 없으면
// 카메라 높이 prior(블랙박스 ≈1.4 m) / median(ego_y − 노면 y) 로 근사한다.
// Waymo GT 교차검증(13_eval)에서 이 prior 스케일은 Umeyama 스케일 대비 1.9%
// 오차로 확인됨 — 단안 추정이므로 UI에는 "≈"와 함께 표기한다.

export interface VehicleTrack {
  id: string;
  isEgo: boolean;
  points: number[][]; // [x, y, z, frame_idx]
}

export interface ScaleInfo {
  metersPerUnit: number | null;
  source: 'data' | 'prior' | 'none';
  cameraHeightPriorM: number;
}

export interface ClosestApproach {
  frame: number;
  aId: string;
  bId: string;
  distanceUnits: number;
}

export const DEFAULT_CAMERA_HEIGHT_M = 1.4; // 승용차 대시보드 블랙박스 prior

// ── 스케일 ────────────────────────────────────────────────────────────────────

export function computeMetersPerUnit(
  meta: { meters_per_unit?: unknown; camera_height_prior_m?: unknown } | null,
  egoPoints: number[][] | null,
  groundAt: ((x: number, z: number) => number) | null,
  cameraHeightPriorM: number = DEFAULT_CAMERA_HEIGHT_M,
): ScaleInfo {
  const fromData = Number(meta?.meters_per_unit);
  const prior = Number(meta?.camera_height_prior_m) || cameraHeightPriorM;
  if (Number.isFinite(fromData) && fromData > 0) {
    return { metersPerUnit: fromData, source: 'data', cameraHeightPriorM: prior };
  }
  if (egoPoints && egoPoints.length >= 3) {
    const heights = egoPoints
      .map((p) => p[1] - (groundAt ? groundAt(p[0], p[2]) : 0))
      .filter((h) => Number.isFinite(h))
      .sort((a, b) => a - b);
    const med = heights[Math.floor(heights.length / 2)];
    if (Number.isFinite(med) && med > 1e-9) {
      return { metersPerUnit: prior / med, source: 'prior', cameraHeightPriorM: prior };
    }
  }
  return { metersPerUnit: null, source: 'none', cameraHeightPriorM: prior };
}

// ── 프레임 샘플 유틸 ──────────────────────────────────────────────────────────

// 정수 프레임 f의 트랙 위치(구간 밖이면 null). points는 frame_idx 오름차순.
export function positionAtFrame(points: number[][], f: number): [number, number, number] | null {
  const n = points.length;
  if (!n) return null;
  const t0 = points[0][3] ?? 0;
  const t1 = points[n - 1][3] ?? n - 1;
  if (f < t0 - 0.5 || f > t1 + 0.5) return null;
  const target = Math.max(t0, Math.min(t1, f));
  let i = 0;
  while (i < n - 2 && (points[i + 1][3] ?? i + 1) < target) i++;
  const a = points[i];
  const b = points[Math.min(i + 1, n - 1)];
  const at = a[3] ?? i;
  const bt = b[3] ?? i + 1;
  const lt = Math.max(0, Math.min(1, (target - at) / Math.max(1e-6, bt - at)));
  return [a[0] + (b[0] - a[0]) * lt, a[1] + (b[1] - a[1]) * lt, a[2] + (b[2] - a[2]) * lt];
}

function distXZ(a: [number, number, number], b: [number, number, number]): number {
  const dx = a[0] - b[0];
  const dz = a[2] - b[2];
  return Math.sqrt(dx * dx + dz * dz);
}

// ── 속도 ─────────────────────────────────────────────────────────────────────

// 정수 프레임별 속도(km/h). ±half 프레임 중앙차분 — 13_eval의 속도 지표와 동일 방식.
export function computeSpeedSeries(
  points: number[][],
  fps: number,
  metersPerUnit: number,
  half: number = 2,
): Map<number, number> {
  const out = new Map<number, number>();
  const n = points.length;
  if (n < 2 || !(metersPerUnit > 0)) return out;
  const t0 = Math.ceil(points[0][3] ?? 0);
  const t1 = Math.floor(points[n - 1][3] ?? n - 1);
  for (let f = t0; f <= t1; f++) {
    const fa = Math.max(t0, f - half);
    const fb = Math.min(t1, f + half);
    if (fb <= fa) continue;
    const pa = positionAtFrame(points, fa);
    const pb = positionAtFrame(points, fb);
    if (!pa || !pb) continue;
    const mps = (distXZ(pa, pb) * metersPerUnit) / ((fb - fa) / fps);
    out.set(f, mps * 3.6);
  }
  return out;
}

// ── 최근접(충돌 후보) 시점 ────────────────────────────────────────────────────

// 모든 활성 차량쌍(ego 포함)의 프레임별 최소거리 → 전체 최솟값 프레임.
export function computeClosestApproach(tracks: VehicleTrack[]): ClosestApproach | null {
  if (tracks.length < 2) return null;
  let t0 = Infinity;
  let t1 = -Infinity;
  for (const tr of tracks) {
    if (!tr.points.length) continue;
    t0 = Math.min(t0, tr.points[0][3] ?? 0);
    t1 = Math.max(t1, tr.points[tr.points.length - 1][3] ?? 0);
  }
  if (!Number.isFinite(t0) || t1 <= t0) return null;

  let best: ClosestApproach | null = null;
  for (let f = Math.ceil(t0); f <= Math.floor(t1); f++) {
    const pos: Array<{ id: string; p: [number, number, number] }> = [];
    for (const tr of tracks) {
      const p = positionAtFrame(tr.points, f);
      if (p) pos.push({ id: tr.id, p });
    }
    for (let i = 0; i < pos.length; i++) {
      for (let j = i + 1; j < pos.length; j++) {
        const d = distXZ(pos[i].p, pos[j].p);
        if (!best || d < best.distanceUnits) {
          best = { frame: f, aId: pos[i].id, bId: pos[j].id, distanceUnits: d };
        }
      }
    }
  }
  return best;
}

// 한 쌍의 프레임별 거리(units). 타임라인 스파크라인/디버그용.
export function pairDistanceSeries(a: number[][], b: number[][]): Map<number, number> {
  const out = new Map<number, number>();
  if (!a.length || !b.length) return out;
  const t0 = Math.ceil(Math.max(a[0][3] ?? 0, b[0][3] ?? 0));
  const t1 = Math.floor(Math.min(a[a.length - 1][3] ?? 0, b[b.length - 1][3] ?? 0));
  for (let f = t0; f <= t1; f++) {
    const pa = positionAtFrame(a, f);
    const pb = positionAtFrame(b, f);
    if (pa && pb) out.set(f, distXZ(pa, pb));
  }
  return out;
}
