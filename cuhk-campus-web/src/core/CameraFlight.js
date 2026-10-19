import { Vector3, MathUtils } from 'three';

export class CameraFlight {
  constructor(camera, controls, { reducedMotion = false, onComplete = () => {} } = {}) {
    this.camera = camera; this.controls = controls;
    this.reducedMotion = reducedMotion; this.onComplete = onComplete;
    this.active = null; this.buildings = []; this.ground = null;
    controls.addEventListener('start', () => { this.active = null; controls.autoRotate = false; });
  }
  flyTo(position, target, duration = 1600) {
    this.controls.autoRotate = false;
    const to = new Vector3(...position);
    this.active = { start: performance.now(), duration: this.reducedMotion ? 0 : duration,
      from: this.camera.position.clone(), to, fromTarget: this.controls.target.clone(), toTarget: new Vector3(...target),
      lift: Math.min(170, this.camera.position.distanceTo(to) * .14) };
  }
  focus(building, close = false, portrait = false) {
    if (building.cameraPosition && building.cameraTarget) return this.flyTo(building.cameraPosition, building.cameraTarget);
    const target = new Vector3(...building.position);
    const size = Math.max(...(building.size || [70,30,70]));
    const distance = Math.max(close ? 135 : 290, size * (close ? 2.25 : 3.5)) * (portrait ? 1.3 : 1);
    const direction = this.camera.position.clone().sub(this.controls.target).normalize();
    direction.y = Math.max(.6, direction.y); direction.normalize();
    this.flyTo(target.clone().addScaledVector(direction, distance).toArray(), target.toArray());
  }
  update(now) {
    const f = this.active;
    if (!f) return false;
    const t = f.duration ? Math.min(1, (now-f.start)/f.duration) : 1;
    const eased = t*t*(3-2*t);
    this.camera.position.lerpVectors(f.from, f.to, eased);
    this.camera.position.y += Math.sin(Math.PI*eased)*f.lift;
    this.controls.target.lerpVectors(f.fromTarget, f.toTarget, eased);
    if (t === 1) { this.active = null; this.onComplete(); }
    return true;
  }
  constrain() {
    const p = this.camera.position;
    const oldX=p.x,oldZ=p.z;
    p.x = MathUtils.clamp(p.x,-4500,4500); p.z = MathUtils.clamp(p.z,-4500,4500);
    let floor = 8;
    const g = this.ground;
    if (g) {
      const c = Math.floor((p.x-g.xmin)/g.step), r = Math.floor((p.z-g.zmin)/g.step);
      if (c>=0 && r>=0 && c<g.cols-1 && r<g.rows-1) floor = Math.max(floor,...[r*g.cols+c,r*g.cols+c+1,(r+1)*g.cols+c,(r+1)*g.cols+c+1].map(i=>g.heights[i]+12));
    }
    for (const b of this.buildings) {
      const [x,y,z]=b.position, [w,h,d]=b.size;
      if (Math.abs(p.x-x)<w/2+5 && Math.abs(p.z-z)<d/2+5) floor=Math.max(floor,y+h/2+12);
    }
    if (p.y<floor) { p.y=floor; return true; }
    return p.x!==oldX||p.z!==oldZ;
  }
}
