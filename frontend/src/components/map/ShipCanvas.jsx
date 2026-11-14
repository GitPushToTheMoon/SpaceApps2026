import { Fragment } from 'react';
import ModuleCard from './ModuleCard';

function Hull({ hull }) {
  return (
    <>
      {hull.engines.map((e, i) => (
        <div key={i} className="hull__engine" style={e} />
      ))}
      <div className="hull" style={hull.body} />
      {hull.ports.map((p, i) => (
        <div key={i} className="hull__port" style={p} />
      ))}
    </>
  );
}

function EmptySlot({ left, top, label, dragging, onAdd, onDropRoom }) {
  return (
    <div
      className={`slot ${dragging ? 'is-dragging' : ''}`}
      style={{ left, top }}
      title="Add a module here"
      onClick={onAdd}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
      }}
      onDrop={(e) => {
        e.preventDefault();
        onDropRoom(e.dataTransfer.getData('text/plain'));
      }}
    >
      <span className="slot__plus">+</span>
      <span className="slot__label">{label}</span>
    </div>
  );
}

export default function ShipCanvas({ geo, planner }) {
  const { layout, board, ui, locked, actions } = planner;
  const dragging = !!ui.dragId;
  const hull = geo.hull();
  const slotLabel = layout.isEmpty ? 'Add first module' : dragging ? 'Drop here' : 'Add module';

  return (
    <div className="ship-canvas" style={{ width: geo.width, height: geo.height }}>
      {hull && <Hull hull={hull} />}

      {geo.tunnels().map((t) => (
        <Fragment key={t.key}>
          <div className="tunnel" style={t.rect} />
          <div className="tunnel__hub" style={t.hub} />
        </Fragment>
      ))}

      {!locked &&
        geo.slots.map((p) => (
          <EmptySlot
            key={`${p.x},${p.y}`}
            left={geo.x(p.x)}
            top={geo.y(p.y)}
            label={slotLabel}
            dragging={dragging}
            onAdd={() => actions.addRoom(p.x, p.y)}
            onDropRoom={(id) => {
              const roomId = id || ui.dragId;
              if (roomId) actions.moveRoom(roomId, p.x, p.y);
            }}
          />
        ))}

      {layout.rooms.map((room) => (
        <ModuleCard
          key={room.id}
          room={room}
          board={board}
          left={geo.x(room.x)}
          top={geo.y(room.y)}
          selected={room.id === ui.sel}
          locked={locked}
          colouring={ui.colouring}
          detail={ui.detail}
          isDragging={ui.dragId === room.id}
          onSelect={actions.select}
          onDragStart={actions.startDrag}
          onDragEnd={actions.endDrag}
        />
      ))}
    </div>
  );
}
