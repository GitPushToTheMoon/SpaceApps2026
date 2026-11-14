import { ROOM_TYPES } from '../../domain/constants';
import { Field, PhaseBars, TypeBadge } from '../common';
import AddItemForm from './AddItemForm';
import StoredItems from './StoredItems';
import Suggestions from './Suggestions';

export default function RoomPanel({ planner, room }) {
  const { board, library, form, newMat, locked, actions } = planner;
  const sc = board.scores(room);
  const update = (fn) => actions.updateRoom(room.id, fn);

  return (
    <aside className="room-panel">
      <div className="card room-panel__card">
        <div className="room-panel__stripe" style={{ background: room.color }} />

        {/* Header */}
        <div className="room-panel__head">
          <div className="row gap-8">
            <TypeBadge room={room} size="md" />
            <input className="room-panel__name" value={room.name} disabled={locked} onChange={(e) => update((r) => r.rename(e.target.value))} />
            <button className="icon-btn icon-btn--filled" title="Close" onClick={actions.deselect}>
              ×
            </button>
          </div>

          <div className="room-panel__props">
            <Field label="Type" small>
              <select className="input input--sm" value={room.type} disabled={locked} onChange={(e) => update((r) => r.changeType(e.target.value))}>
                {Object.entries(ROOM_TYPES).map(([code, t]) => (
                  <option key={code} value={code}>
                    {t.name} · {code}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Airflow cm/s" small>
              <input
                className="input input--sm mono"
                type="number"
                min="0"
                value={room.airflow}
                disabled={locked}
                onChange={(e) => update((r) => r.setAirflow(Math.max(0, parseFloat(e.target.value) || 0)))}
              />
            </Field>
            <div className="field">
              <span className="field__label field__label--sm">Holds</span>
              <span className="mono room-panel__holds">{room.capacity} kg</span>
            </div>
          </div>

          <PhaseBars
            rows={[
              ['Cruise', sc.pre],
              ['Surface', sc.surf],
            ]}
          />
        </div>

        {/* Body */}
        <div className="room-panel__body">
          <AddItemForm library={library} form={form} newMat={newMat} actions={actions} onAdd={() => actions.addItem(room.id)} />
          <StoredItems room={room} library={library} count={board.stats(room).n} onRemove={(itemId) => actions.removeItem(room.id, itemId)} />
          <Suggestions items={board.suggestions(room)} onApply={actions.applyAction} />
        </div>

        {/* Footer */}
        <div className="room-panel__foot">
          {!locked ? (
            <button className="link-btn link-btn--danger" onClick={() => actions.deleteRoom(room.id)}>
              Delete space
            </button>
          ) : (
            <span />
          )}
          <button className="btn btn--dark" onClick={actions.deselect}>
            Done
          </button>
        </div>
      </div>
    </aside>
  );
}
