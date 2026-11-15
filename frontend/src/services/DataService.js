import { MOCK_LAYOUTS, MOCK_MATERIALS } from '../data/mockData';
import { API_BASE } from './config';

/**
 * Base class: the contract for where planner data comes from.
 * Components never fetch directly — they go through one of these.
 */
export class DataService {
  /** @returns {Promise<Array>} material library entries (see MaterialLibrary for shape) */
  async getMaterials() {
    throw new Error('getMaterials() not implemented');
  }

  /** @returns {Promise<Array>} rooms: [{ id?, name, type, x, y, airflow?, items: [{ id?, lib, qty, l, w, h }] }] */
  async getLayout(key) { // eslint-disable-line no-unused-vars
    throw new Error('getLayout() not implemented');
  }

  /** Optional: persist the current layout. */
  async saveLayout(key, rooms) { // eslint-disable-line no-unused-vars
    return null;
  }
}

/** Serves the hard-coded mock data. Used until the backend is ready. */
export class MockDataService extends DataService {
  async getMaterials() {
    return MOCK_MATERIALS;
  }
  async getLayout(key) {
    return (MOCK_LAYOUTS[key] || MOCK_LAYOUTS.iss)();
  }
}

/**
 * Item library from the FastAPI backend (GET /library), converted to the
 * MaterialLibrary shape. Layouts are still the starter layouts in mockData.js
 * (the backend doesn't store layouts yet). If the backend is down, the mock
 * library is used so the editor still works.
 */
const FLAM = { Low: 1, Moderate: 2, High: 3 };

export class ApiDataService extends MockDataService {
  constructor(baseUrl = API_BASE) {
    super();
    this.baseUrl = baseUrl;
  }

  static toLibraryEntry(x) {
    const m = { key: x.key, name: x.name, cat: x.category };
    if (x.flammability) m.flam = FLAM[x.flammability];
    if (x.soft_goods) m.soft = true;
    if (x.swap) m.swap = x.swap;
    if (x.ignition_source) m.ign = true;
    if (x.oxygen_source) m.oxy = true;
    if (x.heat != null) m.heat = x.heat;
    if (x.li_ion) m.liion = true;
    if (x.bagged) m.bagged = true;
    if (x.test_dataset) m.ds = { ...x.test_dataset };
    return m;
  }

  async getMaterials() {
    try {
      const res = await fetch(`${this.baseUrl}/library`);
      if (!res.ok) throw new Error(`GET /library failed: ${res.status}`);
      return (await res.json()).map(ApiDataService.toLibraryEntry);
    } catch (e) {
      console.warn('[DataService] using the mock item library:', e.message || e);
      return super.getMaterials();
    }
  }
}
