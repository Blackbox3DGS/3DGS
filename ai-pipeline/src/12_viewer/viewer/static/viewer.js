// Standalone Stage 12 viewer: Gaussian-splat background + animated 3D
// vehicle meshes following Stage 09 trajectories.
//
// Loads:
//   data/manifest.json     — describes what's available for this run
//   data/background.splat  — Stage 11 output, loaded by gaussian-splats-3d
//   data/trajectories.json — Stage 09 tracks (class_name + per-frame xyz/velocity)
//   data/camera_path.json  — flat list of camera centres for a polyline
//   models/car.glb         — user-supplied CC0 asset (one shared mesh, cloned per track)
//
// Coordinate convention after Phase D-pre alignment: +z is up, ground at z=0.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import * as GS from "@mkkellogg/gaussian-splats-3d";

import { buildAnimators } from "./trajectory_animator.js";

const STATUS = document.getElementById("status");
const PLAY   = document.getElementById("play");
const SCRUB  = document.getElementById("scrub");
const TIME   = document.getElementById("time");

function setStatus(msg, isErr = false) {
  STATUS.textContent = msg;
  STATUS.classList.toggle("err", isErr);
}

// ---------------------------------------------------------------------------
// Scene scaffolding
// ---------------------------------------------------------------------------

const app = document.getElementById("app");
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(devicePixelRatio);
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
app.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x101418);

const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.05, 500);
camera.up.set(0, 0, 1);                     // +z up (gravity-aligned world)
camera.position.set(8, -8, 4);
camera.lookAt(0, 0, 0);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, 0);
controls.enableDamping = true;

// Ambient + hemi light so meshes are readable against splat background.
scene.add(new THREE.AmbientLight(0xffffff, 0.55));
const hemi = new THREE.HemisphereLight(0xffffff, 0x202830, 0.7);
hemi.position.set(0, 0, 5);
scene.add(hemi);

// Faint ground grid as orientation aid.
const grid = new THREE.GridHelper(40, 40, 0x444, 0x222);
grid.rotation.x = Math.PI / 2;              // grid is XY when rotated; +z up
scene.add(grid);

addEventListener("resize", () => {
  renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
});

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

async function loadCarMesh(url) {
  const loader = new GLTFLoader();
  const gltf = await new Promise((res, rej) =>
    loader.load(url, res, undefined, rej));
  const mesh = gltf.scene;

  // Normalize: scale longest dimension to 4.5 m (typical car length) and
  // center on its base so origin sits on the ground plane.
  const box = new THREE.Box3().setFromObject(mesh);
  const size = new THREE.Vector3();
  box.getSize(size);
  const longest = Math.max(size.x, size.y, size.z);
  const scale = 4.5 / Math.max(longest, 1e-6);
  mesh.scale.setScalar(scale);

  const newBox = new THREE.Box3().setFromObject(mesh);
  const center = new THREE.Vector3();
  newBox.getCenter(center);
  mesh.position.set(-center.x, -center.y, -newBox.min.z);  // origin at base

  // Wrap in a group so per-instance position/rotation doesn't fight the
  // normalisation transform above.
  const group = new THREE.Group();
  group.add(mesh);
  return group;
}

function makeFallbackCarMesh() {
  // Used when car.glb is missing — a simple box at car-ish dimensions so the
  // animation still demos visibly. 4.5 m × 1.8 m × 1.5 m.
  const geo = new THREE.BoxGeometry(4.5, 1.8, 1.5);
  const mat = new THREE.MeshStandardMaterial({ color: 0x4488ff, metalness: 0.2, roughness: 0.6 });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.z = 0.75;  // half-height above ground
  const group = new THREE.Group();
  group.add(mesh);
  return group;
}

