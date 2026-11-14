export default function MovesTab({ moves, onApply }) {
  return (
    <div className="card card--pad-lg col gap-12" style={{ maxWidth: 880 }}>
      <div className="eyebrow">SUGGESTED ITEM MOVES</div>
      <div className="text-help">Item moves the agent recommends to lower combined risk across both phases.</div>
      {!moves.length && <div className="empty-note">No moves would lower combined risk.</div>}
      {moves.map((mv) => (
        <div key={mv.key} className="move-row">
          <div className="move-row__text">
            <span className="text-md strong-500">{mv.item}</span>
            <span className="text-sm muted">
              {mv.from} → {mv.to}
            </span>
            <span className="text-sm muted lh-14">{mv.reason}</span>
          </div>
          <span className="mono move-row__delta">{mv.delta}</span>
          <button className="btn btn--amber btn--xs" onClick={() => onApply(mv.action)}>
            Apply
          </button>
        </div>
      ))}
    </div>
  );
}
