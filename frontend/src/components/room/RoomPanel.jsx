import { MODULE_TYPES } from '../../domain/constants';
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
            <input className="room-panel__name" value={room.name} disabled={locked || room.isBay} onChange={(e) => update((r) => r.rename(e.target.value))} />
            <button className="icon-btn icon-btn--filled" title="Close" onClick={actions.deselect}>
              ×
            </button>
          </div>

          <div className="room-panel__props">
            <Field label="Type" small>
              <select className="input input--sm" value={room.type} disabled={locked} onChange={(e) => update((r) => r.changeType(e.target.value))}>
                {room.isBay && (
                  <option value="BAY" disabled>
                    Choose a module type…
                  </option>
                )}
                {MODULE_TYPES.map(([code, t]) => (
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
                disabled={locked || room.isBay}
                onChange={(e) => update((r) => r.setAirflow(Math.max(0, parseFloat(e.target.value) || 0)))}
              />
            </Field>
            <div className="field">
              <span className="field__label field__label--sm">Holds</span>
              <span className="mono room-panel__holds">{room.capacity} kg</span>
            </div>
          </div>

          {!room.isBay && (
            <PhaseBars
              rows={[
                ['Cruise', sc.pre],
                ['Surface', sc.surf],
              ]}
            />
          )}
        </div>

        {/* Body */}
        <div className="room-panel__body">
          {room.isBay ? (
            <div className="text-md-sm muted lh-15">
              This bay is empty. Choose a module type above to add a module here. The hull is fixed, so new modules can only
              go into empty bays; delete a module to free its bay.
            </div>
          ) : (
            <>
              <AddItemForm library={library} form={form} newMat={newMat} actions={actions} onAdd={() => actions.addItem(room.id)} />
              <StoredItems room={room} library={library} count={board.stats(room).n} onRemove={(itemId) => actions.removeItem(room.id, itemId)} />
              <Suggestions items={board.suggestions(room)} onApply={actions.applyAction} />
            </>
          )}
        </div>

        {/* Footer */}
        <div className="room-panel__foot">
          {!locked && !room.isBay ? (
            <button
              className="link-btn link-btn--danger"
              title="Removes the module and its items, leaving an empty bay in the hull"
              onClick={() => actions.clearRoom(room.id)}
            >
              Delete module
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
