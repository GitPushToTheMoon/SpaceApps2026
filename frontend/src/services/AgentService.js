import { CHAT_TABS, FLAMMABILITY } from '../domain/constants';
import { RiskEngine } from '../domain/RiskEngine';
import { arr, parseJSON } from '../domain/utils';
import { ASSESS_SYSTEM_PROMPT, chatSystemPrompt } from './agentPrompts';

/**
 * Talks to the LLM through your backend.
 * Expects:  POST /api/agent/complete  { system, messages, max_tokens }  ->  { text }
 */
export class AgentService {
  constructor({ endpoint = '/api/agent/complete' } = {}) {
    this.endpoint = endpoint;
  }

  async complete({ system, messages, maxTokens = 1000 }) {
    const res = await fetch(this.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ system, messages, max_tokens: maxTokens }),
    });
    if (!res.ok) throw new Error(`Agent request failed: ${res.status}`);
    const data = await res.json();
    return data.text ?? '';
  }

  /** The JSON the agent sees: conditions + every space with its items and baseline. */
  static buildInput(layout, mission, library) {
    const engine = new RiskEngine(library, mission);
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
        baseline: { cruise: engine.score(r, 'pre'), surf: engine.score(r, 'surf') },
        items: r.items.map((i) => {
          const m = library.get(i.lib) || {};
          const o = {
            id: i.id,
            name: m.name,
            category: m.cat,
            flammability: m.flam ? FLAMMABILITY[m.flam] : null,
            ignition_source: !!m.ign,
            oxygen_source: !!m.oxy,
            qty: i.qty,
            cm: [i.l, i.w, i.h],
          };
          if (m.liion) o.bagged = !!m.bagged;
          if (m.liion && !m.bagged) o.swap_to = 'liionbag';
          else if (m.swap) o.swap_to = m.swap;
          if (m.ds) o.test_dataset = { state: m.ds.state, tests: m.ds.tests };
          return o;
        }),
      })),
    };
  }

  /** Full-ship assessment. Returns { summary, rooms, factors, moves }. */
  async assess(input) {
    const text = await this.complete({
      system: ASSESS_SYSTEM_PROMPT,
      messages: [{ role: 'user', content: JSON.stringify(input) }],
      maxTokens: 4000,
    });
    const j = parseJSON(text);
    if (!j || !Array.isArray(j.rooms)) throw new Error('Unreadable response');
    return { summary: j.overall?.summary || '', rooms: arr(j.rooms), factors: arr(j.factors), moves: arr(j.moves) };
  }

  /** Chat about one results tab. Returns { text, actions }. */
  async chat({ tab, thread, input, assessment }) {
    const system = chatSystemPrompt(CHAT_TABS[tab].name, input, assessment);
    const messages = thread.map((m) => ({
      role: m.role === 'user' ? 'user' : 'assistant',
      content: m.role === 'user' ? m.text : JSON.stringify({ reply: m.text, actions: m.actions || [] }),
    }));
    const text = await this.complete({ system, messages, maxTokens: 1000 });
    const j = parseJSON(text);
    return { text: j?.reply || text, actions: j ? arr(j.actions) : [] };
  }
}

/** No backend yet: every call fails, so the UI shows the baseline heuristics. */
export class MockAgentService extends AgentService {
  async complete() {
    throw new Error('Agent not connected yet');
  }
}