function drawCameraPath(positions) {
  if (!positions || positions.length < 2) return;
  const pts = positions.map(p => new THREE.Vector3(p[0], p[1], p[2]));
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({ color: 0xff8844, transparent: true, opacity: 0.7 });
  scene.add(new THREE.Line(geo, mat));
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

let animators = [];
let vehicleInstances = [];     // parallel to animators
let tMin = 0, tMax = 0;
let playing = false;
let currentTime = 0;
let lastFrame = performance.now();

async function boot() {
  setStatus("Reading manifest…");
  let manifest = { files: [], vehicle_model: "models/car.glb" };
  try { manifest = await fetchJson("data/manifest.json"); } catch (e) {
    setStatus(`manifest.json missing — ${e.message}`, true);
  }

  // 1. Splat background.
  if (manifest.files.includes("background.splat")) {
    setStatus("Loading Gaussian splat background…");
    try {
      const viewerGS = new GS.DropInViewer({
        cameraUp: [0, 0, 1],
        initialCameraPosition: camera.position.toArray(),
        initialCameraLookAt: [0, 0, 0],
        sharedMemoryForWorkers: false,
      });
      await viewerGS.addSplatScenes([
        { path: "data/background.splat", splatAlphaRemovalThreshold: 5 },
      ]);
      scene.add(viewerGS);
    } catch (e) {
      console.warn("splat load failed:", e);
      setStatus("Splat load failed, continuing without background", true);
    }
  }

  // 2. Camera path overlay.
  if (manifest.files.includes("camera_path.json")) {
    try {
      const cp = await fetchJson("data/camera_path.json");
      drawCameraPath(cp.positions);
    } catch (e) { console.warn("camera_path skipped:", e); }
  }

  // 3. Trajectories + per-track mesh instances.
  if (manifest.files.includes("trajectories.json")) {
    setStatus("Loading trajectories…");
    const tj = await fetchJson("data/trajectories.json");
    animators = buildAnimators(tj);

    setStatus(`Loading vehicle model (${manifest.vehicle_model})…`);
    let template;
    try {
      template = await loadCarMesh(manifest.vehicle_model);
    } catch (e) {
      console.warn("car.glb missing, using box fallback:", e);
      template = makeFallbackCarMesh();
    }

    for (const a of animators) {
      const inst = template.clone(true);
      inst.visible = false;
      scene.add(inst);
      vehicleInstances.push(inst);
    }

    if (animators.length) {
      tMin = Math.min(...animators.map(a => a.t0));
      tMax = Math.max(...animators.map(a => a.t1));
      currentTime = tMin;
      SCRUB.min = tMin;
      SCRUB.max = tMax;
      SCRUB.value = tMin;
    }
  }

  setStatus(`Loaded: ${animators.length} tracks, t=[${tMin.toFixed(2)}, ${tMax.toFixed(2)}] s`);
}

// ---------------------------------------------------------------------------
// Animation
// ---------------------------------------------------------------------------

function updateVehicles(timeSec) {
  for (let i = 0; i < animators.length; i++) {
    const a = animators[i];
    const inst = vehicleInstances[i];
    const s = a.sample(timeSec);
    if (!s.present) { inst.visible = false; continue; }
    inst.visible = true;
    inst.position.copy(s.position);
    // Heading on the XY plane → rotation about +z.
    inst.rotation.set(0, 0, s.heading);
    inst.traverse(o => {
      if (o.isMesh && o.material) {
        o.material.transparent = s.alpha < 1.0;
        o.material.opacity = s.alpha;
      }
    });
  }
}

function tick() {
  const now = performance.now();
  const dt = (now - lastFrame) / 1000;
  lastFrame = now;

  if (playing && tMax > tMin) {
    currentTime += dt;
    if (currentTime > tMax) currentTime = tMin;       // loop
    SCRUB.value = currentTime;
  }
  TIME.textContent = `${currentTime.toFixed(2)} s`;

  updateVehicles(currentTime);
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}

PLAY.addEventListener("click", () => {
  playing = !playing;
  PLAY.textContent = playing ? "⏸ Pause" : "▶ Play";
  lastFrame = performance.now();   // avoid huge dt after long pause
});
SCRUB.addEventListener("input", () => {
  currentTime = parseFloat(SCRUB.value);
});

boot().catch(e => setStatus(`Boot failed: ${e.message}`, true));
requestAnimationFrame(tick);
