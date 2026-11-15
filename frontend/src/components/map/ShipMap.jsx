import { useMemo } from 'react';
import { COLORS } from '../../domain/constants';
import { Dot } from '../common';
import { MapGeometry } from './MapGeometry';
import MapToolbar from './MapToolbar';
import ShipCanvas from './ShipCanvas';
import ShipOverview from './ShipOverview';

export default function ShipMap({ planner }) {
  const { layout, layoutKey, board, ui, locked, actions } = planner;
  const geo = useMemo(() => new MapGeometry(layout), [layout]);
  const free = layout.bays.length;

  const hint = locked
    ? 'Layout locked for crew. Items can still be added, removed and swapped.'
    : ui.dragId
      ? 'Drop the module on an empty bay to move it there, or on another module to swap places.'
      : free
        ? `Fixed hull · ${free} empty bay${free === 1 ? '' : 's'}. Click a bay to add a module; drag modules to move them; delete a module to free its bay.`
        : 'Hull full · every bay is in use. Delete a module to free a bay; drag modules to swap places.';

  return (
    <div className="card map-card">
      <MapToolbar
        layoutKey={layoutKey}
        locked={locked}
        colouring={ui.colouring}
        onPickLayout={actions.loadLayout}
        onToggleColouring={actions.toggleColouring}
      />
      <div className="map-scroll">
        <ShipCanvas geo={geo} planner={planner} />
      </div>
      <ShipOverview board={board} open={ui.overviewOpen} onToggle={actions.toggleOverview} onSelect={actions.select} />
      <div className="map-hint">
        <Dot size={7} color={locked ? COLORS.amber : COLORS.gray} />
        {hint}
      </div>
    </div>
  );
}
