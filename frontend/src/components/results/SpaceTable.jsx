import { level5 } from '../../domain/levels';
import { COLORS } from '../../domain/constants';
import { Dot, TypeBadge } from '../common';

function ScoreCell({ value }) {
  return (
    <span className="row-inline gap-6 mono">
      <Dot color={level5(value).color} />
      {value ?? '—'}
    </span>
  );
}

export default function SpaceTable({ rows, onSelect, approved, locked, onSignoff }) {
  return (
    <div className="card table-card">
      <div className="row table-card__title">
        <div className="eyebrow">SPACE BY SPACE</div>
        <div className="spacer" />
        {approved ? (
          <span className="signoff-chip nowrap" title="Recorded in this tool for the demo; no real reviewer identities yet">
            <Dot size={7} color={COLORS.green} />
            Approved plan · M&amp;P ✓ · S&amp;MA ✓ · {approved} (demo)
          </span>
        ) : (
          <span className="row gap-10">
            <span className="text-sm muted nowrap">Draft · not yet reviewed</span>
            {!locked && (
              <button className="btn btn--outline-brand btn--xs nowrap" onClick={onSignoff}>
                Record M&amp;P and S&amp;MA sign-off
              </button>
            )}
          </span>
        )}
      </div>
      <div className="table-scroll">
        <table className="space-table">
          <thead>
            <tr>
              <th className="pl-20">Space</th>
              <th>Items</th>
              <th>Cruise</th>
              <th>Surface</th>
              <th>Overall</th>
              <th className="pr-20">Top fix</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.room.id} onClick={() => onSelect(r.room.id)}>
                <td className="pl-20">
                  <div className="row gap-8">
                    <TypeBadge room={r.room} />
                    <div className="col gap-2">
                      <span className="space-table__name">{r.room.name}</span>
                      {r.why && <span className="text-xs muted lh-135">{r.why}</span>}
                    </div>
                  </div>
                </td>
                <td className="mono">{r.items}</td>
                <td>
                  <ScoreCell value={r.pre} />
                </td>
                <td>
                  <ScoreCell value={r.surf} />
                </td>
                <td className="strong">
                  <span className="row-inline gap-6">
                    <span className="mono">{r.overall ?? '—'}</span>
                    <span className="text-sm muted normal">{level5(r.overall).label}</span>
                  </span>
                </td>
                <td className="pr-20 muted text-md-sm">{r.fix}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
