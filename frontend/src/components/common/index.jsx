import logoUrl from '../../assets/sparkshield-logo.png';
import { level5 } from '../../domain/levels';

/** Small coloured status dot. */
export function Dot({ color, size = 8, square = false }) {
  return <span className="dot" style={{ width: size, height: size, background: color, borderRadius: square ? 2 : '50%' }} />;
}

/** SparkShield logo: wide in the header, inside a small tile for the agent avatar. */
export function BrandMark({ avatar = false }) {
  if (avatar) {
    return (
      <div className="agent-avatar">
        <img src={logoUrl} alt="" />
      </div>
    );
  }
  return <img className="brand-logo" src={logoUrl} alt="SparkShield" />;
}

/** Room type code badge (e.g. "LAB"). */
export function TypeBadge({ room, size = 'sm' }) {
  return (
    <span className={`type-badge type-badge--${size}`} style={{ background: room.color }}>
      {room.type}
    </span>
  );
}

/** Pill-style segmented control. variant: 'dark' (active = black) | 'light' (active = white). */
export function Segmented({ options, value, onChange, variant = 'dark', size = 'md' }) {
  return (
    <div className={`segmented segmented--${variant} segmented--${size}`}>
      {options.map(([key, label]) => (
        <button key={key} className={`segmented__btn ${value === key ? 'is-active' : ''}`} onClick={() => onChange(key)}>
          {label}
        </button>
      ))}
    </div>
  );
}

/** Cruise / Surface horizontal score bars. rows: [[label, score], ...] */
export function PhaseBars({ rows }) {
  return (
    <div className="phase-bars">
      {rows.map(([label, v]) => {
        const L = level5(v);
        return (
          <div key={label} className="phase-bars__row">
            <span className="text-sm muted">{label}</span>
            <div className="bar">
              <div className="bar__fill" style={{ width: `${v || 0}%`, background: L.color }} />
            </div>
            <span className="mono phase-bars__score">{v ?? '—'}</span>
            <span className="text-sm">{L.label}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Labelled form field wrapper. */
export function Field({ label, children, className = '', small = false }) {
  return (
    <label className={`field ${className}`}>
      <span className={small ? 'field__label field__label--sm' : 'field__label'}>{label}</span>
      {children}
    </label>
  );
}
