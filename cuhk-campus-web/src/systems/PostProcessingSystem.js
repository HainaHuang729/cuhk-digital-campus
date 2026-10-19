import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

export class PostProcessingSystem {
  constructor({ renderer, scene, camera }) {
    Object.assign(this, { renderer, scene, camera });
    this.enabled = true;
    this.quality = 'medium';
    this.active = false;
    this.width = 1;
    this.height = 1;
    // Count all passes, including shadow maps and AO, instead of only the last full-screen quad.
    renderer.info.autoReset = false;
    const size = renderer.getSize(new THREE.Vector2());
    this.setSize(size.x, size.y);
  }

  createComposer() {
    if (this.composer) return;
    this.composer = new EffectComposer(this.renderer);
    this.composer.renderTarget1.samples = 2;
    this.composer.renderTarget2.samples = 2;
    this.renderPass = new RenderPass(this.scene, this.camera);
    this.ao = new GTAOPass(this.scene, this.camera, 1, 1, undefined,
      { radius: 3.2, thickness: 1.8, distanceFallOff: 1, scale: 1, samples: 8 },
      { samples: 8, radius: 5, rings: 2 });
    this.ao.normalMaterial.side = THREE.DoubleSide;
    this.ao.blendIntensity = .18;
    this.output = new OutputPass();
    this.composer.addPass(this.renderPass);
    this.composer.addPass(this.ao);
    this.composer.addPass(this.output);
    this.setSize(this.width, this.height);
  }

  setEnabled(value) { this.enabled = Boolean(value); }
  setQuality(level) { this.quality = level; }

  setSize(width, height) {
    this.width = Math.max(1, Math.floor(width));
    this.height = Math.max(1, Math.floor(height));
    if (!this.composer) return;
    const ratio = this.renderer.getPixelRatio();
    this.composer.setPixelRatio(ratio);
    this.composer.setSize(this.width, this.height);
    // Only the contact occlusion buffers are reduced; the beauty pass keeps full output resolution.
    this.ao.setSize(Math.ceil(this.width * ratio * .6), Math.ceil(this.height * ratio * .6));
  }

  render(cameraDistance = Infinity) {
    this.renderer.info.reset();
    // ponytail: screen-space AO renders geometry twice; restrict it to high-quality nearby views.
    // Upgrade this path to shared normal/depth buffers if sustained GPU profiling justifies MRT.
    this.active = this.enabled && this.quality === 'high' && cameraDistance < 1100;
    if (this.active) {
      this.createComposer();
      this.ao.blendIntensity = .18 * (1 - THREE.MathUtils.smoothstep(cameraDistance, 700, 1100));
      this.composer.render(0);
    } else this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.ao?.dispose();
    this.output?.dispose();
    this.renderPass?.dispose();
    this.composer?.dispose();
  }
}
