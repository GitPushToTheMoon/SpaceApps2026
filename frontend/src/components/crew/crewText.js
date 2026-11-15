const fmt = (n) => (n == null ? '—' : Number(n).toFixed(1));

/** "Destiny Lab 63.1 → 41.2 · ship 60 → 52.4" from the backend's before/after scores. */
export function effectLine(c) {
  return `${c.from} ${fmt(c.fromBefore)} → ${fmt(c.fromAfter)} · ship ${fmt(c.shipBefore)} → ${fmt(c.shipAfter)}`;
}

/** The newest instruction Bailey still has to do (shown on the map), else null. */
export const openInstruction = (msgs) => [...msgs].reverse().find((m) => m.status === 'sent') || null;
