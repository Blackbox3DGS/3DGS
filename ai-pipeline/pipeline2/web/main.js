// 3DGS 주차장 뷰어: splat 렌더 + 카메라 경로 차량 애니메이션
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import * as GaussianSplats3D from "@mkkellogg/gaussian-splats-3d";

const statusEl = document.getElementById("status");
const frameInfoEl = document.getElementById("frameInfo");
const setStatus = (m) => { statusEl.textContent = m; };

// --- 설정 로드 ---
const CFG = await fetch("./config.json").then(r => r.json()).catch(() => ({}));
const SPLAT_URL = CFG.splat_url || "./output.splat";
const POSES_URL = CFG.poses_url || "./camera_poses.json";
const CAMERA_FPS = CFG.camera_fps || 30;
const VEHICLE = CFG.vehicle_model || "cone";
const BG = CFG.background || "#0b0e14";
// 데이터가 이미 Y-up(지면정렬)이면 회전 불필요. 필요 시 config 로 보정.
const SPLAT_ROT = CFG.splat_rotation || [0, 0, 0]; // XYZ Euler (rad)

// --- Three.js 기본 구성 ---
const canvas = document.getElementById("canvas");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));

const scene = new THREE.Scene();
scene.background = new THREE.Color(BG);

const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.05, 2000);
camera.position.set(4, 4, 8);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;

scene.add(new THREE.AmbientLight(0xffffff, 0.9));
const dir = new THREE.DirectionalLight(0xffffff, 0.6);
dir.position.set(5, 10, 7);
scene.add(dir);

// 지면 격자 (Y=0)
const grid = new THREE.GridHelper(60, 60, 0x335577, 0x1a2230);
scene.add(grid);

// --- 카메라 경로 + 차량 ---
let pathPositions = [];   // THREE.Vector3[]
let vehicle = null;
let pathLine = null;

function buildVehicle() {
  let geo;
  if (VEHICLE === "box") geo = new THREE.BoxGeometry(0.5, 0.3, 1.0);
  else geo = new THREE.ConeGeometry(0.3, 1.0, 16).rotateX(-Math.PI / 2); // 팁이 -Z
  const mat = new THREE.MeshStandardMaterial({ color: 0xff5a3c, emissive: 0x551a10, metalness: 0.2, roughness: 0.5 });
  const mesh = new THREE.Mesh(geo, mat);
  if (VEHICLE === "none") mesh.visible = false;
  return mesh;
}

async function loadPath() {
  const data = await fetch(POSES_URL).then(r => r.json());
  const frames = data.frames || [];
  const rot = new THREE.Euler(SPLAT_ROT[0], SPLAT_ROT[1], SPLAT_ROT[2], "XYZ");
  const rotM = new THREE.Matrix4().makeRotationFromEuler(rot);
  pathPositions = frames.map(f => {
    const m = f.transform_matrix; // 4x4 c2w (row-major)
    const v = new THREE.Vector3(m[0][3], m[1][3], m[2][3]);
    return v.applyMatrix4(rotM);
  });
  if (pathPositions.length < 2) { setStatus("경로 포인트 부족"); return; }

  // 경로 라인
  const lineGeo = new THREE.BufferGeometry().setFromPoints(pathPositions);
  pathLine = new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ color: 0x4da3ff }));
  scene.add(pathLine);

  // 시작/끝 마커
  const sphGeo = new THREE.SphereGeometry(0.25, 16, 12);
  const start = new THREE.Mesh(sphGeo, new THREE.MeshBasicMaterial({ color: 0x39ff88 }));
  const end = new THREE.Mesh(sphGeo, new THREE.MeshBasicMaterial({ color: 0xff3b6b }));
  start.position.copy(pathPositions[0]);
  end.position.copy(pathPositions[pathPositions.length - 1]);
  scene.add(start, end);

  vehicle = buildVehicle();
  scene.add(vehicle);

  // 카메라 초기 시점: 평평한 지면(Y-up)을 위에서 비스듬히 내려다보기
  const box = new THREE.Box3().setFromPoints(pathPositions);
  const center = box.getCenter(new THREE.Vector3());
  const size = Math.max(box.getSize(new THREE.Vector3()).length(), 1);
  controls.target.copy(center);
  // 높이(Y) 위주로 올려서 top-down 에 가깝게, 약간 비스듬히
  camera.position.copy(center).add(new THREE.Vector3(size * 0.15, size * 1.0, size * 0.9));
  camera.near = Math.max(0.02, size / 5000);
  camera.far = size * 50;
  camera.updateProjectionMatrix();
}

