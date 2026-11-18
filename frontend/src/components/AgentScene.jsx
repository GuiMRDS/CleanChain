import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { createUniforms } from '../three/theme.js';
import { createBackground } from '../three/background.js';
import { createHologramMaterial } from '../three/hologram.js';
import './AgentScene.css';

// Exact Clarix hero framing (scroll = 0): camera offset to the left so the
// robot sits on the right, heroic low angle, model close to the camera.
const CAMERA = { fov: 75, position: [-1.8, -1.0, 6.5], target: [-1.8, 0.5, 0] };
const ROBOT = { position: [-0.6, -3.93, 4.17], rotation: [-0.05026, -0.92781, -0.12566] };

// Free space (px) kept between the cards and the robot, and to the screen edge.
const CLEARANCE = 32;
const EDGE = 16;

// `clearOfRef`: element the robot must never sit behind (the cards row).
// The robot keeps the Clarix pose; the camera view is scaled down (zoom) only
// if needed to fit it whole, then slid right (setViewOffset) to clear the cards.
// Placement is computed on load / resize only — the robot never drifts.
export default function AgentScene({ clearOfRef }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight, false);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.autoClear = false;

    const uniforms = createUniforms(window.innerWidth, window.innerHeight);

    // Background pass
    const bgScene = new THREE.Scene();
    const bgCamera = new THREE.Camera();
    const background = createBackground(uniforms);
    bgScene.add(background);

    // Robot pass
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(CAMERA.fov, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(...CAMERA.position);
    camera.lookAt(...CAMERA.target);

    scene.add(new THREE.AmbientLight(0xffffff, 1));
    const key = new THREE.DirectionalLight(0xffffff, 2);
    key.position.set(5, 10, 5);
    const fill = new THREE.DirectionalLight(0xffffff, 1);
    fill.position.set(-5, -5, -5);
    scene.add(key, fill);

    const hologram = createHologramMaterial(uniforms);
    const draco = new DRACOLoader();
    draco.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.7/');
    const loader = new GLTFLoader();
    loader.setDRACOLoader(draco);

    let mixer = null;
    let model = null;
    let disposed = false;

    // --- Fit the robot between the cards and the right edge --------------
    // World-space sample of the robot's surface in its pose, captured once on load.
    // Projecting real vertices (not a bounding box) gives the true silhouette width.
    let robotPoints = [];
    const corner = new THREE.Vector3();

    // Sample the surface across the whole idle clip so the fit holds for every pose.
    const sampleRobot = (clips) => {
      const pts = [];
      const v = new THREE.Vector3();
      const duration = Math.max(0, ...clips.map((c) => c.duration));
      const steps = duration > 0 ? 16 : 1;
      for (let s = 0; s < steps; s++) {
        mixer?.setTime((duration * s) / steps);
        model.updateMatrixWorld(true);
        model.traverse((child) => {
          if (!child.isMesh) return;
          child.skeleton?.update(); // bone matrices normally refresh at render time
          const count = child.geometry.attributes.position.count;
          const stride = Math.max(1, Math.floor(count / 500));
          for (let i = 0; i < count; i += stride) {
            child.getVertexPosition(i, v); // applies skinning for SkinnedMesh
            pts.push(v.clone().applyMatrix4(child.matrixWorld));
          }
        });
      }
      mixer?.setTime(0);
      return pts;
    };

    const robotScreenX = () => {
      camera.zoom = 1;
      camera.clearViewOffset(); // also refreshes the projection matrix
      camera.updateMatrixWorld();
      let min = Infinity;
      let max = -Infinity;
      for (const p of robotPoints) {
        corner.copy(p).project(camera);
        if (corner.y < -1.05) continue; // below the screen: doesn't take horizontal room
        const x = ((corner.x + 1) / 2) * window.innerWidth;
        min = Math.min(min, x);
        max = Math.max(max, x);
      }
      return { min, max };
    };

    const placeRobot = () => {
      if (!robotPoints.length) return;
      const w = window.innerWidth;
      const h = window.innerHeight;
      const { min, max } = robotScreenX();
      const cardsRight = clearOfRef?.current?.getBoundingClientRect().right ?? 0;
      const left = cardsRight + CLEARANCE;
      const available = w - EDGE - left;

      // Shrink (around the screen centre) only when the robot can't fit whole.
      const zoom = Math.max(0.35, Math.min(1, available / (max - min)));
      const scaledMin = w / 2 + (min - w / 2) * zoom;
      const shift = Math.max(0, left - scaledMin);

      camera.zoom = zoom;
      if (shift < 0.5) camera.clearViewOffset();
      else camera.setViewOffset(w, h, -shift, 0, w, h);
      camera.updateProjectionMatrix();
    };

    loader.load('/model.glb', (gltf) => {
      if (disposed) return;
      model = gltf.scene;
      const size = new THREE.Box3().setFromObject(model).getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);
      model.scale.setScalar(maxDim > 0 ? 5 / maxDim : 1);
      model.position.set(...ROBOT.position);
      model.rotation.set(...ROBOT.rotation);
      model.traverse((child) => {
        if (child.isMesh) child.material = hologram;
      });
      scene.add(model);

      // The GLB ships its own idle animation — this is what gives the natural pose.
      if (gltf.animations.length) {
        mixer = new THREE.AnimationMixer(model);
        gltf.animations.forEach((clip) => mixer.clipAction(clip).play());
      }
      robotPoints = sampleRobot(gltf.animations);
      placeRobot();
    });

    // Re-fit only when the layout changes (cards appear/hide, window resizes).
    const ro = new ResizeObserver(placeRobot);
    if (clearOfRef?.current) ro.observe(clearOfRef.current);

    // Input + resize
    const targetMouse = new THREE.Vector2(0.5, 0.5);
    const onMove = (e) => targetMouse.set(e.clientX / window.innerWidth, 1 - e.clientY / window.innerHeight);
    const onResize = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      uniforms.resolution.value.set(w, h);
      placeRobot();
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('resize', onResize);

    // Loop
    const timer = new THREE.Timer();
    let frame = 0;
    const tick = (now) => {
      timer.update(now);
      const delta = timer.getDelta();
      const t = timer.getElapsed();
      uniforms.time.value = t;
      uniforms.scanX.value = 0.35 + ((t * 0.08) % 0.65);
      uniforms.mouse.value.lerp(targetMouse, Math.min(1, delta * 3));
      mixer?.update(delta);

      renderer.clear();
      renderer.render(bgScene, bgCamera);
      renderer.clearDepth();
      renderer.render(scene, camera);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      ro.disconnect();
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('resize', onResize);
      background.geometry.dispose();
      background.material.dispose();
      hologram.dispose();
      scene.traverse((o) => o.geometry?.dispose());
      mixer?.stopAllAction();
      timer.dispose();
      draco.dispose();
      renderer.dispose();
    };
  }, [clearOfRef]);

  return <canvas ref={canvasRef} className="agent-scene" aria-hidden="true" />;
}
