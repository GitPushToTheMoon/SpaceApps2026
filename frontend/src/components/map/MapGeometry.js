/**
 * Converts grid coordinates to pixel positions for the ship canvas,
 * and computes the hull outline and connecting tunnels.
 */
export class MapGeometry {
  static W = 176; // module width
  static H = 124; // module height
  static GAP = 36; // gap between modules
  static PAD = 30; // canvas padding

  constructor(layout) {
    this.layout = layout;
    this.slots = layout.emptySlots();
    const pts = [...layout.rooms, ...this.slots];
    this.minX = Math.min(...pts.map((p) => p.x));
    this.maxX = Math.max(...pts.map((p) => p.x));
    this.minY = Math.min(...pts.map((p) => p.y));
    this.maxY = Math.max(...pts.map((p) => p.y));
  }

  x(gx) {
    const { W, GAP, PAD } = MapGeometry;
    return PAD + (gx - this.minX) * (W + GAP);
  }
  y(gy) {
    const { H, GAP, PAD } = MapGeometry;
    return PAD + (gy - this.minY) * (H + GAP);
  }
  get width() {
    const { W, GAP, PAD } = MapGeometry;
    return PAD * 2 + (this.maxX - this.minX + 1) * (W + GAP) - GAP;
  }
  get height() {
    const { H, GAP, PAD } = MapGeometry;
    return PAD * 2 + (this.maxY - this.minY + 1) * (H + GAP) - GAP;
  }

  /** Hull outline around all rooms (null when the ship is empty). */
  hull() {
    const rooms = this.layout.rooms;
    if (!rooms.length) return null;
    const { W, H } = MapGeometry;
    const x0 = Math.min(...rooms.map((r) => r.x));
    const x1 = Math.max(...rooms.map((r) => r.x));
    const y0 = Math.min(...rooms.map((r) => r.y));
    const y1 = Math.max(...rooms.map((r) => r.y));
    const left = this.x(x0) - 16;
    const top = this.y(y0) - 16;
    const width = this.x(x1) + W + 16 - left;
    const height = this.y(y1) + H + 16 - top;
    const rad = Math.min(height / 2, 110);
    const portX = left + width - Math.min(rad, 70) * 0.55;
    return {
      body: { left, top, width, height, borderRadius: `14px ${rad}px ${rad}px 14px` },
      engines: [top + height / 3 - 15, top + (2 * height) / 3 - 15].map((t) => ({ left: left - 12, top: t })),
      ports: [-18, 0, 18].map((d) => ({ left: portX - 5, top: top + height / 2 + d - 5 })),
    };
  }

  /** Corridor rectangles + hub circles between adjacent rooms. */
  tunnels() {
    const { W, H, GAP } = MapGeometry;
    return this.layout.connections().map(({ a, b, dir }) => {
      const ax = this.x(a.x);
      const ay = this.y(a.y);
      return dir === 'h'
        ? { key: `${a.id}-${b.id}`, rect: { left: ax + W, top: ay + H / 2 - 11, width: GAP, height: 22 }, hub: { left: ax + W + GAP / 2 - 7, top: ay + H / 2 - 7 } }
        : { key: `${a.id}-${b.id}`, rect: { left: ax + W / 2 - 11, top: ay + H, width: 22, height: GAP }, hub: { left: ax + W / 2 - 7, top: ay + H + GAP / 2 - 7 } };
    });
  }
}
