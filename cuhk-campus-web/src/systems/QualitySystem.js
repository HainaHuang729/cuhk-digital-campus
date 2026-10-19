export const qualityLevels = {
  high: { pixelRatio: 1.5, label: 'High' },
  medium: { pixelRatio: 1.25, label: 'Medium' },
  low: { pixelRatio: 1, label: 'Low' },
};
export class QualitySystem {
  constructor(renderer, { mobile = false, onChange = () => {}, notify = () => {} } = {}) {
    this.renderer=renderer; this.mobile=mobile; this.onChange=onChange; this.notify=notify;
    this.automatic=true; this.level=mobile?'low':'high'; this.lastChange=performance.now(); this.slowSince=null;
    renderer.setPixelRatio(Math.min(devicePixelRatio,qualityLevels[this.level].pixelRatio));
  }
  set(level, automatic = false) {
    if (!qualityLevels[level]) return;
    this.automatic=automatic; this.level=level; this.lastChange=performance.now(); this.slowSince=null;
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,qualityLevels[level].pixelRatio));
    this.onChange(level);
  }
  update(fps, now, busy = false) {
    if (!this.automatic || busy || this.level==='low' || now-this.lastChange<20000 || !fps) { this.slowSince=null; return; }
    if (fps>=(this.level==='high'?40:25)) { this.slowSince=null; return; }
    this.slowSince ??= now;
    if (now-this.slowSince>8000) {
      this.set(this.level==='high'?'medium':'low',true);
      this.notify(`已调整为 ${qualityLevels[this.level].label} 画质，让校园漫游更流畅`);
    }
  }
}
