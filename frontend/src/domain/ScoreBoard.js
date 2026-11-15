import { FACTOR_NAMES } from './constants';
import { level5 } from './levels';
import { RoomStats } from './RoomStats';
import { ActionResolver } from './ActionResolver';
import { arr, sum } from './utils';

const EMPTY = { pre: null, surf: null, overall: null };

/**
 * Everything the UI needs to display risk, computed once per render.
 *
 * Every score, level, factor, fix and move comes from the backend (POST /api/assess,
 * already converted by AgentService.normalise). The frontend never scores rooms itself,
 * so the screen can't disagree with the backend. RoomStats is only used for counts
 * (items, ignition sources, missing detectors…) and plain-text drivers.
 *
 * `assessment` shape (AgentService.normalise):
 *   { summary, ship: { pre, surf, overall, driver },
 *     rooms: [{ id, pre, surf, overall, rationale, fixes: [{ title, why, points, action }], factors: { pre, surf } }],
 *     factors: [{ key, name, pre: {avg,min,max}, surf: {avg,min,max} }],
 *     moves: [{ item_id, item, qty, from_id, from_name, to_id, to_name, reason, points }],
 *     dataGaps, textSource, inputHash }
 */
export class ScoreBoard {
  constructor({ layout, mission, library, assessment = null }) {
    this.layout = layout;
    this.mission = mission;
    this.library = library;
    this.assessment = assessment;
    this.engine = new RoomStats(library, mission);
    this.resolver = new ActionResolver(layout, library);
    this._memo = new Map();

    this._agentRooms = {};
    for (const ar of arr(assessment?.rooms)) {
      if (layout.find(ar.id)) this._agentRooms[ar.id] = ar;
    }

    const s = assessment?.ship;
    this.ship = {
      pre: s?.pre ?? null,
      surf: s?.surf ?? null,
      overall: s?.overall ?? null,
      driver: s?.driver ?? null,
      stocked: layout.stocked.length,
    };
  }

  _cached(key, fn) {
    if (!this._memo.has(key)) this._memo.set(key, fn());
    return this._memo.get(key);
  }

  stats(room) {
    return this.engine.stats(room);
  }
  /** { pre, surf, overall } from the backend; nulls until the room has been assessed. */
  scores(room) {
    const ar = this._agentRooms[room.id];
    return ar ? { pre: ar.pre, surf: ar.surf, overall: ar.overall } : EMPTY;
  }
  agentRoom(room) {
    return this._agentRooms[room.id] || null;
  }

  /** Assessed rooms, highest overall score first. */
  get ranked() {
    return this._cached('ranked', () =>
      this.layout.stocked.filter((r) => this.scores(r).overall != null).sort((a, b) => this.scores(b).overall - this.scores(a).overall)
    );
  }

  get sentence() {
    if (this.assessment?.summary) return this.assessment.summary;
    if (!this.ship.stocked) return 'Stock a room to see a score.';
    return 'Waiting for the first assessment from the backend.';
  }

  why(room) {
    const ar = this.agentRoom(room);
    if (ar?.rationale) return ar.rationale;
    const sc = this.scores(room);
    return this.engine.drivers(room, (sc.surf ?? 0) >= (sc.pre ?? 0) ? 'surf' : 'pre').slice(0, 2).join(' · ') || 'No major drivers';
  }

  topSpaces(n = 3) {
    return this.ranked.slice(0, n).map((room) => ({ room, score: this.scores(room).overall, why: this.why(room) }));
  }

  counts() {
    const rooms = this.layout.modules;
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

  /** Fixes for one room from the backend (with real points). `action` is null if it no longer applies. */
  suggestions(room) {
    const ar = this.agentRoom(room);
    return arr(ar?.fixes).map((fx) => ({
      title: fx.title,
      why: fx.points ? `${fx.why} · −${fx.points} pts` : fx.why,
      action: fx.action && this.resolver.describe(fx.action) ? fx.action : null,
    }));
  }

  /** Factor bars for one phase ("pre" or "surf"): the backend's 5 factors. */
  factorRows(phase, selectedRoom = null) {
    const list = arr(this.assessment?.factors);
    const sel = selectedRoom ? this.agentRoom(selectedRoom)?.factors?.[phase] : null;
    if (!list.length) {
      return FACTOR_NAMES.map((label) => ({ label, avg: 0, min: 0, max: 0, color: level5(0).color, selected: null }));
    }
    return list.map((f) => {
      const b = f[phase] || { avg: 0, min: 0, max: 0 };
      const avg = Math.round(b.avg);
      return {
        label: f.name,
        avg,
        min: Math.min(b.min, avg),
        max: Math.max(b.max, avg),
        color: level5(avg).color,
        selected: sel && sel[f.key] != null ? sel[f.key] : null,
      };
    });
  }

  moves() {
    return this._cached('moves', () =>
      arr(this.assessment?.moves)
        .map((m) => {
          const action = { type: 'move', item_id: m.item_id, from_id: m.from_id, to_id: m.to_id };
          if (!this.resolver.describe(action)) return null; // the layout changed since the assessment
          return {
            key: `${m.item_id}-${m.to_id}`,
            item: `${m.item} ×${m.qty}`,
            from: m.from_name,
            to: m.to_name,
            delta: m.points ? `−${m.points} pts` : '',
            reason: m.reason || '',
            action,
            raw: m, // backend move, incl. before/after scores for the crew instruction
          };
        })
        .filter(Boolean)
    );
  }

  tableRows() {
    const rows = [...this.ranked, ...this.layout.modules.filter((r) => !this.ranked.includes(r))];
    return rows.map((room) => {
      const sc = this.scores(room);
      const ar = this.agentRoom(room);
      const fix = arr(ar?.fixes)[0];
      return {
        room,
        items: this.stats(room).n,
        ...sc,
        fix: fix ? fix.title : '—',
        why: (ar && ar.rationale) || '',
      };
    });
  }
}
