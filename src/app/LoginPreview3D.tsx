import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

/**
 * 로그인 화면 좌측 패널에서 hover 시 활성화되는 3D 미니 씬.
 * - 차량 A·B(.glb) + 격자 바닥 + 궤적 라인 + 충돌 지점
 * - 카메라 자동 orbit (사용자 인터랙션 없음)
 * - pointer-events: none (로그인 폼 방해 금지)
 */
export default function LoginPreview3D() {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    let disposed = false;
    let rafId: number | null = null;

    const width = mount.clientWidth || 480;
    const height = mount.clientHeight || 320;

    // 씬·카메라·렌더러
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100);
    camera.position.set(7, 4.5, 7);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x080d16, 0);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    mount.appendChild(renderer.domElement);

    // 조명 — 자연스러운 3-light setup
    const ambient = new THREE.AmbientLight(0xc4d4e8, 0.45);
    scene.add(ambient);
    const hemi = new THREE.HemisphereLight(0xdce6f0, 0x1a2540, 0.35);
    scene.add(hemi);
    const dir = new THREE.DirectionalLight(0xffffff, 0.7);
    dir.position.set(5, 12, 6);
    scene.add(dir);
    const fill = new THREE.DirectionalLight(0x8faabe, 0.2);
    fill.position.set(-4, 3, -3);
    scene.add(fill);

    // 격자 바닥
    const grid = new THREE.GridHelper(20, 24, 0x1e3550, 0x1e3550);
    (grid.material as THREE.Material).opacity = 0.25;
    (grid.material as THREE.Material).transparent = true;
    scene.add(grid);

    // 바닥면 — 미세한 반사
    const floorGeo = new THREE.PlaneGeometry(20, 20);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x0a1020,
      roughness: 0.9,
      metalness: 0.05,
      transparent: true,
      opacity: 0.4,
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.01;
    scene.add(floor);

    // 차량 컨테이너
    const carA = new THREE.Group();
    const carB = new THREE.Group();
    carA.position.set(-2.2, 0, -1.5);
    carA.rotation.y = Math.PI * 0.25;
    carB.position.set(2.0, 0, 1.3);
    carB.rotation.y = -Math.PI * 0.3;
    scene.add(carA);
    scene.add(carB);

    // 차량 모델 로드 (실패해도 무시 — 격자만 표시되는 폴백)
    const loader = new GLTFLoader();
    loader.load(
      '/car-a.glb',
      (gltf) => {
        if (disposed) return;
        carA.add(gltf.scene);
      },
      undefined,
      () => {},
    );
    loader.load(
      '/car-b.glb',
      (gltf) => {
        if (disposed) return;
        carB.add(gltf.scene);
      },
      undefined,
      () => {},
    );

    // 궤적 라인 (차량 A → 충돌 지점)
    const trajPts = [
      new THREE.Vector3(-4.5, 0.05, -3.5),
      new THREE.Vector3(-3.2, 0.05, -2.5),
      new THREE.Vector3(-2.2, 0.05, -1.5),
      new THREE.Vector3(0, 0.05, 0),
      new THREE.Vector3(2.0, 0.05, 1.3),
      new THREE.Vector3(3.5, 0.05, 2.8),
    ];
    const trajGeo = new THREE.BufferGeometry().setFromPoints(trajPts);
    const trajMat = new THREE.LineBasicMaterial({
      color: 0xdc8c64,
      transparent: true,
      opacity: 0.5,
    });
    const trajLine = new THREE.Line(trajGeo, trajMat);
    scene.add(trajLine);

    // 충돌 지점 마커
    const impactGeo = new THREE.SphereGeometry(0.08, 16, 16);
    const impactMat = new THREE.MeshBasicMaterial({ color: 0x60a5fa });
    const impact = new THREE.Mesh(impactGeo, impactMat);
    impact.position.set(0, 0.1, 0);
    scene.add(impact);

    // 카메라 자동 orbit
    let angle = Math.PI * 0.25;
    const radius = 7;
    const heightY = 4.5;

    const animate = () => {
      if (disposed) return;
      angle += 0.0018;
      camera.position.x = Math.cos(angle) * radius;
      camera.position.z = Math.sin(angle) * radius;
      camera.position.y = heightY + Math.sin(angle * 0.5) * 0.2;
      camera.lookAt(0, 0.2, 0);
      renderer.render(scene, camera);
      rafId = requestAnimationFrame(animate);
    };
    animate();

    // 리사이즈 대응
    const onResize = () => {
      if (!mountRef.current) return;
      const w = mountRef.current.clientWidth;
      const h = mountRef.current.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', onResize);

    return () => {
      disposed = true;
      if (rafId !== null) cancelAnimationFrame(rafId);
      window.removeEventListener('resize', onResize);
      renderer.dispose();
      trajGeo.dispose();
      trajMat.dispose();
      impactGeo.dispose();
      impactMat.dispose();
      floorGeo.dispose();
      floorMat.dispose();
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div
      ref={mountRef}
      className="absolute inset-0 w-full h-full"
      style={{ pointerEvents: 'none' }}
      aria-hidden
    />
  );
}
