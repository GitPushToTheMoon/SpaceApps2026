import { COLORS as C } from './constants';

// 3-band level used for module card colouring.
export function level3(score) {
  if (score == null) return { label: 'Empty', color: C.gray, wash: '#ffffff' };
  if (score <= 40) return { label: 'Low', color: C.green, wash: 'oklch(0.975 0.025 150)' };
  if (score <= 60) return { label: 'Elevated', color: C.yellow, wash: 'oklch(0.978 0.045 100)' };
  return { label: 'High', color: C.red, wash: 'oklch(0.968 0.03 27)' };
}

// 5-band level used everywhere else.
export function level5(score) {
  if (score == null) return { label: 'Empty', color: C.gray };
  if (score <= 20) return { label: 'Low', color: C.green };
  if (score <= 40) return { label: 'Guarded', color: C.lgreen };
  if (score <= 60) return { label: 'Elevated', color: C.yellow };
  if (score <= 80) return { label: 'High', color: C.orange };
  return { label: 'Severe', color: C.red };
}

export const SCALE5 = [
  { label: 'Low', color: C.green, lo: 0, hi: 20 },
  { label: 'Guarded', color: C.lgreen, lo: 21, hi: 40 },
  { label: 'Elevated', color: C.yellow, lo: 41, hi: 60 },
  { label: 'High', color: C.orange, lo: 61, hi: 80 },
  { label: 'Severe', color: C.red, lo: 81, hi: 100 },
];

export const MAP_LEGEND = [
  { label: 'Low', color: C.green },
  { label: 'Elevated', color: C.yellow },
  { label: 'High', color: C.red },
];
