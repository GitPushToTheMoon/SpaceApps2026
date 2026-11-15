import { HULL_SIZES, LAYOUT_OPTIONS } from '../../domain/constants';
import { MAP_LEGEND } from '../../domain/levels';
import { Dot } from '../common';

export default function MapToolbar({ layoutKey, locked, colouring, onPickLayout, onToggleColouring }) {
  return (
    <div className="map-toolbar">
      <span className="text-sm muted">Ship</span>
      <div className="row gap-6 wrap">
        {LAYOUT_OPTIONS.map(([key, name]) => {
          const active = key.startsWith('custom') ? layoutKey.startsWith('custom') : layoutKey === key;
          return (
            <button key={key} className={`chip-btn ${active ? 'is-active' : ''}`} disabled={locked} onClick={() => onPickLayout(key)}>
              {name}
            </button>
          );
        })}
        {layoutKey.startsWith('custom') && (
          <select className="input input--sm" style={{ width: "auto" }} value={layoutKey} disabled={locked} onChange={(e) => onPickLayout(e.target.value)} title="Hull size">
            {HULL_SIZES.map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        )}
      </div>
      <div className="spacer" />
      <div className="row gap-12">
        {MAP_LEGEND.map((g) => (
          <span key={g.label} className="row gap-5 text-sm muted">
            <Dot size={9} square color={g.color} />
            {g.label}
          </span>
        ))}
      </div>
      <button className="toggle-btn" onClick={onToggleColouring}>
        <span className={`switch ${colouring ? 'is-on' : ''}`}>
          <span className="switch__knob" />
        </span>
        Risk colouring
      </button>
    </div>
  );
}
