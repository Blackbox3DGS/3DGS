import {
  Component,
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';

// ─── 상수 ───────────────────────────────────────────────────────────────────

const sampleTrajectoryA = [
  [2.8, 0.05, 1.8],
  [2.3, 0.05, 1.3],
  [1.9, 0.05, 0.8],
  [1.6, 0.05, 0.3],
  [1.5, 0.05, -0.2],
  [1.5, 0.05, -0.8],
];

const sampleTrajectoryB = [
  [0.0, 0.05, 0.0],
  [0.8, 0.05, -0.3],
  [1.6, 0.05, -0.6],
  [2.2, 0.05, -1.0],
  [3.0, 0.05, -1.3],
  [3.8, 0.05, -1.5],
];

// 데모용 기본 차량 모델 경로 (public 폴더)
const DEMO_VEHICLE_URL_A = '/car-a.glb';
const DEMO_VEHICLE_URL_B = '/car-b.glb';

const defaultAccidentPoint = [1.5, 0.06, -0.8];
const CAMERA_ROTATE_SPEED = 0.006;
const CAMERA_PAN_MULTIPLIER = 0.0065;
const CAMERA_DOLLY_IN = 0.84;
const CAMERA_DOLLY_OUT = 1.16;
const CAMERA_MIN_DISTANCE = 2.8;
const CAMERA_MAX_DISTANCE = 40;
const CAMERA_MIN_PHI = 0.35;
const CAMERA_MAX_PHI = Math.PI / 2 - 0.12;

// ─── 타입 ────────────────────────────────────────────────────────────────────

interface Viewer3DProps {
  jobId: string;
  resultUrl?: string;      // Gaussian Splat (.splat) URL
  trajectoryUrl?: string;  // 차량 A 궤적 JSON URL
}

interface OrbitState {
  theta: number;
  phi: number;
  distance: number;
  target: [number, number, number];
}

interface Point3D { x: number; y: number; z: number }
interface NormalizedPoint extends Point3D { t: number | null; index: number; raw: unknown }
interface SampleResult { position: [number, number, number]; next: [number, number, number] }

// ─── 에러 바운더리 ────────────────────────────────────────────────────────────

interface ErrorBoundaryState { hasError: boolean; message: string }

class ViewerErrorBoundary extends Component<{ children: React.ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, message: '' };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, message: error?.message || '알 수 없는 렌더링 오류' };
  }
  componentDidCatch() {}
  render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">
          <div className="font-bold">뷰어 렌더링 오류</div>
          <div className="mt-2 text-sm">{this.state.message}</div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ─── 유틸 함수 ───────────────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function setVectorLike(target: any, x: number, y: number, z: number): boolean {
  if (!target) return false;
  if (typeof target.set === 'function') { target.set(x, y, z); return true; }
  if (Array.isArray(target)) { target[0] = x; target[1] = y; target[2] = z; return true; }
  if (typeof target === 'object') {
    let changed = false;
    if ('x' in target) { target.x = x; changed = true; }
    if ('y' in target) { target.y = y; changed = true; }
    if ('z' in target) { target.z = z; changed = true; }
    return changed;
  }
  return false;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function safeSetGsplatCameraPosition(camera: any, x: number, y: number, z: number) {
  if (!camera) return false;
  return (
    setVectorLike(camera.position, x, y, z) ||
    setVectorLike(camera._position, x, y, z) ||
    setVectorLike(camera.translation, x, y, z)
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function safeReadGsplatPosition(camera: any): Point3D | null {
  const candidate = camera && (camera.position || camera._position || camera.translation);
  if (!candidate) return null;
  if (Array.isArray(candidate) && candidate.length >= 3) {
    return { x: Number(candidate[0]) || 0, y: Number(candidate[1]) || 0, z: Number(candidate[2]) || 0 };
  }
  if (typeof candidate.x === 'number' && typeof candidate.y === 'number' && typeof candidate.z === 'number') {
    return { x: candidate.x, y: candidate.y, z: candidate.z };
  }
  return null;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function safeSetGsplatTarget(controls: any, x: number, y: number, z: number) {
  if (!controls?.target || typeof controls.target.set !== 'function') return false;
  controls.target.set(x, y, z);
  return true;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function copyGsplatCameraToThreeCamera(gsCamera: any, threeCamera: any) {
  if (!gsCamera || !threeCamera) return;
  const gsPosition = safeReadGsplatPosition(gsCamera);
  const gsQuaternion = gsCamera.quaternion || gsCamera._quaternion;
  if (gsPosition) threeCamera.position.set(gsPosition.x, gsPosition.y, gsPosition.z);
  if (gsQuaternion && typeof gsQuaternion.x === 'number') {
    threeCamera.quaternion.set(gsQuaternion.x, gsQuaternion.y, gsQuaternion.z, gsQuaternion.w);
  }
  const maybeFov = gsCamera.fov ?? gsCamera._fov ?? gsCamera._data?._fov;
  const maybeNear = gsCamera.near ?? gsCamera._near ?? gsCamera._data?._near;
  const maybeFar = gsCamera.far ?? gsCamera._far ?? gsCamera._data?._far;
  if (typeof maybeFov === 'number') threeCamera.fov = maybeFov;
  if (typeof maybeNear === 'number') threeCamera.near = maybeNear;
  if (typeof maybeFar === 'number') threeCamera.far = maybeFar;
  threeCamera.updateProjectionMatrix();
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getPointComponents(point: any): { x: number; y: number; z: number; t: number | null } {
  if (Array.isArray(point)) {
    return {
      x: Number(point[0] || 0), y: Number(point[1] || 0), z: Number(point[2] || 0),
      t: point.length > 3 ? Number(point[3]) || 0 : null,
    };
  }
  if (point && typeof point === 'object') {
    const tValue = point.t ?? point.time ?? point.timestamp;
    return {
      x: Number(point.x ?? point.X ?? 0) || 0,
      y: Number(point.y ?? point.Y ?? point.height ?? 0) || 0,
      z: Number(point.z ?? point.Z ?? 0) || 0,
      t: tValue != null ? Number(tValue) || 0 : null,
    };
  }
  return { x: 0, y: 0, z: 0, t: null };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeTrajectoryPoints(points: any[]): NormalizedPoint[] {
  const raw = Array.isArray(points) ? points : [];
  return raw.map((point, index) => {
    const parsed = getPointComponents(point);
    return { x: parsed.x, y: parsed.y, z: parsed.z, t: parsed.t, index, raw: point };
  });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function trajectoryHasTimestamps(points: any[]) {
  const normalized = normalizeTrajectoryPoints(points);
  return normalized.length > 1 && normalized.every((p) => p.t != null);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getTrajectoryCenter(pointsA: any[], pointsB: any[]): [number, number, number] {
  const merged = [...(Array.isArray(pointsA) ? pointsA : []), ...(Array.isArray(pointsB) ? pointsB : [])];
  if (merged.length === 0) return [0, 0.22, 0];
  let sumX = 0, sumZ = 0;
  merged.forEach((p) => { const c = getPointComponents(p); sumX += c.x; sumZ += c.z; });
  return [sumX / merged.length, 0.22, sumZ / merged.length];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getFramedCameraPosition(center: [number, number, number], pointsA: any[], pointsB: any[]): [number, number, number] {
  const merged = [...(Array.isArray(pointsA) ? pointsA : []), ...(Array.isArray(pointsB) ? pointsB : [])];
  if (merged.length === 0) return [0, 3.2, 6.8];
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
  merged.forEach((p) => { const c = getPointComponents(p); minX = Math.min(minX, c.x); maxX = Math.max(maxX, c.x); minZ = Math.min(minZ, c.z); maxZ = Math.max(maxZ, c.z); });
  const spanX = Math.max(1.6, maxX - minX);
  const spanZ = Math.max(1.6, maxZ - minZ);
  const depth = Math.max(spanX, spanZ);
  return [center[0], 3.2 + depth * 0.55, center[2] + 5.4 + depth * 0.9];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getAccidentPoint(pointsA: any[], pointsB: any[]): [number, number, number] {
  const a = Array.isArray(pointsA) ? pointsA : [];
  const b = Array.isArray(pointsB) ? pointsB : [];
  if (a.length === 0 && b.length === 0) return [...defaultAccidentPoint] as [number, number, number];
  if (a.length === 0) { const lb = getPointComponents(b[b.length - 1]); return [lb.x, lb.y + 0.01, lb.z]; }
  if (b.length === 0) { const la = getPointComponents(a[a.length - 1]); return [la.x, la.y + 0.01, la.z]; }
  let bestA = getPointComponents(a[0]), bestB = getPointComponents(b[0]), bestDist = Infinity;
  a.forEach((pa_) => {
    const pa = getPointComponents(pa_);
    b.forEach((pb_) => {
      const pb = getPointComponents(pb_);
      const d = (pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2 + (pa.z - pb.z) ** 2;
      if (d < bestDist) { bestDist = d; bestA = pa; bestB = pb; }
    });
  });
  return [(bestA.x + bestB.x) / 2, (bestA.y + bestB.y) / 2 + 0.01, (bestA.z + bestB.z) / 2];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function findClosestPointPair(pointsA: any[], pointsB: any[]) {
  const a = normalizeTrajectoryPoints(pointsA);
  const b = normalizeTrajectoryPoints(pointsB);
  if (a.length === 0 || b.length === 0) return null;
  let best = { indexA: 0, indexB: 0, distanceSq: Infinity };
  a.forEach((pa, indexA) => {
    b.forEach((pb, indexB) => {
      const d = (pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2 + (pa.z - pb.z) ** 2;
      if (d < best.distanceSq) best = { indexA, indexB, distanceSq: d };
    });
  });
  return best;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function computePointSpeedKmh(points: any[], index: number): number | null {
  const normalized = normalizeTrajectoryPoints(points);
  if (normalized.length < 2 || !normalized.every((p) => p.t != null)) return null;
  const cur = Math.max(0, Math.min(normalized.length - 1, index));
  const start = cur === 0 ? normalized[0] : normalized[cur - 1];
  const end = cur === normalized.length - 1 ? normalized[normalized.length - 1] : normalized[Math.min(cur + 1, normalized.length - 1)];
  const dt = Math.max(1e-6, (end.t as number) - (start.t as number));
  const ms = Math.sqrt((end.x - start.x) ** 2 + (end.y - start.y) ** 2 + (end.z - start.z) ** 2) / dt;
  return ms * 3.6;
}

function formatSpeedKmh(speed: number | null | undefined) {
  if (speed == null || !Number.isFinite(speed)) return '시간 정보 없음';
  return `${speed.toFixed(1)} km/h`;
}

function computeOrbitStateFromFrame(target: [number, number, number], framedPos: [number, number, number]): OrbitState {
  const dx = framedPos[0] - target[0], dy = framedPos[1] - target[1], dz = framedPos[2] - target[2];
  const distance = Math.min(CAMERA_MAX_DISTANCE, Math.max(CAMERA_MIN_DISTANCE, Math.sqrt(dx * dx + dy * dy + dz * dz)));
  return {
    theta: Math.atan2(dz, dx),
    phi: Math.min(CAMERA_MAX_PHI, Math.max(CAMERA_MIN_PHI, Math.acos(dy / distance))),
    distance,
    target: [target[0], target[1], target[2]],
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function applyOrbitStateToCamera(state: OrbitState, camera: any, controls: any) {
  const { theta, phi, distance, target } = state;
  safeSetGsplatCameraPosition(camera, target[0] + distance * Math.sin(phi) * Math.cos(theta), target[1] + distance * Math.cos(phi), target[2] + distance * Math.sin(phi) * Math.sin(theta));
  safeSetGsplatTarget(controls, target[0], target[1], target[2]);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function panCameraByScreenDelta(THREE: any, orbitState: OrbitState, camera: any, controls: any, deltaX: number, deltaY: number) {
  const position = safeReadGsplatPosition(camera);
  if (!position) return;
  const pos = new THREE.Vector3(position.x, position.y, position.z);
  const tgt = new THREE.Vector3(...orbitState.target);
  const forward = new THREE.Vector3().subVectors(tgt, pos).normalize();
  const worldUp = new THREE.Vector3(0, 1, 0);
  const right = new THREE.Vector3().crossVectors(forward, worldUp).normalize();
  const up = new THREE.Vector3().crossVectors(right, forward).normalize();
  const scale = orbitState.distance * CAMERA_PAN_MULTIPLIER;
  const movement = new THREE.Vector3().addScaledVector(right, -deltaX * scale).addScaledVector(up, deltaY * scale);
  orbitState.target = [orbitState.target[0] + movement.x, orbitState.target[1] + movement.y, orbitState.target[2] + movement.z];
  applyOrbitStateToCamera(orbitState, camera, controls);
}

function dollyCameraTowardTarget(orbitState: OrbitState, camera: unknown, controls: unknown, deltaY: number) {
  orbitState.distance = Math.min(CAMERA_MAX_DISTANCE, Math.max(CAMERA_MIN_DISTANCE, orbitState.distance * (deltaY > 0 ? CAMERA_DOLLY_OUT : CAMERA_DOLLY_IN)));
  applyOrbitStateToCamera(orbitState, camera, controls);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getTrajectoryDuration(points: any[]) {
  const normalized = normalizeTrajectoryPoints(points);
  if (normalized.length <= 1) return normalized.length;
  if (normalized.every((p) => p.t != null)) {
    const duration = (normalized[normalized.length - 1].t as number) - (normalized[0].t as number);
    return duration > 0 ? duration : normalized.length - 1;
  }
  return normalized.length - 1;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function samplePath(points: any[], progressOrTime: number): SampleResult {
  const normalized = normalizeTrajectoryPoints(points);
  if (normalized.length === 0) return { position: [0, 0, 0], next: [0, 0, -1] };
  if (normalized.length === 1) {
    const p = normalized[0];
    return { position: [p.x, p.y, p.z], next: [p.x, p.y, p.z - 1] };
  }
  const hasTs = normalized.every((p) => p.t != null);
  if (hasTs) {
    const startTime = normalized[0].t as number;
    const endTime = normalized[normalized.length - 1].t as number;
    const targetTime = Math.max(startTime, Math.min(endTime, startTime + progressOrTime));
    let idx = 0;
    while (idx < normalized.length - 2 && (normalized[idx + 1].t as number) < targetTime) idx++;
    const cur = normalized[idx], nxt = normalized[Math.min(idx + 1, normalized.length - 1)];
    const dt = Math.max(1e-6, (nxt.t as number) - (cur.t as number));
    const localT = Math.max(0, Math.min(1, (targetTime - (cur.t as number)) / dt));
    return { position: [cur.x + (nxt.x - cur.x) * localT, cur.y + (nxt.y - cur.y) * localT, cur.z + (nxt.z - cur.z) * localT], next: [nxt.x, nxt.y, nxt.z] };
  }
  const clamped = Math.max(0, Math.min(0.999999, progressOrTime));
  const scaled = clamped * (normalized.length - 1);
  const idx = Math.floor(scaled);
  const localT = scaled - idx;
  const cur = normalized[idx], nxt = normalized[Math.min(idx + 1, normalized.length - 1)];
  return { position: [cur.x + (nxt.x - cur.x) * localT, cur.y + (nxt.y - cur.y) * localT, cur.z + (nxt.z - cur.z) * localT], next: [nxt.x, nxt.y, nxt.z] };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function disposeThreeObject(root: any) {
  if (!root?.traverse) return;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  root.traverse((obj: any) => {
    obj.geometry?.dispose?.();
    if (Array.isArray(obj.material)) obj.material.forEach((m: any) => m?.dispose?.());
    else obj.material?.dispose?.();
  });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function createFallbackCar(THREE: any, color: number) {
  const group = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.45, 0.9), new THREE.MeshStandardMaterial({ color }));
  body.position.y = 0.3;
  group.add(body);
  const cabin = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.35, 0.8), new THREE.MeshStandardMaterial({ color }));
  cabin.position.set(0, 0.6, 0);
  group.add(cabin);
  [[-0.55, 0.1, 0.48], [0.55, 0.1, 0.48], [-0.55, 0.1, -0.48], [0.55, 0.1, -0.48]].forEach(([x, y, z]) => {
    const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.18, 20), new THREE.MeshStandardMaterial({ color: 0x111827 }));
    wheel.rotation.z = Math.PI / 2;
    wheel.position.set(x, y, z);
    group.add(wheel);
  });
  return group;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeVehicleModel(THREE: any, model: any) {
  const wrapper = new THREE.Group();
  wrapper.add(model);
  const box = new THREE.Box3().setFromObject(model);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);
  const maxDim = Math.max(size.x || 0, size.y || 0, size.z || 0);
  const scale = maxDim > 0 ? 1.9 / maxDim : 1;
  model.position.sub(center);
  model.scale.multiplyScalar(scale);
  const scaledBox = new THREE.Box3().setFromObject(model);
  const minY = scaledBox.min.y;
  if (Number.isFinite(minY)) model.position.y -= minY;
  return wrapper;
}

async function safeFetchJson(url: string) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`fetch "${url}" → ${res.status}`);
  return res.json();
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function loadTrajectoryJson(url: string | undefined, fallbackData: any[]) {
  if (!url) return { points: fallbackData, source: 'sample-no-url' };
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const data: any = await safeFetchJson(url);
    if (Array.isArray(data)) return { points: data, source: 'remote-json' };
    if (Array.isArray(data?.points)) return { points: data.points, source: 'remote-json.points' };
    if (Array.isArray(data?.trajectory)) return { points: data.trajectory, source: 'remote-json.trajectory' };
    if (Array.isArray(data?.positions)) return { points: data.positions, source: 'remote-json.positions' };
    return { points: fallbackData, source: 'sample-invalid-shape' };
  } catch {
    return { points: fallbackData, source: 'sample-fetch-error' };
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function loadSplatScene({ SPLAT, url, scene }: { SPLAT: any; url: string | undefined; scene: any }) {
  if (!url) return { ok: false };
  try {
    await SPLAT.Loader.LoadAsync(url, scene, () => {});
    return { ok: true };
  } catch {
    return { ok: false };
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function loadVehicleModel({ THREE, GLTFLoader, url, fallbackColor }: { THREE: any; GLTFLoader: any; url: string | undefined; fallbackColor: number }) {
  if (!url) return { model: createFallbackCar(THREE, fallbackColor), source: 'fallback-no-url' };
  try {
    const loader = new GLTFLoader();
    const res = await fetch(url);
    if (!res.ok) throw new Error('model fetch failed');
    const arrayBuffer = await res.arrayBuffer();
    const basePath = url.startsWith('blob:') ? '' : url.slice(0, url.lastIndexOf('/') + 1);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const gltf = await new Promise<any>((resolve, reject) => loader.parse(arrayBuffer, basePath, resolve, reject));
    const rawModel = gltf?.scene?.clone ? gltf.scene.clone(true) : null;
    if (!rawModel) return { model: createFallbackCar(THREE, fallbackColor), source: 'fallback-empty-scene' };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rawModel.traverse((obj: any) => { if (obj.isMesh) { obj.castShadow = true; obj.receiveShadow = true; } });
    return { model: normalizeVehicleModel(THREE, rawModel), source: 'remote-model' };
  } catch {
    return { model: createFallbackCar(THREE, fallbackColor), source: 'fallback-load-error' };
  }
}

// ─── HTML 폴백 (Three.js 로드 전 표시) ───────────────────────────────────────

function HtmlFallbackPreview({ showVehicleA, showVehicleB, showAccidentPoint, showTrajectoryLines }: {
  showVehicleA: boolean; showVehicleB: boolean; showAccidentPoint: boolean; showTrajectoryLines: boolean;
}) {
  return (
    <div className="absolute inset-0 z-30 overflow-hidden rounded-2xl bg-[radial-gradient(circle_at_top,_#1e293b,_#020617)]">
      <div className="absolute inset-0 opacity-35" style={{ backgroundImage: 'linear-gradient(rgba(148,163,184,0.24) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.24) 1px, transparent 1px)', backgroundSize: '32px 32px' }} />
      {showTrajectoryLines && (
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1000 760" preserveAspectRatio="none">
          <polyline points="250,430 340,420 430,405 520,385 615,365 710,345" fill="none" stroke="#60a5fa" strokeWidth="5" />
          <polyline points="720,280 650,320 590,355 545,390 515,425 500,470" fill="none" stroke="#f87171" strokeWidth="5" />
        </svg>
      )}
      {showVehicleA && <div className="absolute left-[46%] top-[50%] h-10 w-20 -translate-x-1/2 -translate-y-1/2 rounded-xl bg-blue-500/85 shadow-xl" />}
      {showVehicleB && <div className="absolute left-[58%] top-[56%] h-10 w-20 -translate-x-1/2 -translate-y-1/2 rounded-xl bg-red-500/85 shadow-xl" />}
      {showAccidentPoint && <div className="absolute left-[51.5%] top-[61%] h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-amber-400" />}
    </div>
  );
}

// ─── ViewerPane (Three.js + gsplat 렌더러) ────────────────────────────────────

interface ViewerPaneProps {
  splatUrl?: string;
  trajectoryUrlA?: string;
  trajectoryUrlB?: string;
  showVehicleA: boolean;
  showVehicleB: boolean;
  showAccidentPoint: boolean;
  showTrajectoryLines: boolean;
  autoPlay: boolean;
  playbackSpeed: number;
  playbackLoop: boolean;
  onStatusChange: (s: { phase: string; message: string }) => void;
  onLoadedMeta: (m: Record<string, unknown>) => void;
}

interface ViewerPaneRef {
  focusScene: () => void;
}

const ViewerPane = forwardRef<ViewerPaneRef, ViewerPaneProps>(function ViewerPane(props, ref) {
  const {
    splatUrl, trajectoryUrlA, trajectoryUrlB,
    showVehicleA, showVehicleB, showAccidentPoint, showTrajectoryLines,
    autoPlay, playbackSpeed, playbackLoop, onStatusChange, onLoadedMeta,
  } = props;

  const wrapRef = useRef<HTMLDivElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const engineRef = useRef<any>(null);
  const orbitStateRef = useRef<OrbitState | null>(null);
  const uiStateRef = useRef({ showVehicleA, showVehicleB, showAccidentPoint, showTrajectoryLines, autoPlay, playbackSpeed, playbackLoop });

  // 샘플 궤적과 데모 차량 모델이 항상 있으므로 항상 3D 엔진 실행
  const noAssetsProvided = false;

  useEffect(() => {
    uiStateRef.current = { showVehicleA, showVehicleB, showAccidentPoint, showTrajectoryLines, autoPlay, playbackSpeed, playbackLoop };
  }, [showVehicleA, showVehicleB, showAccidentPoint, showTrajectoryLines, autoPlay, playbackSpeed, playbackLoop]);

  useEffect(() => {
    if (noAssetsProvided) {
      onLoadedMeta({});
      onStatusChange({ phase: 'idle', message: '' });
      return;
    }

    let disposed = false;
    let rafId = 0;
    let resizeHandler: (() => void) | null = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let localRendererCanvas: any = null;

    async function init() {
      if (!wrapRef.current || !overlayCanvasRef.current) return;
      onStatusChange({ phase: 'loading', message: '뷰어 로딩 중' });

      try {
        const [SPLAT, THREE, gltfModule] = await Promise.all([
          import('gsplat'),
          import('three'),
          import('three/examples/jsm/loaders/GLTFLoader.js'),
        ]);
        if (disposed) return;

        const { GLTFLoader } = gltfModule;
        const container = wrapRef.current!;
        const overlayCanvas = overlayCanvasRef.current!;

        const splatRenderer = new SPLAT.WebGLRenderer();
        localRendererCanvas = splatRenderer.canvas;
        localRendererCanvas.className = 'absolute inset-0 h-full w-full';
        localRendererCanvas.style.cssText = 'width:100%;height:100%;pointer-events:auto;background:radial-gradient(circle at top,#111827,#020617);touch-action:none;';
        container.prepend(localRendererCanvas);

        const splatScene = new SPLAT.Scene();
        const splatCamera = new SPLAT.Camera();
        const splatControls = new SPLAT.OrbitControls(splatCamera, splatRenderer.canvas);

        const overlayRenderer = new THREE.WebGLRenderer({ canvas: overlayCanvas, antialias: true, alpha: true });
        overlayRenderer.setPixelRatio(window.devicePixelRatio || 1);
        overlayRenderer.setClearColor(0x000000, 0);

        const overlayScene = new THREE.Scene();
        const overlayCamera = new THREE.PerspectiveCamera(55, 1, 0.01, 500);
        overlayScene.add(new THREE.AmbientLight(0xffffff, 1.3));
        const dir = new THREE.DirectionalLight(0xffffff, 1.2);
        dir.position.set(6, 10, 5);
        overlayScene.add(dir);
        const fill = new THREE.DirectionalLight(0xffffff, 0.5);
        fill.position.set(-6, 4, -3);
        overlayScene.add(fill);
        overlayScene.add(new THREE.GridHelper(30, 30, 0x64748b, 0x334155));
        const ground = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshStandardMaterial({ color: 0x0f172a, transparent: true, opacity: 0.35 }));
        ground.rotation.x = -Math.PI / 2;
        overlayScene.add(ground);

        const trajectoryGroup = new THREE.Group();
        const vehicleGroup = new THREE.Group();
        const markerGroup = new THREE.Group();
        overlayScene.add(trajectoryGroup, vehicleGroup, markerGroup);

        const accidentMarker = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.05, 24), new THREE.MeshStandardMaterial({ color: 0xf59e0b }));
        markerGroup.add(accidentMarker);

        const [trajResultA, trajResultB, vehicleResultA, vehicleResultB, splatResult] = await Promise.all([
          loadTrajectoryJson(trajectoryUrlA, sampleTrajectoryA),
          loadTrajectoryJson(trajectoryUrlB, sampleTrajectoryB),
          loadVehicleModel({ THREE, GLTFLoader, url: DEMO_VEHICLE_URL_A, fallbackColor: 0x2563eb }),
          loadVehicleModel({ THREE, GLTFLoader, url: DEMO_VEHICLE_URL_B, fallbackColor: 0xef4444 }),
          loadSplatScene({ SPLAT, url: splatUrl, scene: splatScene }),
        ]);
        if (disposed) return;

        const trajectoryA = trajResultA.points;
        const trajectoryB = trajResultB.points;
        const accidentPoint = getAccidentPoint(trajectoryA, trajectoryB);
        accidentMarker.position.set(accidentPoint[0], accidentPoint[1], accidentPoint[2]);

        const framedTarget = getTrajectoryCenter(trajectoryA, trajectoryB);
        const framedPosition = getFramedCameraPosition(framedTarget, trajectoryA, trajectoryB);

        const vehicleA = vehicleResultA.model;
        const vehicleB = vehicleResultB.model;
        vehicleA.rotation.y += Math.PI;
        vehicleB.rotation.y += Math.PI;
        vehicleGroup.add(vehicleA, vehicleB);

        const lineA = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(trajectoryA.map((p: unknown) => { const c = getPointComponents(p); return new THREE.Vector3(c.x, c.y, c.z); })),
          new THREE.LineBasicMaterial({ color: 0x60a5fa })
        );
        const lineB = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(trajectoryB.map((p: unknown) => { const c = getPointComponents(p); return new THREE.Vector3(c.x, c.y, c.z); })),
          new THREE.LineBasicMaterial({ color: 0xf87171 })
        );
        trajectoryGroup.add(lineA, lineB);

        orbitStateRef.current = computeOrbitStateFromFrame(framedTarget, framedPosition);
        applyOrbitStateToCamera(orbitStateRef.current, splatCamera, splatControls);
        overlayCamera.position.set(framedPosition[0], framedPosition[1], framedPosition[2]);
        overlayCamera.lookAt(framedTarget[0], framedTarget[1], framedTarget[2]);

        // 마우스/터치 컨트롤
        const cs = { mode: null as string | null, pointerId: null as number | null, lastX: 0, lastY: 0 };

        const onPointerDown = (e: PointerEvent) => {
          if (!orbitStateRef.current) return;
          cs.mode = e.button === 0 && !e.shiftKey ? 'rotate' : e.button === 2 || (e.button === 0 && e.shiftKey) ? 'pan' : null;
          if (!cs.mode) return;
          cs.pointerId = e.pointerId; cs.lastX = e.clientX; cs.lastY = e.clientY;
          try { localRendererCanvas.setPointerCapture(e.pointerId); } catch (_) {}
          e.preventDefault(); e.stopPropagation();
        };
        const onPointerMove = (e: PointerEvent) => {
          if (!orbitStateRef.current || !cs.mode) return;
          if (cs.pointerId !== null && e.pointerId !== cs.pointerId) return;
          const dx = e.clientX - cs.lastX, dy = e.clientY - cs.lastY;
          cs.lastX = e.clientX; cs.lastY = e.clientY;
          if (cs.mode === 'rotate') {
            orbitStateRef.current.theta -= dx * CAMERA_ROTATE_SPEED;
            orbitStateRef.current.phi = Math.min(CAMERA_MAX_PHI, Math.max(CAMERA_MIN_PHI, orbitStateRef.current.phi - dy * CAMERA_ROTATE_SPEED));
            applyOrbitStateToCamera(orbitStateRef.current, splatCamera, splatControls);
          } else {
            panCameraByScreenDelta(THREE, orbitStateRef.current, splatCamera, splatControls, dx, dy);
          }
          e.preventDefault();
        };
        const clearPtr = () => { cs.mode = null; cs.pointerId = null; };
        const onPointerUp = () => { try { localRendererCanvas.releasePointerCapture(cs.pointerId!); } catch (_) {} clearPtr(); };
        const onWheel = (e: WheelEvent) => { if (!orbitStateRef.current) return; e.preventDefault(); dollyCameraTowardTarget(orbitStateRef.current, splatCamera, splatControls, e.deltaY); };
        const onContextMenu = (e: Event) => e.preventDefault();
        const onKeyDown = (e: KeyboardEvent) => {
          if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) return;
          e.preventDefault(); // 페이지 스크롤 방지
          if (!orbitStateRef.current) return;
          const state = orbitStateRef.current;
          const pos = safeReadGsplatPosition(splatCamera);
          if (!pos) return;
          const forward = new THREE.Vector3(state.target[0] - pos.x, 0, state.target[2] - pos.z).normalize();
          const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize();
          const ms = state.distance * 0.05;
          const move = new THREE.Vector3();
          if (e.key === 'ArrowUp') move.addScaledVector(forward, ms);
          if (e.key === 'ArrowDown') move.addScaledVector(forward, -ms);
          if (e.key === 'ArrowLeft') move.addScaledVector(right, -ms);
          if (e.key === 'ArrowRight') move.addScaledVector(right, ms);
          state.target = [state.target[0] + move.x, state.target[1], state.target[2] + move.z];
          applyOrbitStateToCamera(state, splatCamera, splatControls);
        };

        localRendererCanvas.addEventListener('pointerdown', onPointerDown);
        localRendererCanvas.addEventListener('pointermove', onPointerMove);
        localRendererCanvas.addEventListener('pointerup', onPointerUp);
        localRendererCanvas.addEventListener('pointercancel', clearPtr);
        localRendererCanvas.addEventListener('wheel', onWheel, { passive: false });
        localRendererCanvas.addEventListener('contextmenu', onContextMenu);
        window.addEventListener('keydown', onKeyDown);

        const resize = () => {
          const rect = container.getBoundingClientRect();
          const w = Math.max(1, Math.floor(rect.width)), h = Math.max(1, Math.floor(rect.height));
          splatRenderer.setSize(w, h);
          overlayRenderer.setSize(w, h, false);
          overlayCamera.aspect = w / h;
          overlayCamera.updateProjectionMatrix();
        };
        resize();
        resizeHandler = resize;
        window.addEventListener('resize', resizeHandler);

        const startTimeRef = { current: performance.now() };
        const pausePlayheadRef = { current: 0 };
        const lastAutoPlayRef = { current: uiStateRef.current.autoPlay };

        engineRef.current = {
          canvasHandlers: { onPointerDown, onPointerMove, onPointerUp, onPointerCancel: clearPtr, onWheel, onContextMenu },
          keyHandler: onKeyDown,
          focusScene: () => {
            orbitStateRef.current = computeOrbitStateFromFrame(framedTarget, framedPosition);
            applyOrbitStateToCamera(orbitStateRef.current, splatCamera, splatControls);
            overlayCamera.position.set(framedPosition[0], framedPosition[1], framedPosition[2]);
            overlayCamera.lookAt(framedTarget[0], framedTarget[1], framedTarget[2]);
          },
          splatRenderer, splatScene, splatCamera, splatControls,
          overlayRenderer, overlayScene, overlayCamera,
          trajectoryA, trajectoryB, vehicleA, vehicleB, lineA, lineB,
          accidentMarker, ground, startTimeRef, pausePlayheadRef, lastAutoPlayRef,
          hasSplat: splatResult.ok,
        };

        const closestPair = findClosestPointPair(trajectoryA, trajectoryB);
        onLoadedMeta({
          trajectoryHasTimeA: trajectoryHasTimestamps(trajectoryA),
          trajectoryHasTimeB: trajectoryHasTimestamps(trajectoryB),
          collisionSpeedA: closestPair ? computePointSpeedKmh(trajectoryA, closestPair.indexA) : null,
          collisionSpeedB: closestPair ? computePointSpeedKmh(trajectoryB, closestPair.indexB) : null,
          collisionDistanceM: closestPair ? Math.sqrt(closestPair.distanceSq) : null,
        });
        onStatusChange({ phase: 'ready', message: '뷰어 준비 완료' });

        const animate = (now: number) => {
          if (disposed || !engineRef.current) return;
          const engine = engineRef.current;
          const state = uiStateRef.current;

          if (engine.hasSplat) {
            copyGsplatCameraToThreeCamera(engine.splatCamera, engine.overlayCamera);
          } else if (orbitStateRef.current) {
            const s = orbitStateRef.current;
            engine.overlayCamera.position.set(
              s.target[0] + s.distance * Math.sin(s.phi) * Math.cos(s.theta),
              s.target[1] + s.distance * Math.cos(s.phi),
              s.target[2] + s.distance * Math.sin(s.phi) * Math.sin(s.theta)
            );
            engine.overlayCamera.lookAt(s.target[0], s.target[1], s.target[2]);
          }

          if (engine.lastAutoPlayRef.current !== state.autoPlay) {
            if (state.autoPlay) engine.startTimeRef.current = now - (engine.pausePlayheadRef.current / Math.max(0.0001, state.playbackSpeed)) * 1000;
            engine.lastAutoPlayRef.current = state.autoPlay;
          }

          const baseElapsed = state.autoPlay ? ((now - engine.startTimeRef.current) / 1000) * state.playbackSpeed : engine.pausePlayheadRef.current;
          const durationA = Math.max(1e-6, getTrajectoryDuration(engine.trajectoryA));
          const durationB = Math.max(1e-6, getTrajectoryDuration(engine.trajectoryB));
          const usesTimeA = trajectoryHasTimestamps(engine.trajectoryA);
          const usesTimeB = trajectoryHasTimestamps(engine.trajectoryB);
          const sampleInputA = usesTimeA ? (state.playbackLoop ? baseElapsed % durationA : Math.min(baseElapsed, durationA)) : (state.playbackLoop ? baseElapsed % 1 : Math.min(baseElapsed, 0.999999));
          const sampleInputB = usesTimeB ? (state.playbackLoop ? baseElapsed % durationB : Math.min(baseElapsed, durationB)) : (state.playbackLoop ? baseElapsed % 1 : Math.min(baseElapsed, 0.999999));
          engine.pausePlayheadRef.current = baseElapsed;

          const sA = samplePath(engine.trajectoryA, sampleInputA);
          const sB = samplePath(engine.trajectoryB, sampleInputB);

          engine.vehicleA.visible = state.showVehicleA;
          engine.vehicleB.visible = state.showVehicleB;
          engine.lineA.visible = state.showTrajectoryLines;
          engine.lineB.visible = state.showTrajectoryLines;
          engine.accidentMarker.visible = state.showAccidentPoint;

          engine.vehicleA.position.set(sA.position[0], sA.position[1], sA.position[2]);
          engine.vehicleB.position.set(sB.position[0], sB.position[1], sB.position[2]);
          engine.vehicleA.lookAt(sA.next[0], sA.position[1], sA.next[2]);
          engine.vehicleB.lookAt(sB.next[0], sB.position[1], sB.next[2]);

          if (engine.hasSplat) engine.splatRenderer.render(engine.splatScene, engine.splatCamera);
          engine.overlayRenderer.render(engine.overlayScene, engine.overlayCamera);
          rafId = requestAnimationFrame(animate);
        };
        rafId = requestAnimationFrame(animate);
      } catch (error) {
        onStatusChange({ phase: 'error', message: (error as Error)?.message || '뷰어 초기화 실패' });
      }
    }

    init();

    return () => {
      disposed = true;
      const engine = engineRef.current;
      if (rafId) cancelAnimationFrame(rafId);
      if (resizeHandler) window.removeEventListener('resize', resizeHandler);
      if (engine) {
        if (engine.keyHandler) window.removeEventListener('keydown', engine.keyHandler);
        try {
          const ch = engine.canvasHandlers;
          if (localRendererCanvas && ch) {
            localRendererCanvas.removeEventListener('pointerdown', ch.onPointerDown);
            localRendererCanvas.removeEventListener('pointermove', ch.onPointerMove);
            localRendererCanvas.removeEventListener('pointerup', ch.onPointerUp);
            localRendererCanvas.removeEventListener('pointercancel', ch.onPointerCancel);
            localRendererCanvas.removeEventListener('wheel', ch.onWheel);
            localRendererCanvas.removeEventListener('contextmenu', ch.onContextMenu);
          }
          engine.splatControls?.dispose?.();
          engine.overlayRenderer?.dispose?.();
          disposeThreeObject(engine.vehicleA);
          disposeThreeObject(engine.vehicleB);
          engine.lineA?.geometry?.dispose?.();
          engine.lineA?.material?.dispose?.();
          engine.lineB?.geometry?.dispose?.();
          engine.lineB?.material?.dispose?.();
          engine.accidentMarker?.geometry?.dispose?.();
          engine.accidentMarker?.material?.dispose?.();
          engine.ground?.geometry?.dispose?.();
          engine.ground?.material?.dispose?.();
        } catch (_) {}
      }
      engineRef.current = null;
      orbitStateRef.current = null;
      if (localRendererCanvas?.parentNode) localRendererCanvas.parentNode.removeChild(localRendererCanvas);
    };
  }, [splatUrl, trajectoryUrlA, trajectoryUrlB, noAssetsProvided, onStatusChange, onLoadedMeta]);

  useImperativeHandle(ref, () => ({
    focusScene: () => engineRef.current?.focusScene?.(),
  }));

  return (
    <div ref={wrapRef} className="relative h-[600px] overflow-hidden rounded-2xl border border-slate-200 bg-slate-950">
      {!noAssetsProvided && (
        <canvas ref={overlayCanvasRef} className="pointer-events-none absolute inset-0 z-10 h-full w-full" />
      )}
      {noAssetsProvided && (
        <HtmlFallbackPreview
          showVehicleA={showVehicleA} showVehicleB={showVehicleB}
          showAccidentPoint={showAccidentPoint} showTrajectoryLines={showTrajectoryLines}
        />
      )}
      <div className="pointer-events-none absolute bottom-4 right-4 z-20 rounded-xl bg-black/45 px-3 py-2 text-xs text-white backdrop-blur">
        좌클릭 드래그 회전 · 방향키 이동 · 휠 줌
      </div>
    </div>
  );
});

// ─── 메인 컴포넌트 ────────────────────────────────────────────────────────────

export function Viewer3D({ jobId, resultUrl, trajectoryUrl }: Viewer3DProps) {
  const [status, setStatus] = useState({ phase: 'idle', message: '' });
  const [showVehicleA, setShowVehicleA] = useState(true);
  const [showVehicleB, setShowVehicleB] = useState(true);
  const [showTrajectoryLines, setShowTrajectoryLines] = useState(true);
  const [showAccidentPoint, setShowAccidentPoint] = useState(true);
  const [autoPlay, setAutoPlay] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [loadedMeta, setLoadedMeta] = useState<Record<string, unknown>>({});

  const viewerPaneRef = useRef<ViewerPaneRef>(null);
  const handleLoadedMeta = useCallback((meta: Record<string, unknown>) => setLoadedMeta(meta || {}), []);

  return (
    <ViewerErrorBoundary>
      <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-gray-900">3D 사고 복원 뷰어</h2>
            <p className="text-sm text-gray-500 mt-1">Job ID: {jobId}</p>
          </div>
          {status.phase === 'loading' && (
            <div className="flex items-center gap-2 text-sm text-indigo-600">
              <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              {status.message}
            </div>
          )}
          {status.phase === 'error' && (
            <div className="text-sm text-red-600">{status.message}</div>
          )}
        </div>

        {/* 뷰어 + 컨트롤 패널 */}
        <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
          {/* 컨트롤 패널 */}
          <div className="space-y-4">
            {/* 표시 옵션 */}
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-700 mb-3">표시 옵션</p>
              <div className="space-y-2">
                {[
                  { label: '차량 A', value: showVehicleA, onChange: setShowVehicleA },
                  { label: '차량 B', value: showVehicleB, onChange: setShowVehicleB },
                  { label: '궤적 라인', value: showTrajectoryLines, onChange: setShowTrajectoryLines },
                  { label: '사고 지점', value: showAccidentPoint, onChange: setShowAccidentPoint },
                ].map(({ label, value, onChange }) => (
                  <label key={label} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm cursor-pointer">
                    <span className="text-slate-700">{label}</span>
                    <input type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-indigo-600" />
                  </label>
                ))}
              </div>
            </div>

            {/* 재생 옵션 */}
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-700 mb-3">재생 옵션</p>
              <div className="space-y-3">
                <button
                  onClick={() => setAutoPlay((v) => !v)}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  {autoPlay ? '⏸ 정지' : '▶ 재생'}
                </button>
                <button
                  onClick={() => viewerPaneRef.current?.focusScene?.()}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  화면 맞추기
                </button>
                <div>
                  <div className="flex justify-between text-xs text-slate-600 mb-1">
                    <span>재생 배속</span>
                    <span>{playbackSpeed.toFixed(2)}x</span>
                  </div>
                  <input
                    type="range" min="0.1" max="3" step="0.05"
                    value={playbackSpeed}
                    onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
                    className="w-full accent-indigo-600"
                  />
                </div>
              </div>
            </div>

            {/* 충돌 정보 */}
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-700 mb-3">충돌 순간 속도</p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">차량 A</span>
                  <span className="font-semibold text-blue-600">{formatSpeedKmh(loadedMeta.collisionSpeedA as number)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">차량 B</span>
                  <span className="font-semibold text-red-500">{formatSpeedKmh(loadedMeta.collisionSpeedB as number)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* 3D 뷰 */}
          <ViewerPane
            key={`${resultUrl ?? ''}-${trajectoryUrl ?? ''}`}
            ref={viewerPaneRef}
            splatUrl={resultUrl}
            trajectoryUrlA={trajectoryUrl}
            trajectoryUrlB={undefined}
            showVehicleA={showVehicleA}
            showVehicleB={showVehicleB}
            showTrajectoryLines={showTrajectoryLines}
            showAccidentPoint={showAccidentPoint}
            autoPlay={autoPlay}
            playbackSpeed={playbackSpeed}
            playbackLoop={true}
            onStatusChange={setStatus}
            onLoadedMeta={handleLoadedMeta}
          />
        </div>
      </div>
    </ViewerErrorBoundary>
  );
}
