import * as THREE from 'three';

// Dark physical material patched with Clarix's holographic shader: iridescent
// waves, fresnel rim, flowing scan lines and a screen-space pixel dither.
export function createHologramMaterial(uniforms) {
  const material = new THREE.MeshPhysicalMaterial({
    color: 0x010103,
    metalness: 0.9,
    roughness: 0.2,
    clearcoat: 1,
    clearcoatRoughness: 0.1,
    transparent: true,
    opacity: 0.95,
    side: THREE.DoubleSide,
  });

  material.onBeforeCompile = (shader) => {
    for (const key of ['time', 'colorCyan', 'colorPurple', 'colorBlue', 'colorPeach', 'colorHotPink', 'edgeBlurAmount']) {
      shader.uniforms[key] = uniforms[key];
    }

    shader.vertexShader =
      'varying vec3 vLocalPosition;\n' +
      shader.vertexShader.replace(
        '#include <begin_vertex>',
        `#include <begin_vertex>
         vLocalPosition = position;`
      );

    shader.fragmentShader =
      `uniform float time;
       uniform float edgeBlurAmount;
       uniform vec3 colorCyan, colorPurple, colorBlue, colorPeach, colorHotPink;
       varying vec3 vLocalPosition;\n` +
      shader.fragmentShader.replace(
        '#include <dithering_fragment>',
        `#include <dithering_fragment>
        vec3 vDir = normalize(vViewPosition);
        float fresnel = 1.0 - max(dot(vDir, normal), 0.0);
        float fp = pow(fresnel, 2.0);

        float w = (sin(vLocalPosition.x * 2.0 - time)
                 + cos(vLocalPosition.y * 1.5 + time * 0.8)
                 + sin(vLocalPosition.z * 2.5 + time * 0.5)) / 3.0;
        w = smoothstep(-0.5, 0.5, w);
        float wp = sin(vLocalPosition.y * 2.0 - vLocalPosition.x + time * 1.2) * 0.5 + 0.5;

        vec3 mc = mix(colorBlue, colorCyan, w);
        mc = mix(mc, colorHotPink, smoothstep(0.2, 0.8, wp));
        mc = mix(mc, colorPeach, smoothstep(0.5, 0.95, wp));
        mc = mix(mc, colorPurple, fresnel);

        vec3 glow = colorCyan * fp * 1.5;
        float dist = sin(vLocalPosition.x * 2.5 + time * 0.5) * 0.4 + cos(vLocalPosition.z * 2.0) * 0.4;
        float lines = fract((vLocalPosition.y + dist - time * 0.2) * 1.2);
        float li = smoothstep(0.2, 0.6, lines) * smoothstep(1.0, 0.6, lines);
        vec3 lg = vec3(0.2, 0.8, 1.0) * li * (0.3 + fresnel);
        vec3 fe = mc * 0.6 + glow + lg;

        // Pixel dither: squares (cool tones) morph into circles (warm tones)
        float ps = 8.0;
        vec2 lu = fract(gl_FragCoord.xy / ps) - 0.5;
        float luma = dot(fe, vec3(0.2126, 0.7152, 0.0722));
        float cs = clamp(luma * 1.2, 0.05, 0.45);
        float cr = mix(0.0, cs, wp);
        float d = length(max(abs(lu) - (cs - cr), 0.0)) - cr;
        float sa = smoothstep(1.5 / ps, 0.0, d);
        if (sa < 0.1) discard;

        float eb = smoothstep(mix(1.0, 0.7, edgeBlurAmount), mix(0.99, 0.1, edgeBlurAmount), fresnel);
        fe *= 1.2;
        gl_FragColor = vec4(gl_FragColor.rgb + fe, gl_FragColor.a * sa * eb);`
      );
  };

  return material;
}
