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
      ? 'Drop the module on another module or an empty bay to swap their places.'
      : free
        ? `Fixed hull · ${free} empty bay${free === 1 ? '' : 's'}. Click a bay to assign a module; drag modules to swap places.`
        : 'Fixed hull · every bay is in use. Click a module to stock or retype it; drag to swap places. To change a module, clear it back to a bay.';

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
