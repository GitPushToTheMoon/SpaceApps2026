export default function Suggestions({ items, onApply }) {
  if (!items.length) return null;
  return (
    <div className="col gap-6">
      <div className="eyebrow">SUGGESTIONS</div>
      {items.map((s, i) => (
        <div key={i} className="suggestion">
          <div className="suggestion__text">
            <span className="suggestion__title">{s.title}</span>
            <span className="text-xs muted">{s.why}</span>
          </div>
          {s.action && (
            <button className="btn btn--outline-dark btn--xs" onClick={() => onApply(s.action)}>
              Apply
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
