import { FLAMMABILITY } from './constants';
import { newId } from './utils';

/**
 * Lookup of everything that can be stowed: materials, machinery, safety gear.
 * `base` comes from the DataService (later: your DB); `custom` are user-added materials.
 *
 * Library entry shape:
 *   { key, name, cat: 'material'|'machinery'|'safety',
 *     flam?: 1|2|3, soft?, swap?: key, ign?, heat?, liion?, bagged?, oxy?,
 *     ds?: { plain, state, tests }   // PSI test-dataset metadata
 *     saved? }                        // user-created
 */
export class MaterialLibrary {
  constructor(base = [], custom = []) {
    this.base = base;
    this.custom = custom;
    this._map = new Map([...base, ...custom].map((m) => [m.key, m]));
  }

  get(key) {
    return this._map.get(key);
  }
  name(key) {
    return this.get(key)?.name ?? key;
  }
  get firstKey() {
    return this.base[0]?.key ?? '';
  }

  withBase(base) {
    return new MaterialLibrary(base, this.custom);
  }
  withCustom(material) {
    return new MaterialLibrary(this.base, [...this.custom, material]);
  }

  static createCustom(name, flam) {
    return { key: newId('c'), name: name.trim(), cat: 'material', flam: +flam, saved: true };
  }

  /** Grouped options for the "Add to this space" <select>. */
  groups() {
    const b = this.base;
    const groups = [
      {
        label: 'Materials (no NASA tests: score is an estimate)',
        options: b
          .filter((l) => l.cat === 'material' && !(l.ds && l.ds.tests > 0))
          .map((l) => ({
            key: l.key,
            label: l.ds ? `${l.name} — ${l.ds.plain} · ${FLAMMABILITY[l.flam]} · PSI material, no tests yet` : `${l.name} · ${FLAMMABILITY[l.flam]}`,
          })),
      },
      {
        label: 'NASA test data (PSI)',
        options: b
          .filter((l) => l.ds && l.ds.tests > 0)
          .map((l) => ({
            key: l.key,
            label: `${l.name} — ${l.ds.plain} · ${l.ds.tests} test${l.ds.tests === 1 ? '' : 's'}${l.ds.tests < 5 ? ' (limited)' : ''}`,
          })),
      },
    ];
    if (this.custom.length) {
      groups.push({
        label: 'Saved materials',
        options: this.custom.map((l) => ({ key: l.key, label: `${l.name} · ${FLAMMABILITY[l.flam]} (saved)` })),
      });
    }
    groups.push(
      { label: 'Machinery', options: b.filter((l) => l.cat === 'machinery').map((l) => ({ key: l.key, label: l.name })) },
      { label: 'Safety', options: b.filter((l) => l.cat === 'safety').map((l) => ({ key: l.key, label: l.name })) }
    );
    return groups.filter((g) => g.options.length);
  }
}
