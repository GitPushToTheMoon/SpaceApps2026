import { level5 } from '../../domain/levels';
import { Dot, TypeBadge } from '../common';

/** DET / EXT chip: solid when present, red dashed when needed but missing, grey dashed otherwise. */
function SafetyChip({ label, has, needed }) {
  const state = has ? 'has' : needed ? 'missing' : 'none';
  return <span className={`safety-chip safety-chip--${state} mono`}>{label}</span>;
}

export default function ModuleCard({ room, board, left, top, selected, locked, colouring, detail, isDragging, onSelect, onDragStart, onDragEnd, drop = {} }) {
  const s = board.stats(room);
  const score = board.scores(room).overall;
  const L = level5(score);
  const tags = [];
  if (s.heat >= 25 || s.ign >= 2) tags.push('Hot electronics');
  if (s.oxy) tags.push('O₂ outlet');

  return (
    <div
      className={`module ${selected ? 'is-selected' : ''}`}
      style={{ left, top, background: colouring ? L.wash : '#ffffff', cursor: locked ? 'pointer' : 'grab', opacity: isDragging ? 0.35 : 1 }}
      draggable={!locked}
      onDragStart={(e) => {
        if (locked) return e.preventDefault();
        e.dataTransfer.setData('text/plain', room.id);
        e.dataTransfer.effectAllowed = 'move';
        setTimeout(() => onDragStart(room.id), 0);
      }}
      onDragEnd={onDragEnd}
      onClick={() => onSelect(room.id)}
      {...drop}
    >
      <div className="module__stripe" style={{ background: room.color }} />
      <div className="module__body">
        <div className="module__head">
          <TypeBadge room={room} />
          <span className="module__name">{room.name}</span>
        </div>

        {detail && (
          <>
            <div className="module__chips">
              <SafetyChip label="DET" has={s.det} needed={s.fuel > 0 || s.ign > 0} />
              <SafetyChip label="EXT" has={s.ext} needed={s.fuel > 0} />
              {tags.map((t) => (
                <span key={t} className="chip-amber">
                  {t}
                </span>
              ))}
            </div>
            <div className="module__meta mono">
              {room.airflow} cm/s · holds {room.capacity} kg
            </div>
          </>
        )}

        <div className="spacer" />
        <div className="module__foot">
          <span className="row gap-5 module__level">
            <Dot color={L.color} />
            {L.label}
          </span>
          <span className="mono module__score">{score ?? '—'}</span>
        </div>
      </div>
    </div>
  );
}
