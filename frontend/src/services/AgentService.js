import { FLAMMABILITY } from '../domain/constants';
import { arr } from '../domain/utils';
import { API_BASE } from './config';

/**
 * Talks to the FastAPI backend's stowage planner:
 *   POST /api/assess  -> scores, fixes and moves (computed by code from NASA test data;
 *                        the AI only writes the summary and explanations)
 *   POST /api/chat    -> one chat turn about a results tab
 *
 * The frontend never scores anything itself and never talks to the AI directly.
 * Backend phase names are "cruise"/"surf"; this file converts them to the
 * frontend's "pre"/"surf" so the components don't change.
 */
export class AgentService {
  constructor({ baseUrl = API_BASE } = {}) {
    this.baseUrl = baseUrl;
  }

  async _post(path, body) {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = new Error(`${path} failed: ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return res.json();
  }

  /** The request body for /api/assess (the handoff's agent input, plus each item's library key). */
  static buildInput(layout, mission, library) {
    const A = mission.atmosphere;
    const B = mission.destination;
    return {
      conditions: {
        cruise: { gravity_g: 0, pressure_psia: 14.7, o2_percent: 21, ventilation: mission.preVent, cruise_days: mission.pad },
        surface: { body: B.body, gravity_g: B.g, pressure_psia: A.p, o2_percent: A.o2, stay_days: mission.stay, eva_prep_periods_high_o2: mission.eva },
      },
      out_of_scope: ['launch'],
      spaces: layout.rooms.map((r) => ({
        id: r.id,
        name: r.name,
        type: r.info.name,
        passage: r.isPassage,
        airflow_cm_s: r.airflow,
        capacity_kg: r.capacity,
        neighbours: layout.neighboursOf(r).map((o) => o.id),
        items: r.items.map((i) => {
          const m = library.get(i.lib) || {};
          const o = {
            id: i.id,
            key: i.lib,
            name: m.name || i.lib,
            category: m.cat || 'material',
            flammability: m.flam ? FLAMMABILITY[m.flam] : null,
            ignition_source: !!m.ign,
            oxygen_source: !!m.oxy,
            qty: i.qty,
            cm: [i.l, i.w, i.h],
          };
          if (m.liion) o.bagged = !!m.bagged;
          if (m.liion && !m.bagged) o.swap_to = 'liionbag';
          else if (m.swap) o.swap_to = m.swap;
          return o;
        }),
      })),
    };
  }

  /** Converts the /api/assess response to the shape ScoreBoard reads ("pre" = cruise). */
  static normalise(j) {
    const ph = j.phases || {};
    const phase = (p) => (p ? { avg: p.avg, min: p.min, max: p.max } : null);
    return {
      summary: j.overall?.summary || '',
      ship: {
        pre: ph.cruise?.score ?? null,
        surf: ph.surf?.score ?? null,
        overall: j.overall?.score ?? null,
        driver: j.overall?.driver === 'cruise' ? 'pre' : 'surf',
      },
      rooms: arr(j.rooms).map((r) => ({
        id: r.id,
        stocked: r.stocked,
        pre: r.cruise,
        surf: r.surf,
        overall: r.overall,
        rationale: r.rationale || '',
        fixes: arr(r.fixes).map((f) => ({ title: f.title, why: f.why, points: f.points, action: f.action || null })),
        factors: { pre: r.factors?.cruise || {}, surf: r.factors?.surf || {} },
        items: arr(r.items),
      })),
      factors: arr(j.factors).map((f) => ({ key: f.key, name: f.name, pre: phase(f.cruise), surf: phase(f.surf) })),
      moves: arr(j.moves),
      dataGaps: arr(j.data_gaps),
      textSource: j.text_source,
      inputHash: j.input_hash,
      disclaimer: j.disclaimer || '',
    };
  }

  /** Full-ship assessment. */
  async assess(input) {
    return AgentService.normalise(await this._post('/api/assess', input));
  }

  /** Chat about one results tab. Returns { text, actions, citations }. 503 = agent unreachable (throws). */
  async chat({ tab, thread, input }) {
    const j = await this._post('/api/chat', {
      tab,
      messages: thread.map((m) => ({ role: m.role === 'user' ? 'user' : 'agent', text: m.text, actions: arr(m.actions) })),
      assessment_input: input,
    });
    return { text: j.reply, actions: arr(j.actions), citations: arr(j.citations) };
  }
}

/** No backend: every call fails, so the UI shows "Backend unreachable". */
export class MockAgentService extends AgentService {
  async _post() {
    throw new Error('Backend not connected (VITE_USE_MOCK_AGENT=true)');
  }
}
