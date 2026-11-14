import { MOCK_LAYOUTS, MOCK_MATERIALS } from '../data/mockData';

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
 * Talks to the FastAPI backend. Endpoints (adjust to match your routes):
 *   GET  /api/materials          -> [material, ...]
 *   GET  /api/layouts/{key}      -> [room, ...]
 *   PUT  /api/layouts/{key}      <- [room, ...]
 */
export class ApiDataService extends DataService {
  constructor(baseUrl = '/api') {
    super();
    this.baseUrl = baseUrl;
  }

  async _request(path, options = {}) {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!res.ok) throw new Error(`${options.method || 'GET'} ${path} failed: ${res.status}`);
    return res.json();
  }

  getMaterials() {
    return this._request('/materials');
  }
  getLayout(key) {
    return this._request(`/layouts/${encodeURIComponent(key)}`);
  }
  saveLayout(key, rooms) {
    return this._request(`/layouts/${encodeURIComponent(key)}`, { method: 'PUT', body: JSON.stringify(rooms) });
  }
}
