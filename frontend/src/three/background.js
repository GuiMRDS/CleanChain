import * as THREE from 'three';

// Full-screen ASCII grid background (from Clarix): rounded squares revealed in
// organic blobs, a blue/cyan/pink gradient, a ripple around the cursor, and
// scattered cells that light up as the agent's scan sweeps across.
export function createBackground(uniforms) {
  const material = new THREE.ShaderMaterial({
    uniforms,
    depthWrite: false,
    depthTest: false,
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = vec4(position.xy, 1.0, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float time, pixelSize, scanX;
      uniform vec2 mouse, resolution;
      uniform vec3 bgColor, colorCyan, colorBlue, colorHotPink, colorPeach;
      varying vec2 vUv;

      mat2 rot(float a) { return mat2(cos(a), -sin(a), sin(a), cos(a)); }
      float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }

      void main() {
        float aspect = resolution.x / resolution.y;
        vec2 a = vec2(vUv.x * aspect, vUv.y);
        vec2 g = a * (resolution.y / pixelSize);
        vec2 cell = floor(g);
        vec2 l = fract(g) - 0.5;

        // 1. Procedural colours
        float w1 = sin(a.x * 4.0 - time * 0.8);
        float w2 = cos(a.y * 3.0 + time * 0.6);
        float cw = smoothstep(-0.8, 0.8, (w1 + w2) * 0.5);
        float wp = sin(a.y * 3.0 - a.x * 2.0 + time * 0.9) * 0.5 + 0.5;
        vec3 c = mix(colorBlue, colorCyan, cw);
        c = mix(c, colorHotPink, smoothstep(0.1, 0.7, wp));
        c = mix(c, colorPeach, smoothstep(0.5, 1.0, wp));
        vec3 gridCol = mix(c, vec3(1.0), 0.6);

        // 2. Breathing rounded squares
        float box = 0.3 + sin(time * 2.0 + g.x * 0.2 + g.y * 0.2) * 0.1;
        float r = 0.12;
        float d = length(max(abs(l) - (box - r), 0.0)) - r;
        float alpha = smoothstep(0.05, 0.0, d);

        // 3. Masks: radial (biased to the robot on the right) * organic blobs
        vec2 rc = mix(vec2(0.70, 0.50), mouse, 0.3);
        vec2 dv = (vUv - rc) * vec2(aspect, 1.0);
        float radial = smoothstep(0.85, 0.08, length(dv * vec2(0.9, 1.0)));

        vec2 p = a * 3.0;
        vec2 ma = vec2(mouse.x * aspect, mouse.y);
        float md = distance(a, ma);
        float n = 0.0;
        n += sin(p.x + time * 0.4) * sin(p.y + time * 0.3);
        p *= rot(1.1); n += sin(p.x * 1.5 - time * 0.5) * sin(p.y * 1.5 + time * 0.2);
        p *= rot(2.3); n += sin(p.x * 2.0 + time * 0.3) * sin(p.y * 2.0 - time * 0.4);
        n += cos(md * 12.0 - time * 3.0) * smoothstep(0.6, 0.0, md) * 1.2;
        float blob = smoothstep(0.0, 1.5, n);
        float cursor = smoothstep(0.2, 0.0, md);

        // 4. Scan: random cells light up behind the sweep
        float scanned = step(hash(cell), 0.18) * smoothstep(scanX + 0.15, scanX - 0.15, vUv.x);

        float m = clamp(radial * blob + cursor * 0.5 + scanned * 0.35 * radial, 0.0, 1.0);
        gl_FragColor = vec4(mix(bgColor, gridCol, alpha * m * 0.85), 1.0);
      }
    `,
  });

  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
  mesh.frustumCulled = false;
  return mesh;
}
