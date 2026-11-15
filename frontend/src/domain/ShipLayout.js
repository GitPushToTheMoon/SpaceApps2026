import { Room } from './Room';

/**
 * The whole ship: a fixed hull of grid cells. Each cell is a module (Room) or an
 * empty bay (a Room of type BAY). The hull never grows: modules can be retyped,
 * cleared back to a bay, or swapped with another cell. Immutable.
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
  /** Real spaces (not empty bays): what gets scored and shown in tables. */
  get modules() {
    return this.rooms.filter((r) => !r.isBay);
  }
  get bays() {
    return this.rooms.filter((r) => r.isBay);
  }
  find(id) {
    return this.rooms.find((r) => r.id === id) || null;
  }
  neighboursOf(room) {
    return this.modules.filter((o) => room.isAdjacentTo(o));
  }
  isOccupied(x, y) {
    return this.rooms.some((r) => r.x === x && r.y === y);
  }

  /** Pairs of modules joined by a tunnel (right or down neighbours); bays have no tunnels. */
  connections() {
    const out = [];
    const mods = this.modules;
    for (const a of mods) {
      for (const b of mods) {
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
  updateRoom(id, fn) {
    return new ShipLayout(this.rooms.map((r) => (r.id === id ? fn(r) : r)));
  }
  /** Swap two cells' positions (a module with another module or with an empty bay). */
  swapRooms(idA, idB) {
    const a = this.find(idA);
    const b = this.find(idB);
    if (!a || !b || a.id === b.id) return this;
    return new ShipLayout(this.rooms.map((r) => (r.id === a.id ? r.moveTo(b.x, b.y) : r.id === b.id ? r.moveTo(a.x, a.y) : r)));
  }
  clearRoom(id) {
    return this.updateRoom(id, (r) => r.clear());
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
