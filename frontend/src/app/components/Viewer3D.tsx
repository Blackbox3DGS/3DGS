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
  [2.8, 0.05, 1.8, 0], [2.3, 0.05, 1.3, 1], [1.9, 0.05, 0.8, 2],
  [1.6, 0.05, 0.3, 3], [1.5, 0.05, -0.2, 4], [1.5, 0.05, -0.8, 5],
];
const sampleTrajectoryB = [
  [0.0, 0.05, 0.0, 0], [0.8, 0.05, -0.3, 1], [1.6, 0.05, -0.6, 2],
  [2.2, 0.05, -1.0, 3], [3.0, 0.05, -1.3, 4], [3.8, 0.05, -1.5, 5],
];

// 데모용 기본 차량 모델 (public 폴더)
const DEMO_VEHICLE_URL_CAR = '/car-a.glb';
const DEMO_VEHICLE_URL_EGO = '/car-b.glb';

const EGO_COLOR = 0x22c55e;
const DYNAMIC_COLORS = [0x2563eb, 0xef4444, 0xf59e0b, 0xa855f7, 0x06b6d4, 0xec4899, 0x84cc16, 0xf97316];
const VEHICLE_CLASSES = new Set(['car', 'truck', 'bus', 'motorcycle', 'bicycle']);
const MIN_TRACK_POINTS = 5;
const FRAME_FPS = 10;            // vehicles.json의 frame_idx → 재생 fps
const SPLAT_POINT_SIZE = 0.05;   // THREE.Points 점 크기(월드 단위, sizeAttenuation)
const VEHICLE_SCALE_FRAC = 0.055; // 차량 크기 = 씬 최대치수 × 이 비율 (lingbot 네이티브=비미터라 상대 크기)

// ─── 타입 ────────────────────────────────────────────────────────────────────

interface Viewer3DProps {
  jobId: string;
  resultUrl?: string;      // Gaussian Splat (.splat) URL → 점구름 배경
  trajectoryUrl?: string;  // (legacy) 단일 궤적 JSON URL
  vehiclesUrl?: string;    // vehicles.json (ego + 동적차량 N대)
}

interface VehicleSpec { id: string; cls: string; points: unknown[] }
interface SampleResult { position: [number, number, number]; next: [number, number, number] }

// ─── 에러 바운더리 ────────────────────────────────────────────────────────────

interface ErrorBoundaryState { hasError: boolean; message: string }
class ViewerErrorBoundary extends Component<{ children: React.ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: React.ReactNode }) { super(props); this.state = { hasError: false, message: '' }; }
  static getDerivedStateFromError(error: Error) { return { hasError: true, message: error?.message || '렌더링 오류' }; }
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

// ─── 유틸 ────────────────────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getPointComponents(point: any): { x: number; y: number; z: number; t: number | null } {
  if (Array.isArray(point)) {
    return { x: Number(point[0] || 0), y: Number(point[1] || 0), z: Number(point[2] || 0), t: point.length > 3 ? Number(point[3]) || 0 : null };
  }
  if (point && typeof point === 'object') {
    const tValue = point.t ?? point.time ?? point.timestamp;
    return { x: Number(point.x ?? 0) || 0, y: Number(point.y ?? point.height ?? 0) || 0, z: Number(point.z ?? 0) || 0, t: tValue != null ? Number(tValue) || 0 : null };
  }
  return { x: 0, y: 0, z: 0, t: null };
}

// 이동평균 스무딩 — lingbot 포즈/depth 지터로 인한 흔들림 완화. t(frame_idx) 유지.
function smoothPoints(points: unknown[], win = 7): number[][] {
  const c = (Array.isArray(points) ? points : []).map(getPointComponents);
  if (c.length < 3) return c.map((p, i) => [p.x, p.y, p.z, p.t ?? i]);
  const half = Math.floor(win / 2);
  return c.map((_, i) => {
    let sx = 0, sy = 0, sz = 0, n = 0;
    for (let j = Math.max(0, i - half); j <= Math.min(c.length - 1, i + half); j++) { sx += c[j].x; sy += c[j].y; sz += c[j].z; n++; }
    return [sx / n, sy / n, sz / n, c[i].t ?? i];
  });
}

