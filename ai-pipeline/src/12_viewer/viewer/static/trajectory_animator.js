// Per-track animator: holds a parsed trajectory and exposes pose(time).
//
// Heading is derived from velocity_mps via atan2(vy, vx) and smoothed with an
// EMA. Below the low-speed threshold we hold the previous heading — direction
// from near-zero velocity is meaningless and would jitter the mesh.
//
// "Up" axis after Phase D-pre alignment is +z. We rotate the mesh around z so
// its forward axis (+x by glTF convention) tracks the velocity direction.

import * as THREE from "three";

const ASSUMED_FPS = 10;          // matches Stage 02's extraction rate
const EMA_ALPHA = 0.3;           // heading smoothing
const LOW_SPEED_MPS = 0.5;       // below this, keep previous heading

export class TrajectoryAnimator {
  constructor(trackId, classNames, points) {
    this.trackId = trackId;
    this.className = classNames;
    this.points = points;        // sorted by frame_idx
    this._cacheHeadings();
  }

  // First/last time (seconds) covered by this track.
  get t0()    { return this.points[0].frame_idx / ASSUMED_FPS; }
  get t1()    { return this.points[this.points.length - 1].frame_idx / ASSUMED_FPS; }
  get tSpan() { return this.t1 - this.t0; }

  _cacheHeadings() {
    // Pre-compute one smoothed heading per point. Speeds up scrubbing later.
    let prev = null;
    for (const p of this.points) {
      const [vx, vy /*vz*/] = p.velocity_mps;
      const speed = Math.hypot(vx, vy);
      let h;
      if (speed < LOW_SPEED_MPS && prev !== null) {
        h = prev;
      } else {
        const raw = Math.atan2(vy, vx);
        h = (prev === null) ? raw : _emaAngle(prev, raw, EMA_ALPHA);
      }
      p._heading = h;
      prev = h;
    }
  }

  // Return {position: Vector3, heading: rad, alpha: 0..1, present: bool}.
  // present=false if `time` falls outside the track's lifespan.
  sample(timeSec) {
    if (timeSec < this.t0 || timeSec > this.t1) {
      return { present: false };
    }
    const frameF = timeSec * ASSUMED_FPS;
    // Binary-search the bracket. Points are dense (every frame) so linear is fine.
    let lo = 0, hi = this.points.length - 1;
    for (let i = 0; i < this.points.length - 1; i++) {
      if (this.points[i].frame_idx <= frameF && this.points[i + 1].frame_idx >= frameF) {
        lo = i; hi = i + 1; break;
      }
    }
    const a = this.points[lo], b = this.points[hi];
    const denom = (b.frame_idx - a.frame_idx) || 1;
    const t = (frameF - a.frame_idx) / denom;

    const pos = new THREE.Vector3(
      a.xyz[0] * (1 - t) + b.xyz[0] * t,
      a.xyz[1] * (1 - t) + b.xyz[1] * t,
      a.xyz[2] * (1 - t) + b.xyz[2] * t,
    );
    const heading = _lerpAngle(a._heading, b._heading, t);
    const interp = (a.interpolated && b.interpolated) ? 0.4 : 1.0;
    return { present: true, position: pos, heading, alpha: interp };
  }
}

export function buildAnimators(trajectoriesJson) {
  const out = [];
  for (const [tid, info] of Object.entries(trajectoriesJson.tracks || {})) {
    if (!info.points || info.points.length < 2) continue;
    const sorted = [...info.points].sort((a, b) => a.frame_idx - b.frame_idx);
    out.push(new TrajectoryAnimator(tid, info.class_name || "car", sorted));
  }
  return out;
}

// ---- angle helpers ----------------------------------------------------------

function _wrap(a) {
  // Wrap into (-π, π].
  a = (a + Math.PI) % (2 * Math.PI);
  if (a < 0) a += 2 * Math.PI;
  return a - Math.PI;
}

function _emaAngle(prev, next, alpha) {
  // EMA on unit-vector representation, so we cross the ±π seam cleanly.
  const x = (1 - alpha) * Math.cos(prev) + alpha * Math.cos(next);
  const y = (1 - alpha) * Math.sin(prev) + alpha * Math.sin(next);
  return Math.atan2(y, x);
}

function _lerpAngle(a, b, t) {
  const diff = _wrap(b - a);
  return _wrap(a + diff * t);
}
