import { Room } from './Room';

const DIRS = [
  [1, 0],
  [-1, 0],
  [0, 1],
  [0, -1],
];

/**
 * The whole ship: a collection of Rooms on a grid. Immutable.
 */
export class ShipLayout {
  constructor(rooms = []) {
    this.rooms = rooms.map((r) => (r instanceof Room ? r : new Room(r)));
  }

  /** Build from plain JSON (e.g. an API response). */
  static fromJSON(rooms = []) {
    return new ShipLayout(rooms);
  }

  // ---- queries -----------------------------------------------------------
  get isEmpty() {
    return this.rooms.length === 0;
  }
  get stocked() {
    return this.rooms.filter((r) => r.isStocked);
  }
  find(id) {
    return this.rooms.find((r) => r.id === id) || null;
  }
  neighboursOf(room) {
    return this.rooms.filter((o) => room.isAdjacentTo(o));
  }
  isOccupied(x, y) {
    return this.rooms.some((r) => r.x === x && r.y === y);
  }

  /** Free grid cells next to existing rooms (where "+ Add module" boxes go). */
  emptySlots() {
    if (this.isEmpty) return [{ x: 0, y: 0 }];
    const seen = new Set();
    const out = [];
    for (const r of this.rooms) {
      for (const [dx, dy] of DIRS) {
        const x = r.x + dx;
        const y = r.y + dy;
        const k = `${x},${y}`;
        if (!this.isOccupied(x, y) && !seen.has(k)) {
          seen.add(k);
          out.push({ x, y });
        }
      }
    }
    return out;
  }

  /** Pairs of rooms joined by a tunnel (right or down neighbours). */
  connections() {
    const out = [];
    for (const a of this.rooms) {
      for (const b of this.rooms) {
        if (a.x + 1 === b.x && a.y === b.y) out.push({ a, b, dir: 'h' });
        if (a.y + 1 === b.y && a.x === b.x) out.push({ a, b, dir: 'v' });
      }
    }
    return out;
  }

  /** Stable string that changes whenever anything affecting risk changes. */
  fingerprint() {
    return JSON.stringify(
      this.rooms.map((r) => [r.id, r.type, r.x, r.y, r.airflow, r.items.map((i) => [i.id, i.lib, i.qty, i.l, i.w, i.h])])
    );
  }

  // ---- immutable updates -------------------------------------------------
  addRoom(room) {
    return new ShipLayout([...this.rooms, room]);
  }
  removeRoom(id) {
    return new ShipLayout(this.rooms.filter((r) => r.id !== id));
  }
  updateRoom(id, fn) {
    return new ShipLayout(this.rooms.map((r) => (r.id === id ? fn(r) : r)));
  }
  moveRoom(id, x, y) {
    if (this.isOccupied(x, y)) return this;
    return this.updateRoom(id, (r) => r.moveTo(x, y));
  }
  moveItem(itemId, fromId, toId) {
    const from = this.find(fromId);
    const to = this.find(toId);
    const item = from?.findItem(itemId);
    if (!item || !to || from.id === to.id) return this;
    return new ShipLayout(
      this.rooms.map((r) => (r.id === fromId ? r.removeItem(itemId) : r.id === toId ? r.addItem(item) : r))
    );
  }

  toJSON() {
    return this.rooms.map((r) => r.toJSON());
  }
}
