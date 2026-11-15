import { COLORS as C } from './constants';

// One 5-band scale everywhere (map cards, panels, tables), matching the backend's levels.
// `wash` is the module card background when risk colouring is on.
export function level5(score) {
  if (score == null) return { label: 'Empty', color: C.gray, wash: '#ffffff' };
  if (score <= 20) return { label: 'Low', color: C.green, wash: 'oklch(0.975 0.025 150)' };
  if (score <= 40) return { label: 'Guarded', color: C.lgreen, wash: 'oklch(0.975 0.035 130)' };
  if (score <= 60) return { label: 'Elevated', color: C.yellow, wash: 'oklch(0.978 0.045 100)' };
  if (score <= 80) return { label: 'High', color: C.orange, wash: 'oklch(0.972 0.035 55)' };
  return { label: 'Severe', color: C.red, wash: 'oklch(0.965 0.035 27)' };
}

export const SCALE5 = [
  { label: 'Low', color: C.green, lo: 0, hi: 20 },
  { label: 'Guarded', color: C.lgreen, lo: 21, hi: 40 },
  { label: 'Elevated', color: C.yellow, lo: 41, hi: 60 },
  { label: 'High', color: C.orange, lo: 61, hi: 80 },
  { label: 'Severe', color: C.red, lo: 81, hi: 100 },
];

export const MAP_LEGEND = SCALE5.map(({ label, color }) => ({ label, color }));
