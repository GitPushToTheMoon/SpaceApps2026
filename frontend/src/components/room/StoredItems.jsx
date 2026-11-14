import { COLORS, FLAMMABILITY } from '../../domain/constants';
import { Dot } from '../common';

function itemTag(m) {
  if (m.flam) return FLAMMABILITY[m.flam];
  if (m.oxy) return 'O₂ source';
  if (m.ign) return 'Ignition';
  return 'Safety';
}

function itemColor(m) {
  if (m.flam === 3) return COLORS.red;
  if (m.flam === 2) return COLORS.yellow;
  if (m.flam === 1) return COLORS.green;
  if (m.ign || m.oxy) return COLORS.ink;
  return COLORS.gray;
}

export default function StoredItems({ room, library, count, onRemove }) {
  return (
    <div className="col gap-6">
      <div className="eyebrow">STORED · {count}</div>
      {!room.isStocked && <div className="empty-note">Nothing stowed here yet.</div>}
      {room.items.map((item) => {
        const m = library.get(item.lib) || { name: item.lib };
        return (
          <div key={item.id} className="item-row">
            <Dot square color={itemColor(m)} />
            <div className="item-row__text">
              <span className="text-md">
                {m.name}
                {m.saved ? ' (saved)' : ''}
              </span>
              <span className="mono item-row__meta">
                ×{item.qty} · {item.l} × {item.w} × {item.h} cm
              </span>
            </div>
            <span className="text-xs muted">{itemTag(m)}</span>
            <button className="icon-btn" title="Remove" onClick={() => onRemove(item.id)}>
              ×
            </button>
          </div>
        );
      })}
    </div>
  );
}
