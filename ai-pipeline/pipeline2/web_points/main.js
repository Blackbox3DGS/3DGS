// 포인트클라우드 뷰어: .ply 를 THREE.Points 로 또렷하게 렌더 (LingBot viser 스타일) + 차량 경로
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { PLYLoader } from "three/addons/loaders/PLYLoader.js";

const statusEl = document.getElementById("status");
const frameInfoEl = document.getElementById("frameInfo");
const setStatus = (m) => { statusEl.textContent = m; };

const CFG = await fetch("./config.json").then(r => r.json()).catch(() => ({}));
const PLY_URL = CFG.ply_url || "./point_cloud.ply";
const POSES_URL = CFG.poses_url || "./camera_poses.json";
const CAMERA_FPS = CFG.camera_fps || 30;

const canvas = document.getElementById("canvas");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

const scene = new THREE.Scene();
scene.background = new THREE.Color("#0b0e14");
const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.001, 5000);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.dampingFactor = 0.08;

const grid = new THREE.GridHelper(40, 40, 0x335577, 0x16202c);
scene.add(grid);

let points = null, vehicle = null, pathLine = null, pathPositions = [];

// --- 포인트클라우드 로드 ---
const loader = new PLYLoader();
function loadPoints() {
  return new Promise((resolve, reject) => {
    loader.load(PLY_URL, (geo) => {
      geo.computeBoundingBox();
      const hasColor = !!geo.getAttribute("color");
      const mat = new THREE.PointsMaterial({
        size: 1.2, sizeAttenuation: false,   // 화면 px 고정 → 또렷
        vertexColors: hasColor, color: hasColor ? 0xffffff : 0x88aaff,
      });
      points = new THREE.Points(geo, mat);
      scene.add(points);
      resolve(geo.boundingBox);
    }, undefined, reject);
  });
}

async function loadPath() {
  const data = await fetch(POSES_URL).then(r => r.json()).catch(() => null);
  if (!data) return;
  pathPositions = (data.frames || []).map(f => {
    const m = f.transform_matrix;
    return new THREE.Vector3(m[0][3], m[1][3], m[2][3]);
  });
  if (pathPositions.length < 2) return;
  pathLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pathPositions),
    new THREE.LineBasicMaterial({ color: 0x4da3ff }));
  scene.add(pathLine);
  const sph = new THREE.SphereGeometry(0.04, 12, 8);
  const s0 = new THREE.Mesh(sph, new THREE.MeshBasicMaterial({ color: 0x39ff88 }));
  s0.position.copy(pathPositions[0]); scene.add(s0);
  vehicle = new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.16, 14).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: 0xff5a3c }));
  scene.add(vehicle);
}

function frameCamera(box) {
  const center = box.getCenter(new THREE.Vector3());
  const size = Math.max(box.getSize(new THREE.Vector3()).length(), 0.5);
  controls.target.copy(center);
  camera.position.copy(center).add(new THREE.Vector3(size * 0.1, size * 0.7, size * 0.7));
  camera.near = size / 5000; camera.far = size * 50; camera.updateProjectionMatrix();
}

// --- 애니메이션 ---
let playing = true, speed = 1, tFrame = 0, lastT = performance.now();
const _tan = new THREE.Vector3(), _look = new THREE.Vector3();
function updateVehicle(dt) {
  if (!vehicle || pathPositions.length < 2) return;
  if (playing) tFrame += dt * CAMERA_FPS * speed;
  const N = pathPositions.length;
  if (tFrame >= N - 1) tFrame = 0;
  const i = Math.floor(tFrame), f = tFrame - i;
  const p0 = pathPositions[i], p1 = pathPositions[Math.min(i + 1, N - 1)];
  vehicle.position.lerpVectors(p0, p1, f);
  _tan.subVectors(p1, p0);
  if (_tan.lengthSq() > 1e-9) { _look.copy(vehicle.position).add(_tan); vehicle.lookAt(_look); }
  frameInfoEl.textContent = `frame ${i} / ${N - 1}`;
}
function animate() {
  requestAnimationFrame(animate);
  const now = performance.now(), dt = Math.min((now - lastT) / 1000, 0.1); lastT = now;
  updateVehicle(dt); controls.update(); renderer.render(scene, camera);
}

// UI
document.getElementById("playBtn").onclick = (e) => { playing = !playing; e.target.textContent = playing ? "⏸ 일시정지" : "▶ 재생"; };
document.getElementById("psize").oninput = (e) => { if (points) points.material.size = parseFloat(e.target.value); };
document.getElementById("speed").oninput = (e) => { speed = parseFloat(e.target.value); };
document.getElementById("togglePath").onchange = (e) => { if (pathLine) pathLine.visible = e.target.checked; };
document.getElementById("toggleGrid").onchange = (e) => { grid.visible = e.target.checked; };
document.getElementById("bright").onchange = (e) => { scene.background = new THREE.Color(e.target.checked ? "#000000" : "#0b0e14"); };
window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

try {
  setStatus("포인트클라우드 로딩…");
  const box = await loadPoints();
  await loadPath();
  frameCamera(box);
  setStatus(`준비완료 · ${points.geometry.getAttribute("position").count.toLocaleString()} pts`);
  animate();
} catch (err) { console.error(err); setStatus("로드 실패: " + err.message); }
