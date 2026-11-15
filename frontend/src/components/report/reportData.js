/** Data helpers for the handoff report: manifest rows and the CSV download. */

const FLAM = { 1: 'Low', 2: 'Moderate', 3: 'High' };

/** What kind of item it is, and where its hazard rating comes from. */
function itemFacts(m, backendItem) {
  if (!m) return { kind: 'Unknown', hazard: '—', evidence: '—' };
  if (m.oxy) return { kind: 'Oxygen source', hazard: '—', evidence: '—' };
  if (m.ign) return { kind: 'Ignition source', hazard: '—', evidence: '—' };
  if (m.cat === 'safety') return { kind: 'Safety', hazard: '—', evidence: '—' };
  const tested = backendItem && backendItem.evidence !== 'none' && backendItem.n_tests > 0;
  return {
    kind: 'Material',
    hazard: FLAM[m.flam] || '—',
    evidence: tested ? `NASA test data (${backendItem.n_tests} tests)` : 'Team estimate (no NASA test data)',
  };
}

/** Rows for the manifest table and the CSV download. */
export function manifestRows(planner) {
  const { layout, library, board } = planner;
  const rows = [];
  for (const room of layout.modules) {
    const backendItems = Object.fromEntries((board.agentRoom(room)?.items || []).map((i) => [i.id, i]));
    for (const it of room.items) {
      const m = library.get(it.lib);
      const f = itemFacts(m, backendItems[it.id]);
      rows.push({ space: room.name, item: m?.name || it.lib, qty: it.qty, size: `${it.l} × ${it.w} × ${it.h}`, ...f });
    }
  }
  return rows;
}

export function downloadManifestCsv(planner) {
  const head = ['Space', 'Item', 'Qty', 'Size (L × W × H cm)', 'Type', 'Flammability', 'Hazard basis'];
  const esc = (v) => `"${String(v).replace(/"/g, '""')}"`;
  const lines = [head, ...manifestRows(planner).map((r) => [r.space, r.item, r.qty, r.size, r.kind, r.hazard, r.evidence])];
  const blob = new Blob([lines.map((l) => l.map(esc).join(',')).join('\n')], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `sparkshield-manifest-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}
