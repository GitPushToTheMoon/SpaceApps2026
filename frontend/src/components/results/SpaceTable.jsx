import { level5 } from '../../domain/levels';
import { Dot, TypeBadge } from '../common';

function ScoreCell({ value }) {
  return (
    <span className="row-inline gap-6 mono">
      <Dot color={level5(value).color} />
      {value ?? '—'}
    </span>
  );
}

export default function SpaceTable({ rows, onSelect }) {
  return (
    <div className="card table-card">
      <div className="eyebrow table-card__title">SPACE BY SPACE</div>
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
                      <span>{r.room.name}</span>
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
