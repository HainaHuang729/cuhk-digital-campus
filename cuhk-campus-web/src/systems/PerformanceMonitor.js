// Counts rendered frames, not idle requestAnimationFrame callbacks.
export class PerformanceMonitor {
  constructor(renderer, scene) {
    this.renderer = renderer;
    this.scene = scene;
    this.samples = [];
    this.last = 0;
    this.panel = document.createElement('aside');
    this.panel.id = 'performance-monitor';
    this.panel.hidden = true;
    this.panel.setAttribute('aria-label', 'Performance monitor');
    this.panel.style.cssText = 'position:absolute;right:20px;top:20px;z-index:40;background:#102025ed;color:#e3eeec;padding:14px;font:12px/1.7 monospace;white-space:pre;pointer-events:none';
    document.querySelector('#app').append(this.panel);
    addEventListener('keydown', event => {
      if (event.key.toLowerCase() === 'p' && !/INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) this.panel.hidden = !this.panel.hidden;
    });
  }
  sample(time) {
    const delta = time - this.last;
    this.last = time;
    if (delta > 0 && delta < 1000) this.samples.push({ time, delta });
    this.samples = this.samples.filter(s => time - s.time < 3000);
    if (time - (this.updated || 0) < 400) return;
    this.updated = time;
    if(time-(this.memoryUpdated||0)>2500){
      this.memoryUpdated=time;let bytes=0;const seen=new Set();
      const add=attribute=>{if(!attribute||seen.has(attribute))return;seen.add(attribute);bytes+=(attribute.isInterleavedBufferAttribute?attribute.data.array:attribute.array).byteLength;};
      this.scene.traverse(o=>{if(o.geometry){Object.values(o.geometry.attributes).forEach(add);add(o.geometry.index);}add(o.instanceMatrix);add(o.instanceColor);});
      this.geometryMB=+(bytes/1048576).toFixed(1);
    }
    const info = this.renderer.info;
    const deltas = this.samples.map(s => s.delta).sort((a,b) => a-b);
    const data = { fps: deltas.length ? +(1000 * deltas.length / deltas.reduce((a,b) => a+b,0)).toFixed(1) : 0,
      frameMsP95: deltas.length ? +deltas[Math.floor(deltas.length*.95)].toFixed(2) : 0,
      drawCalls: info.render.calls, triangles: info.render.triangles, geometries: info.memory.geometries,
      textures: info.memory.textures, pixelRatio: this.renderer.getPixelRatio(),
      viewport: [innerWidth, innerHeight], geometryMB:this.geometryMB??null, gpuMemoryMB:null, heapMB: performance.memory ? +(performance.memory.usedJSHeapSize/1048576).toFixed(1) : null };
    Object.assign(data,this.extra?.()||{});
    this.data = data;
    this.panel.dataset.metrics = JSON.stringify(data);
    this.panel.textContent = `PERFORMANCE · P to hide\n${data.fps} FPS · ${data.frameMsP95} ms p95\n${data.drawCalls} calls · ${data.triangles.toLocaleString()} triangles\n${data.geometries} geometries · ${data.textures} textures\nDPR ${data.pixelRatio} · ${innerWidth} × ${innerHeight}\nJS heap ${data.heapMB ?? 'unavailable'} MB\nGeometry ~${data.geometryMB??'—'} MB · GPU VRAM n/a${data.quality ? `\n${data.quality.toUpperCase()} · AO ${data.ao?'ON':'OFF'} · ${data.streaming.zones} zones\n${data.streaming.loadedMiB.toFixed(1)} MiB assets · ${data.life.people} people` : ''}`;
  }
}
