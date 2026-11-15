import { useEffect, useMemo, useRef, useState } from 'react';
import { ActionResolver, MaterialLibrary, Mission, ScoreBoard, ShipLayout, CHAT_TABS } from '../domain';
import { AgentService } from '../services/AgentService';
import { agentService, dataService } from '../services';

const ASSESS_DEBOUNCE_MS = 1800;
const emptyForm = (lib = 'cotton') => ({ lib, qty: 1, l: '', w: '', h: '' });

/**
 * Single source of truth for the planner. Holds domain objects in state and
 * exposes `actions` for components. Components stay presentational.
 */
export function usePlanner({ initialLayout = 'iss', cardDetail = 'Full', riskColouring = true } = {}) {
  // ---- domain state ------------------------------------------------------
  const [library, setLibrary] = useState(() => new MaterialLibrary());
  const [layout, setLayout] = useState(() => new ShipLayout());
  const [layoutKey, setLayoutKey] = useState(initialLayout);
  const [mission, setMission] = useState(() => new Mission());

  // ---- UI state ----------------------------------------------------------
  const [ui, setUi] = useState({
    sel: null,
    mode: 'eng', // 'eng' | 'crew'
    tab: 'overall',
    factorPhase: 'surf',
    dragId: null,
    colouring: riskColouring,
    detail: cardDetail === 'Full',
    missionOpen: false,
    report: false, // handoff report overlay
    reportBy: '',
    overviewOpen: false, // open, it covers the right-hand modules; the header still shows the score
  });
  const [form, setForm] = useState(emptyForm());
  const [newMat, setNewMat] = useState(null);
  const [agent, setAgent] = useState({ status: 'idle' });
  const [chat, setChat] = useState({ threads: {}, draft: '', busy: null });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const patchUi = (patch) => setUi((u) => ({ ...u, ...patch }));

  // ---- initial load ------------------------------------------------------
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [materials, rooms] = await Promise.all([dataService.getMaterials(), dataService.getLayout(initialLayout)]);
        if (!alive) return;
        setLibrary((l) => l.withBase(materials));
        setLayout(ShipLayout.fromJSON(rooms));
        setForm(emptyForm(materials[0]?.key));
      } catch (e) {
        if (alive) setLoadError(String(e.message || e));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [initialLayout]);

  // ---- derived -----------------------------------------------------------
  const board = useMemo(() => new ScoreBoard({ layout, mission, library, assessment: agent.result }), [layout, mission, library, agent.result]);
  const reqKey = useMemo(() => layout.fingerprint() + mission.fingerprint(), [layout, mission]);
  const selectedRoom = layout.find(ui.sel);
  const locked = ui.mode === 'crew';

  // ---- agent assessment (debounced) -------------------------------------
  const latest = useRef({ layout, mission, library, reqKey });
  latest.current = { layout, mission, library, reqKey };
  const seq = useRef(0);
  const firstRun = useRef(true);

  async function assess() {
    const my = ++seq.current;
    const { layout: L, mission: M, library: lib, reqKey: key } = latest.current;
    setAgent((a) => ({ ...a, status: 'running' }));
    try {
      const result = await agentService.assess(AgentService.buildInput(L, M, lib));
      if (my !== seq.current) return;
      setAgent({ status: 'done', key, at: new Date(), result });
    } catch (e) {
      if (my !== seq.current) return;
      setAgent((a) => ({ ...a, status: 'error', error: String(e.message || e) }));
    }
  }

  useEffect(() => {
    if (loading) return;
    const delay = firstRun.current ? 0 : ASSESS_DEBOUNCE_MS;
    firstRun.current = false;
    const t = setTimeout(assess, delay);
    return () => clearTimeout(t);
  }, [reqKey, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => void seq.current++, []); // ignore in-flight results after unmount

  // ---- chat --------------------------------------------------------------
  async function sendChat(text) {
    const tab = CHAT_TABS[ui.tab] ? ui.tab : 'overall';
    text = (text || '').trim();
    if (!text || chat.busy) return;
    const thread = [...(chat.threads[tab] || []), { role: 'user', text }];
    setChat((c) => ({ ...c, threads: { ...c.threads, [tab]: thread }, draft: '', busy: tab }));
    const push = (m) => setChat((c) => ({ ...c, threads: { ...c.threads, [tab]: [...(c.threads[tab] || []), m] }, busy: null }));
    try {
      const input = AgentService.buildInput(layout, mission, library);
      const reply = await agentService.chat({ tab, thread, input });
      push({ role: 'agent', text: reply.text, actions: reply.actions, citations: reply.citations });
    } catch {
      // 503 = the AI is unreachable; anything else = the backend is down
      push({ role: 'agent', text: 'The agent could not be reached. Try again in a moment.', actions: [] });
    }
  }

  // ---- actions -----------------------------------------------------------
  const actions = {
    // UI
    setMode: (mode) => patchUi({ mode }),
    select: (id) => patchUi({ sel: id }),
    deselect: () => {
      patchUi({ sel: null });
      setNewMat(null);
    },
    setTab: (tab) => patchUi({ tab }),
    setFactorPhase: (factorPhase) => patchUi({ factorPhase }),
    toggleColouring: () => setUi((u) => ({ ...u, colouring: !u.colouring })),
    toggleMission: () => setUi((u) => ({ ...u, missionOpen: !u.missionOpen })),
    openReport: () => patchUi({ report: true, missionOpen: false }),
    closeReport: () => patchUi({ report: false }),
    setReportBy: (reportBy) => patchUi({ reportBy }),
    toggleOverview: () => setUi((u) => ({ ...u, overviewOpen: !u.overviewOpen })),

    // Mission
    setMissionField: (key, value) => setMission((m) => m.with(key, value)),

    // Layout
    async loadLayout(key) {
      const rooms = await dataService.getLayout(key);
      setLayout(ShipLayout.fromJSON(rooms));
      setLayoutKey(key);
      patchUi({ sel: null });
    },
    /** Drop a dragged module on another cell: the two swap places (the hull never grows). */
    swapRooms(id, targetId) {
      setLayout((l) => l.swapRooms(id, targetId));
      patchUi({ dragId: null });
    },
    startDrag: (id) => patchUi({ dragId: id }),
    endDrag: () => patchUi({ dragId: null }),
    updateRoom: (id, fn) => setLayout((l) => l.updateRoom(id, fn)),
    /** Turn a module back into an empty bay (its items are removed). */
    clearRoom(id) {
      setLayout((l) => l.clearRoom(id));
      patchUi({ sel: null });
    },
    removeItem: (roomId, itemId) => setLayout((l) => l.updateRoom(roomId, (r) => r.removeItem(itemId))),
    applyAction: (action) => setLayout((l) => ActionResolver.apply(action, l)),

    // Add-item form
    setFormField: (key, value) => setForm((f) => ({ ...f, [key]: value })),
    addItem(roomId) {
      const f = form;
      if (!(f.qty >= 1 && +f.l > 0 && +f.w > 0 && +f.h > 0)) return;
      setLayout((l) => l.updateRoom(roomId, (r) => r.addItem({ lib: f.lib, qty: +f.qty, l: +f.l, w: +f.w, h: +f.h })));
      setForm((s) => ({ ...s, qty: 1, l: '', w: '', h: '' }));
    },

    // Custom materials
    toggleNewMaterial: () => setNewMat((n) => (n ? null : { name: '', flam: '2' })),
    setNewMaterialField: (key, value) => setNewMat((n) => ({ ...n, [key]: value })),
    saveNewMaterial() {
      if (!newMat || !newMat.name.trim()) return;
      const material = MaterialLibrary.createCustom(newMat.name, newMat.flam);
      setLibrary((l) => l.withCustom(material));
      setNewMat(null);
      setForm((f) => ({ ...f, lib: material.key }));
    },

    // Agent
    reassess: () => assess(),
    setChatDraft: (draft) => setChat((c) => ({ ...c, draft })),
    sendChat,
  };

  return { loading, loadError, library, layout, layoutKey, mission, ui, form, newMat, agent, chat, board, reqKey, selectedRoom, locked, actions };
}
