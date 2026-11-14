import { Segmented } from '../common';

export default function FactorsTab({ board, phase, onPhase, selectedRoom }) {
  const rows = board.factorRows(phase, selectedRoom);
  const showSel = rows.some((r) => r.selected != null);

  return (
    <div className="card card--pad-lg col gap-14">
      <div className="row gap-12 wrap">
        <div className="eyebrow">RISK FACTORS</div>
        <div className="spacer" />
        <Segmented
          variant="light"
          size="sm"
          options={[
            ['pre', 'Cruise'],
            ['surf', 'Surface'],
          ]}
          value={phase}
          onChange={onPhase}
        />
      </div>

      <div className="row gap-16 wrap text-xs muted">
        <span className="row gap-6">
          <span className="legend-avg" />
          Ship average
        </span>
        <span className="row gap-6">
          <span className="legend-band" />
          Lowest–highest space
        </span>
        {showSel && (
          <span className="row gap-6">
            <span className="legend-sel" />
            {selectedRoom.name}
          </span>
        )}
      </div>

      <div className="col gap-12">
        {rows.map((f) => (
          <div key={f.label} className="factor">
            <span className="text-md">{f.label}</span>
            <div className="factor__track">
              <div className="factor__rail" />
              <div className="factor__fill" style={{ width: `${f.avg}%`, background: f.color }} />
              <div className="factor__band" style={{ left: `${f.min}%`, width: `${Math.max(f.max - f.min, 0.5)}%` }} />
              <div className="factor__avg" style={{ left: `${f.avg}%` }} />
              {f.selected != null && <div className="factor__sel" style={{ left: `${f.selected}%` }} />}
            </div>
            <span className="mono factor__value">{f.avg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
