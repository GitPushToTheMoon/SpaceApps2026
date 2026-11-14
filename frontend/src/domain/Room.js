import { ROOM_TYPES, typeColor } from './constants';
import { Item } from './Item';
import { newId } from './utils';

/**
 * A module / space on the ship grid. Immutable — every mutator returns a new Room.
 */
export class Room {
  constructor({ id = newId(), name = 'New module', type = 'OTH', x = 0, y = 0, airflow, items = [] }) {
    this.id = id;
    this.name = name;
    this.type = ROOM_TYPES[type] ? type : 'OTH';
    this.x = x;
    this.y = y;
    this.airflow = airflow ?? ROOM_TYPES[this.type].air;
    this.items = items.map((i) => (i instanceof Item ? i : new Item(i)));
  }

  // ---- read-only helpers -------------------------------------------------
  get info() {
    return ROOM_TYPES[this.type];
  }
  get isPassage() {
    return !!this.info.passage;
  }
  get capacity() {
    return this.info.cap;
  }
  get color() {
    return typeColor(this.type);
  }
  get isStocked() {
    return this.items.length > 0;
  }

  isAdjacentTo(other) {
    return other.id !== this.id && Math.abs(this.x - other.x) + Math.abs(this.y - other.y) === 1;
  }
  hasItem(lib) {
    return this.items.some((i) => i.lib === lib);
  }
  findItem(itemId) {
    return this.items.find((i) => i.id === itemId);
  }

  // ---- immutable updates -------------------------------------------------
  with(changes) {
    const { id, name, type, x, y, airflow, items } = this;
    return new Room({ id, name, type, x, y, airflow, items, ...changes });
  }
  rename(name) {
    return this.with({ name });
  }
  changeType(type) {
    return this.with({ type, airflow: ROOM_TYPES[type].air });
  }
  setAirflow(airflow) {
    return this.with({ airflow });
  }
  moveTo(x, y) {
    return this.with({ x, y });
  }
  addItem(item) {
    return this.with({ items: [...this.items, item] });
  }
  removeItem(itemId) {
    return this.with({ items: this.items.filter((i) => i.id !== itemId) });
  }
  replaceItem(itemId, fn) {
    return this.with({ items: this.items.map((i) => (i.id === itemId ? fn(i) : i)) });
  }

  toJSON() {
    const { id, name, type, x, y, airflow } = this;
    return { id, name, type, x, y, airflow, items: this.items.map((i) => i.toJSON()) };
  }
}