// frame_idx(t) 기준 보간 샘플.
function samplePath(points: number[][], frame: number): SampleResult {
  const n = points.length;
  if (n === 0) return { position: [0, 0, 0], next: [0, 0, -1] };
  if (n === 1) { const p = points[0]; return { position: [p[0], p[1], p[2]], next: [p[0], p[1], p[2] - 1] }; }
  const t0 = points[0][3] ?? 0;
  const t1 = points[n - 1][3] ?? (n - 1);
  const target = Math.max(t0, Math.min(t1, t0 + frame));
  let i = 0;
  while (i < n - 2 && (points[i + 1][3] ?? i + 1) < target) i++;
  const cur = points[i], nxt = points[Math.min(i + 1, n - 1)];
  const ct = cur[3] ?? i, nt = nxt[3] ?? (i + 1);
  const dt = Math.max(1e-6, nt - ct);
  const lt = Math.max(0, Math.min(1, (target - ct) / dt));
  return {
    position: [cur[0] + (nxt[0] - cur[0]) * lt, cur[1] + (nxt[1] - cur[1]) * lt, cur[2] + (nxt[2] - cur[2]) * lt],
    next: [nxt[0], nxt[1], nxt[2]],
  };
}

function vehicleColor(spec: VehicleSpec, dynamicIndex: number): number {
  return spec.id === 'ego' ? EGO_COLOR : DYNAMIC_COLORS[dynamicIndex % DYNAMIC_COLORS.length];
}

async function safeFetchJson(url: string) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`fetch "${url}" → ${res.status}`);
  return res.json();
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toSpecs(list: any[]): VehicleSpec[] {
  return (Array.isArray(list) ? list : [])
    .map((v) => ({ id: String(v.id ?? ''), cls: String(v.class ?? v.cls ?? 'car'), points: v.points ?? [] }))
    .filter((v) => v.id === 'ego' || (VEHICLE_CLASSES.has(v.cls) && (v.points?.length || 0) >= MIN_TRACK_POINTS));
}

async function loadVehiclesJson(url: string | undefined): Promise<VehicleSpec[] | null> {
  if (!url) return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const data: any = await safeFetchJson(url);
    if (Array.isArray(data?.vehicles)) return toSpecs(data.vehicles);
    if (Array.isArray(data)) return [{ id: 'A', cls: 'car', points: data }];
    if (Array.isArray(data?.points)) return [{ id: 'A', cls: 'car', points: data.points }];
    return null;
  } catch { return null; }
}

