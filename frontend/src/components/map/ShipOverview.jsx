import { COLORS } from '../../domain/constants';
import { level5 } from '../../domain/levels';
import { Dot, PhaseBars } from '../common';

export default function ShipOverview({ board, open, onToggle, onSelect }) {
  const ship = board.ship;
  const L = level5(ship.overall);

  return (
    <div className="overview">
      <button className="overview__toggle" onClick={onToggle}>
        <span className="eyebrow flex-1">WHOLE SPACECRAFT</span>
        <span className="row gap-6 text-md strong">
          <Dot color={L.color} />
          {L.label}
        </span>
        <span className="mono overview__score">{ship.overall ?? '—'}</span>
        <span className="overview__chevron">{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div className="overview__body">
          <div className="overview__hero">
            <span className="mono overview__big">{ship.overall ?? '—'}</span>
            <div className="col gap-3">
              <span className="row gap-6 overview__level">
                <Dot size={10} color={L.color} />
                {L.label}
              </span>
              <span className="text-sm muted">{!ship.stocked ? 'No stocked spaces yet' : ship.driver ? `Driven by ${ship.driver === 'surf' ? 'surface' : 'cruise'}` : 'Waiting for assessment'}</span>
            </div>
          </div>

          <PhaseBars
            rows={[
              ['Cruise', ship.pre],
              ['Surface', ship.surf],
            ]}
          />

          <div className="count-grid">
            {board.counts().map((c) => (
              <div key={c.label} className="count-grid__cell">
                <span className="mono count-grid__value" style={{ color: c.alert ? COLORS.danger : COLORS.ink }}>
                  {c.value}
                </span>
                <span className="count-grid__label">{c.label}</span>
              </div>
            ))}
          </div>

          <div className="col gap-6">
            <div className="eyebrow">HIGHEST-RISK SPACES</div>
            {board.topSpaces().map(({ room, score, why }) => (
              <button key={room.id} className="list-btn" onClick={() => onSelect(room.id)}>
                <Dot color={level5(score).color} />
                <div className="list-btn__text">
                  <span className="list-btn__title">{room.name}</span>
                  <span className="list-btn__sub">{why}</span>
                </div>
                <span className="mono list-btn__score">{score}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
