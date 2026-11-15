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

/** Drag-and-drop target props: dropping a module on a cell swaps the two. */
function dropTarget(room, ui, locked, actions) {
  if (locked) return {};
  return {
    onDragOver: (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    },
    onDrop: (e) => {
      e.preventDefault();
      const id = e.dataTransfer.getData('text/plain') || ui.dragId;
      if (id && id !== room.id) actions.swapRooms(id, room.id);
    },
  };
}

/** An unused cell of the hull. Click it to choose a module type. */
function BayCard({ room, left, top, selected, dragging, locked, onSelect, drop }) {
  return (
    <div
      className={`slot ${dragging ? 'is-dragging' : ''} ${selected ? 'is-selected' : ''}`}
      style={{ left, top, cursor: locked ? 'default' : 'pointer' }}
      title={locked ? 'Empty bay' : 'Empty bay: click to add a module, or drop a module here to move it'}
      onClick={() => !locked && onSelect(room.id)}
      {...drop}
    >
      <span className="slot__plus">+</span>
      <span className="slot__label">{dragging ? 'Move here' : locked ? 'Empty bay' : 'Empty bay · add module'}</span>
    </div>
  );
}

export default function ShipCanvas({ geo, planner }) {
  const { layout, board, ui, locked, actions } = planner;
  const dragging = !!ui.dragId;
  const hull = geo.hull();

  return (
    <div className="ship-canvas" style={{ width: geo.width, height: geo.height }}>
      {hull && <Hull hull={hull} />}

      {geo.tunnels().map((t) => (
        <Fragment key={t.key}>
          <div className="tunnel" style={t.rect} />
          <div className="tunnel__hub" style={t.hub} />
        </Fragment>
      ))}

      {layout.rooms.map((room) =>
        room.isBay ? (
          <BayCard
            key={room.id}
            room={room}
            left={geo.x(room.x)}
            top={geo.y(room.y)}
            selected={room.id === ui.sel}
            dragging={dragging}
            locked={locked}
            onSelect={actions.select}
            drop={dropTarget(room, ui, locked, actions)}
          />
        ) : (
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
            drop={dropTarget(room, ui, locked, actions)}
          />
        )
      )}
    </div>
  );
}
