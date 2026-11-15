/**
 * Per-room counts and plain-text reasons, for display only (DET/EXT badges,
 * "Hot electronics" tags, the counts grid, fallback reasons).
 *
 * This file does NOT score anything. Every score, level, factor, fix and move
 * comes from the backend (POST /api/assess, backend/scoring.py).
 */
export class RoomStats {
  constructor(library, mission) {
    this.library = library;
    this.mission = mission;
    this._stats = new WeakMap(); // rooms are immutable, so caching by instance is safe
  }

  /** Aggregate counts for one room. */
  stats(room) {
    if (this._stats.has(room)) return this._stats.get(room);
    const s = { fuel: 0, ign: 0, oxy: 0, ext: false, det: false, modHigh: false, high: 0, liion: 0, soft: 0, mats: 0, heat: 0, thin: null, n: 0 };
    for (const item of room.items) {
      const m = this.library.get(item.lib);
      if (!m) continue;
      s.n += item.qty;
      if (m.flam) {
        s.fuel += m.flam * item.sizeFactor;
        s.mats += item.qty;
        if (m.flam >= 2) s.modHigh = true;
        if (m.flam === 3) s.high += item.qty;
        if (m.soft) s.soft += item.qty;
        const d = item.minDimension;
        if (s.thin === null || d < s.thin) s.thin = d;
      }
      if (m.ign) {
        s.ign += item.qty;
        s.heat += (m.heat || 15) * Math.min(item.qty, 3);
      }
      if (m.liion && !m.bagged) s.liion += item.qty;
      if (m.oxy) s.oxy += item.qty;
      if (m.key === 'ext') s.ext = true;
      if (m.key === 'det') s.det = true;
    }
    this._stats.set(room, s);
    return s;
  }

  /** Short reasons a room may be risky; shown only until the backend's rationale arrives. */
  drivers(room, phase) {
    const s = this.stats(room);
    const A = this.mission.atmosphere;
    const d = [];
    if (s.oxy && s.modHigh) d.push('oxygen outlet next to flammables');
    if (s.fuel && s.ign) d.push(`${s.ign} ignition source${s.ign > 1 ? 's' : ''} beside flammables`);
    if (s.high) d.push(`${s.high} high-flammability item${s.high > 1 ? 's' : ''}`);
    if (phase !== 'pre' && A.o2 > 21 && s.fuel) d.push(`${A.o2}% O₂ cabin`);
    if (room.isPassage && s.mats) d.push('cargo in a passage');
    if (room.airflow < 5 && s.fuel) d.push(`low airflow (${room.airflow} cm/s)`);
    if (s.fuel && !s.det) d.push('no smoke detector');
    return d;
  }
}
