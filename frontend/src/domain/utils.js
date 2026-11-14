let uid = 1;

/** Client-side id generator. Swap for server ids once data is connected. */
export const newId = (prefix = 'n') => `${prefix}${uid++}`;

/** Pull the first {...} block out of an LLM reply and parse it. */
export function parseJSON(text) {
  if (!text) return null;
  const s = text.indexOf('{');
  const e = text.lastIndexOf('}');
  if (s < 0 || e < s) return null;
  try {
    return JSON.parse(text.slice(s, e + 1));
  } catch {
    return null;
  }
}

/** Clamp to an integer 0–100, or null if not a number. */
export const clamp = (v) => (v == null || isNaN(+v) ? null : Math.max(0, Math.min(100, Math.round(+v))));

export const arr = (v) => (Array.isArray(v) ? v : []);

export const sum = (xs) => xs.reduce((a, b) => a + b, 0);