// .splat(32 byte/점: xyz f32 + scale f32x3 + rgba u8 + quat u8x4) → THREE.Points
// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function loadSplatAsPoints(THREE: any, url: string | undefined) {
  if (!url) return null;
  try {
    const buf = await (await fetch(url)).arrayBuffer();
    const n = Math.floor(buf.byteLength / 32);
    const dv = new DataView(buf);
    const positions = new Float32Array(n * 3);
    const colors = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const b = i * 32;
      positions[i * 3] = dv.getFloat32(b, true);
      positions[i * 3 + 1] = dv.getFloat32(b + 4, true);
      positions[i * 3 + 2] = dv.getFloat32(b + 8, true);
      colors[i * 3] = dv.getUint8(b + 24) / 255;
      colors[i * 3 + 1] = dv.getUint8(b + 25) / 255;
      colors[i * 3 + 2] = dv.getUint8(b + 26) / 255;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const mat = new THREE.PointsMaterial({ size: SPLAT_POINT_SIZE, sizeAttenuation: true, vertexColors: true });
    // eslint-disable-next-line no-console
    console.log(`[Viewer3D] splat → ${n} points`);
    return new THREE.Points(geo, mat);
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error('[Viewer3D] splat parse failed', e);
    return null;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function createFallbackCar(THREE: any, color: number) {
  const group = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.45, 0.9), new THREE.MeshStandardMaterial({ color }));
  body.position.y = 0.3; group.add(body);
  const cabin = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.35, 0.8), new THREE.MeshStandardMaterial({ color }));
  cabin.position.set(0, 0.6, 0); group.add(cabin);
  return group;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeVehicleModel(THREE: any, model: any) {
  const wrapper = new THREE.Group();
  wrapper.add(model);
  const box = new THREE.Box3().setFromObject(model);
  const size = new THREE.Vector3(); const center = new THREE.Vector3();
  box.getSize(size); box.getCenter(center);
  const maxDim = Math.max(size.x || 0, size.y || 0, size.z || 0);
  const scale = maxDim > 0 ? 1.0 / maxDim : 1;   // 단위 크기로 정규화 (씬 비례 스케일은 호출부에서)
  model.position.sub(center);
  model.scale.multiplyScalar(scale);
  const scaledBox = new THREE.Box3().setFromObject(model);
  if (Number.isFinite(scaledBox.min.y)) model.position.y -= scaledBox.min.y;  // 바닥을 y=0에
  return wrapper;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function loadVehicleModel({ THREE, GLTFLoader, url, fallbackColor }: { THREE: any; GLTFLoader: any; url: string; fallbackColor: number }) {
  try {
    const loader = new GLTFLoader();
    const res = await fetch(url);
    if (!res.ok) throw new Error('model fetch failed');
    const arrayBuffer = await res.arrayBuffer();
    const basePath = url.slice(0, url.lastIndexOf('/') + 1);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const gltf = await new Promise<any>((resolve, reject) => loader.parse(arrayBuffer, basePath, resolve, reject));
    const raw = gltf?.scene?.clone ? gltf.scene.clone(true) : null;
    if (!raw) return { model: createFallbackCar(THREE, fallbackColor) };
    return { model: normalizeVehicleModel(THREE, raw) };
  } catch {
    return { model: createFallbackCar(THREE, fallbackColor) };
  }
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

// ─── ViewerPane (Three.js 단일 씬: 점구름 + 차량 + OrbitControls) ─────────────

interface ViewerPaneProps {
  splatUrl?: string;
  vehiclesUrl?: string;
  showVehicles: boolean;
  showEgo: boolean;
  showTrajectoryLines: boolean;
  autoPlay: boolean;
  playbackSpeed: number;
  playbackLoop: boolean;
  onStatusChange: (s: { phase: string; message: string }) => void;
  onLoadedMeta: (m: Record<string, unknown>) => void;
}
interface ViewerPaneRef { focusScene: () => void }

const ViewerPane = forwardRef<ViewerPaneRef, ViewerPaneProps>(function ViewerPane(props, ref) {
  const { splatUrl, vehiclesUrl, showVehicles, showEgo, showTrajectoryLines, autoPlay, playbackSpeed, playbackLoop, onStatusChange, onLoadedMeta } = props;

  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const engineRef = useRef<any>(null);
  const uiStateRef = useRef({ showVehicles, showEgo, showTrajectoryLines, autoPlay, playbackSpeed, playbackLoop });

  useEffect(() => {
    uiStateRef.current = { showVehicles, showEgo, showTrajectoryLines, autoPlay, playbackSpeed, playbackLoop };
  }, [showVehicles, showEgo, showTrajectoryLines, autoPlay, playbackSpeed, playbackLoop]);

  useEffect(() => {
    let disposed = false;
    let rafId = 0;
    let resizeHandler: (() => void) | null = null;

    async function init() {
      if (!wrapRef.current || !canvasRef.current) return;
      onStatusChange({ phase: 'loading', message: '뷰어 로딩 중' });
      try {
        const [THREE, gltfMod, ctrlMod] = await Promise.all([
          import('three'),
          import('three/examples/jsm/loaders/GLTFLoader.js'),
          import('three/examples/jsm/controls/OrbitControls.js'),
        ]);
        if (disposed) return;
        const { GLTFLoader } = gltfMod;
        const { OrbitControls } = ctrlMod;
        const container = wrapRef.current!;
        const canvas = canvasRef.current!;

        const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
        renderer.setPixelRatio(window.devicePixelRatio || 1);
        renderer.setClearColor(0x0a0f1a, 1);

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(55, 1, 0.01, 5000);
        const controls = new OrbitControls(camera, canvas);
        controls.enableDamping = true; controls.dampingFactor = 0.08;

        scene.add(new THREE.AmbientLight(0xffffff, 1.25));
        const dir = new THREE.DirectionalLight(0xffffff, 1.1); dir.position.set(5, 10, 6); scene.add(dir);

        const trajectoryGroup = new THREE.Group();
        const vehicleGroup = new THREE.Group();
        scene.add(trajectoryGroup, vehicleGroup);

        const [vehSpecsRaw, carBaseRes, egoBaseRes, splatPoints] = await Promise.all([
          loadVehiclesJson(vehiclesUrl),
          loadVehicleModel({ THREE, GLTFLoader, url: DEMO_VEHICLE_URL_CAR, fallbackColor: 0x2563eb }),
          loadVehicleModel({ THREE, GLTFLoader, url: DEMO_VEHICLE_URL_EGO, fallbackColor: EGO_COLOR }),
          loadSplatAsPoints(THREE, splatUrl),
        ]);
        if (disposed) return;
        if (splatPoints) scene.add(splatPoints);

        const specs: VehicleSpec[] = vehSpecsRaw && vehSpecsRaw.length ? vehSpecsRaw
          : [{ id: 'A', cls: 'car', points: sampleTrajectoryA }, { id: 'B', cls: 'car', points: sampleTrajectoryB }];

        const carBase = carBaseRes.model;
        const egoBase = egoBaseRes.model;
        let dynIdx = 0;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const vehicles: any[] = specs.map((spec) => {
          const isEgo = spec.id === 'ego';
          const color = vehicleColor(spec, isEgo ? 0 : dynIdx++);
          const model = (isEgo ? egoBase : carBase).clone(true);
          model.visible = isEgo ? uiStateRef.current.showEgo : uiStateRef.current.showVehicles;
          vehicleGroup.add(model);
          const pts = smoothPoints(spec.points);
          const line = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(pts.map((p) => new THREE.Vector3(p[0], p[1], p[2]))),
            new THREE.LineBasicMaterial({ color })
          );
          trajectoryGroup.add(line);
          const first = pts.length ? (pts[0][3] ?? 0) : 0;
          const last = pts.length ? (pts[pts.length - 1][3] ?? first) : 0;
          return { id: spec.id, isEgo, points: pts, model, line, first, last };
        });

        // 카메라 프레이밍: 점구름 bbox + 차량 포인트.
        const box = new THREE.Box3();
        if (splatPoints) { splatPoints.geometry.computeBoundingBox(); if (splatPoints.geometry.boundingBox) box.union(splatPoints.geometry.boundingBox); }
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        vehicles.forEach((v: any) => v.points.forEach((p: number[]) => box.expandByPoint(new THREE.Vector3(p[0], p[1], p[2]))));
        if (box.isEmpty()) box.set(new THREE.Vector3(-5, -1, -5), new THREE.Vector3(5, 3, 5));
        const center = new THREE.Vector3(); box.getCenter(center);
        const size = new THREE.Vector3(); box.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z, 1);

        // 차량 크기를 씬에 비례하게 (네이티브=비미터) + 도로 평면 y 추정.
        const carScale = maxDim * VEHICLE_SCALE_FRAC;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        vehicles.forEach((v: any) => v.model.scale.setScalar(carScale));
        const dynY: number[] = [];
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        vehicles.forEach((v: any) => { if (!v.isEgo) v.points.forEach((p: number[]) => dynY.push(p[1])); });
        dynY.sort((a, b) => a - b);
        const groundY = dynY.length ? dynY[Math.floor(dynY.length / 2)] : center.y;

        // 격자를 씬 크기에 맞춰 도로 평면에 배치 (고정 80×80은 씬 대비 너무 큼).
        const grid = new THREE.GridHelper(maxDim * 1.5, 30, 0x334155, 0x1f2937);
        grid.position.set(center.x, groundY, center.z);
        scene.add(grid);

        const focusScene = () => {
          controls.target.copy(center);
          camera.position.set(center.x, center.y + maxDim * 0.45, center.z + maxDim * 1.1);
          camera.near = Math.max(0.01, maxDim / 1000); camera.far = maxDim * 40;
          camera.updateProjectionMatrix(); controls.update();
        };
        focusScene();

        const resize = () => {
          const r = container.getBoundingClientRect();
          const w = Math.max(1, Math.floor(r.width)), h = Math.max(1, Math.floor(r.height));
          renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
        };
        resize(); resizeHandler = resize; window.addEventListener('resize', resize);

        const startTimeRef = { current: performance.now() };
        const pausePlayheadRef = { current: 0 };
        const lastAutoPlayRef = { current: uiStateRef.current.autoPlay };
        engineRef.current = { renderer, scene, camera, controls, vehicles, grid, groundY, focusScene, startTimeRef, pausePlayheadRef, lastAutoPlayRef };

        onLoadedMeta({
          vehicleCount: vehicles.filter((v: { isEgo: boolean }) => !v.isEgo).length,
          hasEgo: vehicles.some((v: { isEgo: boolean }) => v.isEgo),
          hasSplat: !!splatPoints,
        });
        onStatusChange({ phase: 'ready', message: '뷰어 준비 완료' });

        const animate = (now: number) => {
          if (disposed || !engineRef.current) return;
          const e = engineRef.current; const st = uiStateRef.current;
          if (e.lastAutoPlayRef.current !== st.autoPlay) {
            if (st.autoPlay) e.startTimeRef.current = now - (e.pausePlayheadRef.current / Math.max(0.0001, st.playbackSpeed)) * 1000;
            e.lastAutoPlayRef.current = st.autoPlay;
          }
          const baseElapsed = st.autoPlay ? ((now - e.startTimeRef.current) / 1000) * st.playbackSpeed : e.pausePlayheadRef.current;
          e.pausePlayheadRef.current = baseElapsed;

          let dur = 1;
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          e.vehicles.forEach((v: any) => { if (v.points.length) { const last = v.points[v.points.length - 1][3]; if (last != null) dur = Math.max(dur, last); } });
          const frames = baseElapsed * FRAME_FPS;
          const sampleInput = st.playbackLoop ? frames % dur : Math.min(frames, dur);

          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          e.vehicles.forEach((v: any) => {
            const s = samplePath(v.points, sampleInput - v.first);
            // 트랙 활성 구간에서만 표시 (시작 전/종료 후엔 숨김 → 정지상태로 남지 않음).
            const active = sampleInput >= v.first - 0.5 && sampleInput <= v.last + 0.5;
            v.model.visible = active && (v.isEgo ? st.showEgo : st.showVehicles);
            v.line.visible = st.showTrajectoryLines;
            // 모든 차량을 도로 평면(groundY)에 올림 — ego(카메라 높이) 부유 + y 지터 제거.
            v.model.position.set(s.position[0], e.groundY, s.position[2]);
            const dx = s.next[0] - s.position[0], dz = s.next[2] - s.position[2];
            if (dx * dx + dz * dz > 1e-6) {
              v.model.lookAt(s.next[0], e.groundY, s.next[2]);
              if (v.isEgo) v.model.rotateY(Math.PI);  // ego GLB 전방축 보정
            }
          });

          e.controls.update();
          e.renderer.render(e.scene, e.camera);
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
      if (rafId) cancelAnimationFrame(rafId);
      if (resizeHandler) window.removeEventListener('resize', resizeHandler);
      const e = engineRef.current;
      if (e) {
        try {
          e.controls?.dispose?.();
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (e.vehicles || []).forEach((v: any) => { disposeThreeObject(v.model); v.line?.geometry?.dispose?.(); v.line?.material?.dispose?.(); });
          e.scene?.traverse?.((o: any) => { if (o.isPoints) { o.geometry?.dispose?.(); o.material?.dispose?.(); } });
          e.renderer?.dispose?.();
        } catch (_) {}
      }
      engineRef.current = null;
    };
  }, [splatUrl, vehiclesUrl, onStatusChange, onLoadedMeta]);

  useImperativeHandle(ref, () => ({ focusScene: () => engineRef.current?.focusScene?.() }));

  return (
    <div ref={wrapRef} className="relative h-[600px] overflow-hidden rounded-2xl border border-[#dae3dd] bg-[#0a1e14]">
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" style={{ touchAction: 'none' }} />
      <div className="pointer-events-none absolute bottom-4 right-4 z-20 rounded-xl bg-black/45 px-3 py-2 text-xs text-white backdrop-blur">
        좌클릭 드래그 회전 · 우클릭 이동 · 휠 줌
      </div>
    </div>
  );
});

// ─── 메인 컴포넌트 ────────────────────────────────────────────────────────────

export function Viewer3D({ jobId, resultUrl, trajectoryUrl, vehiclesUrl }: Viewer3DProps) {
  const [status, setStatus] = useState({ phase: 'idle', message: '' });
  const [showVehicles, setShowVehicles] = useState(true);
  const [showEgo, setShowEgo] = useState(true);
  const [showTrajectoryLines, setShowTrajectoryLines] = useState(true);
  const [autoPlay, setAutoPlay] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [loadedMeta, setLoadedMeta] = useState<Record<string, unknown>>({});

  const resolvedVehiclesUrl = vehiclesUrl ?? trajectoryUrl;
  const viewerPaneRef = useRef<ViewerPaneRef>(null);
  const handleLoadedMeta = useCallback((meta: Record<string, unknown>) => setLoadedMeta(meta || {}), []);

  return (
    <ViewerErrorBoundary>
      <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-[#20543d]">3D 사고 복원 뷰어</h2>
            <p className="text-sm text-[#8a9590] mt-1">Job ID: {jobId}</p>
          </div>
          {status.phase === 'loading' && (
            <div className="flex items-center gap-2 text-sm text-[#299283]">
              <div className="w-4 h-4 border-2 border-[#299283] border-t-transparent rounded-full animate-spin" />
              {status.message}
            </div>
          )}
          {status.phase === 'error' && <div className="text-sm text-red-600">{status.message}</div>}
        </div>

        <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
          <div className="space-y-4">
            <div className="rounded-xl border border-[#dae3dd] p-4">
              <p className="text-sm font-semibold text-[#5a665e] mb-3">표시 옵션</p>
              <div className="space-y-2">
                {[
                  { label: '자기차량(블랙박스)', value: showEgo, onChange: setShowEgo },
                  { label: '동적차량', value: showVehicles, onChange: setShowVehicles },
                  { label: '궤적 라인', value: showTrajectoryLines, onChange: setShowTrajectoryLines },
                ].map(({ label, value, onChange }) => (
                  <label key={label} className="flex items-center justify-between rounded-lg bg-[#f7f9f8] px-3 py-2 text-sm cursor-pointer">
                    <span className="text-[#5a665e]">{label}</span>
                    <input type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-indigo-600" />
                  </label>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-[#dae3dd] p-4">
              <p className="text-sm font-semibold text-[#5a665e] mb-3">재생 옵션</p>
              <div className="space-y-3">
                <button onClick={() => setAutoPlay((v) => !v)} className="w-full rounded-lg border border-[#dae3dd] bg-white px-3 py-2 text-sm font-medium text-[#5a665e] hover:bg-[#f7f9f8]">
                  {autoPlay ? '⏸ 정지' : '▶ 재생'}
                </button>
                <button onClick={() => viewerPaneRef.current?.focusScene?.()} className="w-full rounded-lg border border-[#dae3dd] bg-white px-3 py-2 text-sm font-medium text-[#5a665e] hover:bg-[#f7f9f8]">
                  화면 맞추기
                </button>
                <div>
                  <div className="flex justify-between text-xs text-[#5a665e] mb-1"><span>재생 배속</span><span>{playbackSpeed.toFixed(2)}x</span></div>
                  <input type="range" min="0.1" max="3" step="0.05" value={playbackSpeed} onChange={(e) => setPlaybackSpeed(Number(e.target.value))} className="w-full accent-indigo-600" />
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-[#dae3dd] p-4">
              <p className="text-sm font-semibold text-[#5a665e] mb-3">장면 정보</p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-[#8a9590]">배경 점구름</span><span className="font-semibold text-[#5a665e]">{loadedMeta.hasSplat ? '있음' : '없음'}</span></div>
                <div className="flex justify-between"><span className="text-[#8a9590]">자기차량</span><span className="font-semibold text-[#299283]">{loadedMeta.hasEgo ? '있음' : '없음'}</span></div>
                <div className="flex justify-between"><span className="text-[#8a9590]">동적차량 수</span><span className="font-semibold text-[#5a665e]">{(loadedMeta.vehicleCount as number) ?? 0}대</span></div>
              </div>
            </div>
          </div>

          <ViewerPane
            key={`${resultUrl ?? ''}-${resolvedVehiclesUrl ?? ''}`}
            ref={viewerPaneRef}
            splatUrl={resultUrl}
            vehiclesUrl={resolvedVehiclesUrl}
            showVehicles={showVehicles}
            showEgo={showEgo}
            showTrajectoryLines={showTrajectoryLines}
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
