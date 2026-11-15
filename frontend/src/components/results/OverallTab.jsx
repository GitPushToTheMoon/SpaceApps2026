import { COLORS } from '../../domain/constants';
import { level5, SCALE5 } from '../../domain/levels';
import { Dot } from '../common';

export default function OverallTab({ board }) {
  const ship = board.ship;
  const phases = [
    ['pre', 'Cruise', ship.pre],
    ['surf', 'Surface', ship.surf],
  ];

  return (
    <div className="card card--pad-lg col gap-16">
      <div className="eyebrow">OVERALL FIRE RISK</div>
      <div className="row gap-10 baseline">
        <span className="mono hero-score">{ship.overall ?? '—'}</span>
        <span className="text-md muted">/ 100</span>
      </div>

      <div className="col gap-6">
        <div className="scale">
          {SCALE5.map((z) => {
            const on = ship.overall != null && level5(ship.overall).label === z.label;
            return <div key={z.label} className="scale__seg" style={{ background: z.color, opacity: on ? 1 : 0.28 }} />;
          })}
        </div>
        <div className="row">
          {SCALE5.map((z) => {
            const on = ship.overall != null && level5(ship.overall).label === z.label;
            return (
              <span key={z.label} className="scale__label" style={{ color: on ? COLORS.ink : COLORS.faint, fontWeight: on ? 600 : 400 }}>
                {z.label}
              </span>
            );
          })}
        </div>
      </div>

      <div className="text-md lh-15">{board.sentence}</div>

      {board.assessment?.dataGaps?.length > 0 && (
        <details className="text-sm muted">
          <summary>Data gaps and limits ({board.assessment.dataGaps.length})</summary>
          <ul>
            {board.assessment.dataGaps.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
          {board.assessment.disclaimer && <p>{board.assessment.disclaimer}</p>}
        </details>
      )}

      <div className="grid-2">
        {phases.map(([key, label, score]) => {
          const L = level5(score);
          const drives = ship.stocked && ship.driver === key;
          return (
            <div key={key} className="phase-card" style={{ borderColor: drives ? COLORS.amber : COLORS.lineSoft }}>
              <span className="text-sm muted">{label}</span>
              <span className="mono phase-card__score">{score ?? '—'}</span>
              <span className="row gap-6 text-sm">
                <Dot color={L.color} />
                {L.label}
              </span>
              <span className="phase-card__drives">{drives ? 'DRIVES OVERALL' : ''}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
