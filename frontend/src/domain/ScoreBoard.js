import { FACTOR_NAMES } from './constants';
import { level5 } from './levels';
import { RiskEngine, RAW_TO_SCORE } from './RiskEngine';
import { ActionResolver } from './ActionResolver';
import { arr, clamp, sum } from './utils';

/**
 * Everything the UI needs to display risk, computed once per render.
 * Uses agent scores where the agent has answered, baseline heuristics otherwise.
 *
 * `assessment` (agent result) shape:
 *   { summary, rooms: [{ id, pre, surf, rationale, fixes: [{ title, why, action }] }],
 *     factors: [{ name, pre: {avg,min,max}, surf: {avg,min,max} }],
 *     moves: [{ item_id, from_id, to_id, reason, points }] }
 */
export class ScoreBoard {
  constructor({ layout, mission, library, assessment = null }) {
    this.layout = layout;
    this.mission = mission;
    this.library = library;
    this.assessment = assessment;
    this.engine = new RiskEngine(library, mission);
    this.resolver = new ActionResolver(layout, library);
    this._memo = new Map();

    this._scores = {};
    this._agentRooms = {};
    for (const r of layout.rooms) this._scores[r.id] = this.engine.roomScores(r);

    for (const ar of arr(assessment?.rooms)) {
      const r = layout.find(ar.id);
      if (!r) continue;
      this._agentRooms[r.id] = ar;
      const pre = clamp(ar.pre);
      const surf = clamp(ar.surf);
      if (r.isStocked && pre != null && surf != null) this._scores[r.id] = { pre, surf, overall: Math.max(pre, surf) };
    }

    this.ship = RiskEngine.summarise(layout, this._scores);
  }

  _cached(key, fn) {
    if (!this._memo.has(key)) this._memo.set(key, fn());
    return this._memo.get(key);
  }

  stats(room) {
    return this.engine.stats(room);
  }
  scores(room) {
    return this._scores[room.id];
  }
  agentRoom(room) {
    return this._agentRooms[room.id] || null;
  }

  /** Stocked rooms, highest overall score first. */
  get ranked() {
    return this._cached('ranked', () => [...this.layout.stocked].sort((a, b) => this.scores(b).overall - this.scores(a).overall));
  }

  get sentence() {
    if (this.assessment?.summary) return this.assessment.summary;
    const s = this.ship;
    if (!s.stocked) return 'Stock a room to see a score.';
    const surfDrives = s.driver === 'surf';
    return `The overall score is the worse of the two phases. ${surfDrives ? 'Surface' : 'Cruise'} drives it at ${s.overall}; ${surfDrives ? 'cruise' : 'surface'} scores ${surfDrives ? s.pre : s.surf}.`;
  }

  why(room) {
    const ar = this.agentRoom(room);
    if (ar?.rationale) return ar.rationale;
    const sc = this.scores(room);
    return this.engine.drivers(room, sc.surf >= sc.pre ? 'surf' : 'pre').slice(0, 2).join(' · ') || 'No major drivers';
  }

  topSpaces(n = 3) {
    return this.ranked.slice(0, n).map((room) => ({ room, score: this.scores(room).overall, why: this.why(room) }));
  }

  counts() {
    const rooms = this.layout.rooms;
    const st = (r) => this.stats(r);
    const total = (k) => sum(rooms.map((r) => st(r)[k]));
    const missDet = rooms.filter((r) => (st(r).fuel || st(r).ign) && !st(r).det).length;
    const missExt = rooms.filter((r) => st(r).fuel && !st(r).ext).length;
    return [
      { label: 'Spaces', value: rooms.length },
      { label: 'Items stowed', value: total('n') },
      { label: 'Ignition sources', value: total('ign') },
      { label: 'Oxygen sources', value: total('oxy') },
      { label: 'Detectors missing', value: missDet, alert: missDet > 0 },
      { label: 'Extinguishers missing', value: missExt, alert: missExt > 0 },
    ];
  }

  /** Fixes for one room. `action` is null when it can't be applied in one click. */
  suggestions(room) {
    const ar = this.agentRoom(room);
    const list = ar && Array.isArray(ar.fixes) ? ar.fixes : this.engine.suggestions(room);
    return list.map((fx) => ({
      title: fx.title,
      why: fx.why,
      action: fx.action && this.resolver.describe(fx.action) ? fx.action : null,
    }));
  }

  factorRows(phase, selectedRoom = null) {
    const stocked = this.layout.stocked;
    const perRoom = stocked.map((r) => this.engine.factors(r, phase, this.layout));
    const selF = selectedRoom?.isStocked ? this.engine.factors(selectedRoom, phase, this.layout) : null;
    const agentF = arr(this.assessment?.factors).length ? this.assessment.factors : null;

    return FACTOR_NAMES.map((label, k) => {
      const af = agentF && (agentF.find((x) => x && x.name === label) || agentF[k]);
      const ph = af && af[phase];
      let avg, min, max;
      if (ph && clamp(ph.avg) != null) {
        avg = clamp(ph.avg);
        min = Math.min(clamp(ph.min) ?? avg, avg);
        max = Math.max(clamp(ph.max) ?? avg, avg);
      } else {
        const vals = perRoom.map((f) => f[k]);
        avg = vals.length ? Math.round(sum(vals) / vals.length) : 0;
        min = vals.length ? Math.min(...vals) : 0;
        max = vals.length ? Math.max(...vals) : 0;
      }
      return { label, avg, min, max, color: level5(avg).color, selected: selF && !agentF ? selF[k] : null };
    });
  }

  moves() {
    return this._cached('moves', () => {
      if (this.assessment) {
        return arr(this.assessment.moves)
          .map((m) => {
            const action = { type: 'move', item_id: m.item_id, from_id: m.from_id, to_id: m.to_id };
            if (!this.resolver.describe(action)) return null;
            const from = this.layout.find(m.from_id);
            const to = this.layout.find(m.to_id);
            const item = from.findItem(m.item_id);
            return {
              key: `${m.item_id}-${m.to_id}`,
              item: `${this.library.name(item.lib)} ×${item.qty}`,
              from: from.name,
              to: to.name,
              delta: m.points ? `−${Math.abs(Math.round(m.points))} pts` : '',
              reason: m.reason || '',
              action,
            };
          })
          .filter(Boolean);
      }
      return this.engine.findMoves(this.layout).map((m) => ({
        key: `${m.item.id}-${m.to.id}`,
        item: `${m.material.name} ×${m.item.qty}`,
        from: m.from.name,
        to: m.to.name,
        delta: `−${m.points * RAW_TO_SCORE} pts`,
        reason: 'Baseline heuristic',
        action: { type: 'move', item_id: m.item.id, from_id: m.from.id, to_id: m.to.id },
      }));
    });
  }

  tableRows() {
    const rows = [...this.ranked, ...this.layout.rooms.filter((r) => !r.isStocked)];
    return rows.map((room) => {
      const sc = this.scores(room);
      const ar = this.agentRoom(room);
      const fix = (ar && arr(ar.fixes)[0]) || this.engine.suggestions(room)[0];
      return {
        room,
        items: this.stats(room).n,
        ...sc,
        fix: fix ? fix.title : '—',
        why: (ar && room.isStocked && ar.rationale) || '',
      };
    });
  }
}
