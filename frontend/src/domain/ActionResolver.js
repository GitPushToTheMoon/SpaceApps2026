import { SAFETY_ITEMS } from './constants';
import { Item } from './Item';

/**
 * Validates and applies "actions" — the one-click fixes coming from either
 * the heuristics or the agent. Shapes:
 *   { type: 'swap', room_id, item_id, to }
 *   { type: 'add',  room_id, key: 'ext' | 'det' | 'mask' }
 *   { type: 'move', item_id, from_id, to_id }
 */
export class ActionResolver {
  constructor(layout, library) {
    this.layout = layout;
    this.library = library;
  }

  /** Button label if the action is valid for the current layout, else null. */
  describe(a) {
    if (!a || !a.type) return null;
    const L = this.layout;
    const lib = this.library;

    if (a.type === 'swap') {
      const room = L.find(a.room_id);
      const item = room?.findItem(a.item_id);
      const to = lib.get(a.to);
      if (!item || !to || item.lib === a.to) return null;
      return `Swap ${lib.name(item.lib)} → ${to.name}`;
    }
    if (a.type === 'add') {
      const room = L.find(a.room_id);
      if (!room || !SAFETY_ITEMS[a.key] || room.hasItem(a.key)) return null;
      return `Add ${lib.name(a.key).toLowerCase()} to ${room.name}`;
    }
    if (a.type === 'move') {
      const from = L.find(a.from_id);
      const to = L.find(a.to_id);
      const item = from?.findItem(a.item_id);
      if (!item || !to || from.id === to.id) return null;
      return `Move ${lib.name(item.lib)} to ${to.name}`;
    }
    return null;
  }

  /** Returns a new ShipLayout with the action applied (or the same one if invalid). */
  static apply(a, layout) {
    switch (a?.type) {
      case 'swap':
        return layout.updateRoom(a.room_id, (r) => r.replaceItem(a.item_id, (i) => i.with({ lib: a.to })));
      case 'add': {
        const size = SAFETY_ITEMS[a.key];
        if (!size) return layout;
        return layout.updateRoom(a.room_id, (r) => (r.hasItem(a.key) ? r : r.addItem(new Item({ lib: a.key, qty: 1, ...size }))));
      }
      case 'move':
        return layout.moveItem(a.item_id, a.from_id, a.to_id);
      default:
        return layout;
    }
  }
}