// --- splat 로드 (DropInViewer: 내 씬에 추가) ---
async function loadSplats() {
  const viewer = new GaussianSplats3D.DropInViewer({
    gpuAcceleratedSort: true,
    sharedMemoryForWorkers: false, // COOP/COEP 헤더 불필요하게
  });
  await viewer.addSplatScene(SPLAT_URL, {
    showLoadingUI: false,
    splatAlphaRemovalThreshold: 5,
    rotation: new THREE.Quaternion().setFromEuler(
      new THREE.Euler(SPLAT_ROT[0], SPLAT_ROT[1], SPLAT_ROT[2], "XYZ")).toArray(),
    position: [0, 0, 0],
    scale: [1, 1, 1],
  });
  scene.add(viewer);
  return viewer;
}

// --- 애니메이션 상태 ---
let playing = true;
let speed = 1.0;
let tFrame = 0;             // 현재 경로 위치(부동 인덱스)
let followCam = false;
let lastT = performance.now();

const _tan = new THREE.Vector3();
const _look = new THREE.Vector3();
function updateVehicle(dtSec) {
  if (!vehicle || pathPositions.length < 2) return;
  if (playing) tFrame += dtSec * CAMERA_FPS * speed;
  const N = pathPositions.length;
  if (tFrame >= N - 1) tFrame = 0; // 루프
  const i = Math.floor(tFrame);
  const f = tFrame - i;
  const p0 = pathPositions[i], p1 = pathPositions[Math.min(i + 1, N - 1)];
  vehicle.position.lerpVectors(p0, p1, f);
  _tan.subVectors(p1, p0);
  if (_tan.lengthSq() > 1e-9) {
    _look.copy(vehicle.position).add(_tan);
    vehicle.lookAt(_look);  // 콘 팁(-Z)이 진행방향
  }
  frameInfoEl.textContent = `frame ${i} / ${N - 1}`;
  if (followCam) {
    const behind = _tan.clone().normalize().multiplyScalar(-4);
    behind.y += 2;
    camera.position.lerp(vehicle.position.clone().add(behind), 0.1);
    controls.target.lerp(vehicle.position, 0.1);
  }
}

function animate() {
  requestAnimationFrame(animate);
  const now = performance.now();
  const dt = Math.min((now - lastT) / 1000, 0.1);
  lastT = now;
  updateVehicle(dt);
  controls.update();
  renderer.render(scene, camera);
}

// --- UI ---
document.getElementById("playBtn").onclick = (e) => {
  playing = !playing;
  e.target.textContent = playing ? "⏸ 일시정지" : "▶ 재생";
};
document.getElementById("speed").oninput = (e) => { speed = parseFloat(e.target.value); };
document.getElementById("togglePath").onchange = (e) => { if (pathLine) pathLine.visible = e.target.checked; };
document.getElementById("toggleGrid").onchange = (e) => { grid.visible = e.target.checked; };
document.getElementById("follow").onchange = (e) => { followCam = e.target.checked; };

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// --- 부트 ---
try {
  setStatus("카메라 경로 로딩…");
  await loadPath();
  setStatus("splat 로딩… (수십 MB, 잠시만요)");
  await loadSplats();
  setStatus(`준비완료 · ${pathPositions.length} 프레임 경로`);
  animate();
} catch (err) {
  console.error(err);
  setStatus("로드 실패: " + err.message);
}
