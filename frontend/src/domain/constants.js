// Static reference data and design tokens used across the app.
// These are rules/config, not mission data — mission data comes from the DataService.

export const ROOM_TYPES = {
  STO: { name: 'Stowage', cap: 140, air: 3, hue: 70 },
  ENG: { name: 'Engine room', cap: 80, air: 12, hue: 30 },
  LAB: { name: 'Lab', cap: 70, air: 14, hue: 250 },
  OPS: { name: 'Operations', cap: 60, air: 10, hue: 285 },
  GAL: { name: 'Galley', cap: 60, air: 12, hue: 40 },
  LS: { name: 'Life support', cap: 60, air: 12, hue: 195 },
  CQ: { name: 'Crew quarters', cap: 50, air: 8, hue: 320 },
  PWR: { name: 'Power', cap: 50, air: 8, hue: 100 },
  HYG: { name: 'Hygiene', cap: 45, air: 16, hue: 220 },
  EX: { name: 'Exercise', cap: 45, air: 16, hue: 160 },
  AL: { name: 'Airlock', cap: 40, air: 10, hue: 350 },
  NODE: { name: 'Node (passage)', cap: 30, air: 10, passage: true },
  HALL: { name: 'Hall / tunnel (passage)', cap: 20, air: 10, passage: true },
  OTH: { name: 'Other', cap: 50, air: 8 },
};

export function typeColor(code) {
  const t = ROOM_TYPES[code];
  if (!t) return '#6f737a';
  if (t.hue == null) return t.passage ? '#8b8f96' : '#6f737a';
  return `oklch(0.56 0.1 ${t.hue})`;
}

export const ATMOSPHERES = {
  earth: { name: 'Sea-level', label: '14.7 psia · 21% O₂', p: 14.7, o2: 21, press: 25 },
  base: { name: 'Moon base', label: '10.2 psia · 30% O₂', p: 10.2, o2: 30, press: 55 },
  expl: { name: 'Exploration', label: '8.2 psia · 34% O₂', p: 8.2, o2: 34, press: 70 },
};

export const CRUISE_ATMOSPHERE = ATMOSPHERES.earth;

export const BODIES = {
  moon: { name: 'Lunar surface', body: 'Moon', g: 0.166, gl: '0.166 g · about 1/6 g' },
  mars: { name: 'Martian surface', body: 'Mars', g: 0.38, gl: '0.38 g · about 3/8 g' },
};

export const FLAMMABILITY = { 1: 'Low', 2: 'Moderate', 3: 'High' };

export const COLORS = {
  green: 'oklch(0.64 0.13 150)',
  lgreen: 'oklch(0.78 0.13 130)',
  yellow: 'oklch(0.87 0.15 100)',
  orange: 'oklch(0.73 0.16 55)',
  red: 'oklch(0.6 0.19 27)',
  gray: '#c4c6ca',
  amber: 'oklch(0.79 0.16 72)',
  amberWash: 'oklch(0.965 0.04 82)',
  amberText: 'oklch(0.42 0.1 60)',
  danger: 'oklch(0.5 0.17 27)',
  positive: 'oklch(0.45 0.12 150)',
  ink: '#16181b',
  muted: '#5b5f66',
  faint: '#8b8f96',
  line: '#e3e3df',
  lineSoft: '#ededea',
};

// Default sizes (cm) used when an action adds a safety item.
export const SAFETY_ITEMS = {
  ext: { l: 50, w: 15, h: 15 },
  det: { l: 10, w: 10, h: 5 },
  mask: { l: 25, w: 20, h: 15 },
};

export const PHASES = { pre: 'Cruise', surf: 'Surface' };

export const FACTOR_NAMES = [
  'Materials & fuel load',
  'Oxygen & ventilation',
  'Cabin pressure',
  'Airflow',
  'Material thickness',
  'Proximity to combustible machinery',
  'Machinery heat & temperature',
];

export const LAYOUT_OPTIONS = [
  ['iss', 'ISS-style station'],
  ['transit', 'Transit spacecraft'],
  ['blank', 'Blank hull'],
];

export const CHAT_TABS = {
  overall: {
    name: 'Overall fire risk',
    prompts: ['Why is one phase worse than the other?', 'What single change lowers the score most?', 'Is this layout ready for M&P review?'],
  },
  factors: {
    name: 'Risk factors',
    prompts: ['Which factor matters most for this ship?', 'Explain the oxygen & ventilation factor', 'How does surface gravity change these?'],
  },
  moves: {
    name: 'Suggested moves',
    prompts: ['Find safer spots for the most flammable items', 'Why these moves first?', 'Which moves keep crew access easy?'],
  },
  table: {
    name: 'Space by space',
    prompts: ['Which spaces are fine as they are?', 'Compare the two highest-risk spaces', 'What should I fix first in the riskiest space?'],
  },
};
