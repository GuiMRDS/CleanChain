import * as THREE from 'three';

// Shared uniforms: background grid and robot hologram animate in sync.
export function createUniforms(width, height) {
  return {
    time: { value: 0 },
    mouse: { value: new THREE.Vector2(0.72, 0.55) },
    resolution: { value: new THREE.Vector2(width, height) },
    bgColor: { value: new THREE.Color(0xf6fafe) },
    colorCyan: { value: new THREE.Color(0x00aaff) },
    colorBlue: { value: new THREE.Color(0x0091ff) },
    colorHotPink: { value: new THREE.Color(0xff0099) },
    colorPeach: { value: new THREE.Color(0xff3355) },
    colorPurple: { value: new THREE.Color(0x8000ff) },
    pixelSize: { value: 15 },
    edgeBlurAmount: { value: 0.5 },
    scanX: { value: 0 },
  };
}
