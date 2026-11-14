import { newId } from './utils';

/**
 * One stowed line item (a material, machine or safety item) inside a Room.
 * Immutable: use `with()` to get a changed copy so React sees new state.
 */
export class Item {
  constructor({ id = newId(), lib, qty = 1, l = 0, w = 0, h = 0 }) {
    this.id = id;
    this.lib = lib; // key into the MaterialLibrary
    this.qty = qty;
    this.l = l;
    this.w = w;
    this.h = h;
  }

  /** Total volume in cm³ across all units. */
  get volume() {
    return this.l * this.w * this.h * this.qty;
  }

  /** 1–4 multiplier on fuel load based on volume. */
  get sizeFactor() {
    return Math.min(4, 1 + Math.floor(this.volume / 1000 / 5));
  }

  get minDimension() {
    return Math.min(this.l, this.w, this.h);
  }

  with(changes) {
    return new Item({ ...this.toJSON(), ...changes });
  }

  toJSON() {
    const { id, lib, qty, l, w, h } = this;
    return { id, lib, qty, l, w, h };
  }
}
