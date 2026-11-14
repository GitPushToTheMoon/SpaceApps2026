import { CRUISE_ATMOSPHERE, FLAMMABILITY } from './constants';
import { sum } from './utils';

const RAW_TO_SCORE = 7;

/**
 * Baseline (placeholder) fire-risk heuristics. Used when the agent hasn't
 * answered yet, and sent to the agent as an anchor.
 *
 * When your real scoring model lives in the backend, you can either replace
 * these methods or keep them as the offline fallback.
 *
 * Phases: 'pre' = in-space cruise, 'surf' = surface operations.
 */
export class RiskEngine {
  constructor(library, mission) {
    this.library = library;
    this.mission = mission;
    this._stats = new WeakMap(); // rooms are immutable, so caching by instance is safe
  }

  static toScore(raw) {
    return raw == null ? null : Math.min(100, raw * RAW_TO_SCORE);
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

  rawScore(room, phase) {
    if (!room.isStocked) return null;
    const s = this.stats(room);
    const M = this.mission;
    let v =
      s.fuel +
      (s.fuel > 0 ? 2 * s.ign : 0) +
      (s.oxy && s.modHigh ? 4 : 0) +
      (room.isPassage && s.mats ? 2 : 0) -
      (s.ext ? 1 : 0) -
      (s.det ? 1 : 0);

    if (phase === 'pre') {
      v += Math.min(3, Math.ceil(s.soft / 2));
      if (s.fuel > 0 && !s.det) v += 1;
      if (M.preVent === 'reduced' && s.ign && s.fuel) v += 1;
      if (M.pad > 180 && s.fuel >= 5) v += 1;
    } else {
      const A = M.atmosphere;
      if (s.liion) v += 2;
      if (s.ign && s.fuel) v += 1;
      if (M.body === 'mars' && s.fuel) v += 1;
      if (A.o2 >= 30 && s.fuel) v += 2;
      if (M.eva > 0 && s.oxy) v += 1;
      if (M.stay > 30 && s.fuel >= 5) v += 1;
    }
    return Math.max(0, v);
  }

  score(room, phase) {
    return RiskEngine.toScore(this.rawScore(room, phase));
  }

  /** { pre, surf, overall } on 0–100 (null when empty). */
  roomScores(room) {
    const pre = this.score(room, 'pre');
    const surf = this.score(room, 'surf');
    return { pre, surf, overall: pre == null ? null : Math.max(pre, surf) };
  }

  rawMax(room) {
    return Math.max(this.rawScore(room, 'pre') || 0, this.rawScore(room, 'surf') || 0);
  }

  /** The 7 risk factors (0–100 each), in FACTOR_NAMES order. */
  factors(room, phase, layout) {
    const s = this.stats(room);
    const M = this.mission;
    const A = phase === 'pre' ? CRUISE_ATMOSPHERE : M.atmosphere;
    const vent = phase === 'pre' ? M.preVent : 'normal';
    const a = room.airflow;
    const hotNeighbour = layout.neighboursOf(room).some((o) => this.stats(o).ign > 0);
    const f = [
      (s.fuel / 14) * 100 + 5 * s.high,
      10 + (s.oxy ? 15 : 0) + (s.oxy && s.modHigh ? 40 : 0) + (A.o2 >= 30 ? 25 : 0) + (vent === 'reduced' ? 10 : 0),
      A.press,
      a < 5 ? 75 - 8 * a : a <= 15 ? 20 : 20 + 6 * (a - 15),
      !s.mats ? 10 : s.thin == null ? 40 : s.thin < 0.5 ? 85 : s.thin < 2 ? 55 : s.thin < 5 ? 35 : 20,
      s.fuel && s.ign ? 45 + 12 * s.ign : s.fuel && hotNeighbour ? 35 : s.ign ? 20 : 10,
      s.heat + (a < 5 && s.ign ? 10 : 0),
    ];
    return f.map((v) => Math.max(0, Math.min(100, Math.round(v))));
  }

  /** Short human-readable reasons a room scores high. */
  drivers(room, phase) {
    const s = this.stats(room);
    const A = this.mission.atmosphere;
    const d = [];
    if (s.oxy && s.modHigh) d.push('oxygen outlet next to flammables');
    if (s.fuel && s.ign) d.push(`${s.ign} ignition source${s.ign > 1 ? 's' : ''} beside flammables`);
    if (s.high) d.push(`${s.high} high-flammability item${s.high > 1 ? 's' : ''}`);
    if (phase !== 'pre' && A.o2 >= 30 && s.fuel) d.push(`${A.o2}% O₂ cabin`);
    if (phase !== 'pre' && s.liion) d.push('unbagged Li-ion');
    if (room.isPassage && s.mats) d.push('cargo in a passage');
    if (room.airflow < 5 && s.fuel) d.push(`low airflow (${room.airflow} cm/s)`);
    if (s.fuel && !s.det) d.push('no smoke detector');
    return d;
  }

  /** Fix suggestions. `action` uses the same shape the agent returns. */
  suggestions(room) {
    const s = this.stats(room);
    const lib = this.library;
    const out = [];
    for (const i of room.items) {
      const m = lib.get(i.lib);
      if (!m) continue;
      if (m.liion && !m.bagged) {
        out.push({
          title: `Bag the ${m.name}`,
          why: 'Unbagged cells add 2 points on the surface',
          action: { type: 'swap', room_id: room.id, item_id: i.id, to: 'liionbag' },
        });
      } else if (m.flam >= 2 && m.swap && lib.get(m.swap) && (s.ign || s.oxy || room.isPassage)) {
        const near = s.oxy ? 'an oxygen source' : s.ign ? 'ignition sources' : 'a passage';
        out.push({
          title: `Swap ${m.name} for ${lib.name(m.swap)}`,
          why: `${FLAMMABILITY[m.flam]} flammability beside ${near}`,
          action: { type: 'swap', room_id: room.id, item_id: i.id, to: m.swap },
        });
      }
    }
    if (s.fuel > 0 && !s.ext)
      out.push({ title: 'Add a portable extinguisher', why: 'Fuel is stowed with no extinguisher in reach', action: { type: 'add', room_id: room.id, key: 'ext' } });
    if ((s.fuel > 0 || s.ign) && !s.det)
      out.push({ title: 'Add a smoke detector', why: 'No smoke detection in this space', action: { type: 'add', room_id: room.id, key: 'det' } });
    if (s.oxy && s.modHigh)
      out.push({ title: 'Separate the oxygen supply from flammables', why: 'An oxygen outlet beside flammables adds 4 points', action: null });
    if (room.isPassage && s.mats)
      out.push({ title: 'Clear cargo from the passage', why: 'Stowage in a passage adds 2 points and blocks egress', action: null });
    return out;
  }

  /** Up to 5 single-item moves that lower combined raw risk. */
  findMoves(layout) {
    const out = [];
    for (const from of layout.rooms) {
      const sA = this.stats(from);
      if (!(sA.ign || sA.oxy || from.isPassage)) continue;
      const before = this.rawMax(from);
      for (const item of from.items) {
        const m = this.library.get(item.lib);
        if (!m || !m.flam || m.flam < 2) continue;
        const after = this.rawMax(from.removeItem(item.id));
        let best = null;
        for (const to of layout.rooms) {
          if (to.id === from.id || to.isPassage) continue;
          const points = before + this.rawMax(to) - (after + this.rawMax(to.addItem(item)));
          if (points > 0 && (!best || points > best.points)) best = { item, material: m, from, to, points };
        }
        if (best) out.push(best);
      }
    }
    return out.sort((a, b) => b.points - a.points).slice(0, 5);
  }

  /** Ship-level summary from per-room scores: 60% worst room + 40% mean. */
  static summarise(layout, scoresById) {
    const stocked = layout.stocked;
    const phase = (k) => {
      if (!stocked.length) return 0;
      const v = stocked.map((r) => scoresById[r.id][k] || 0);
      return Math.round(0.6 * Math.max(...v) + 0.4 * (sum(v) / v.length));
    };
    const pre = phase('pre');
    const surf = phase('surf');
    return { pre, surf, overall: Math.max(pre, surf), driver: surf >= pre ? 'surf' : 'pre', stocked: stocked.length };
  }
}

export { RAW_TO_SCORE };
