import { useEffect, useMemo, useRef, useState } from 'react';
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

  // Shrink the ship to fit narrow screens (phones); below MIN_SCALE it scrolls instead.
  const scrollRef = useRef(null);
  const [avail, setAvail] = useState(0);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(([e]) => setAvail(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const MIN_SCALE = 0.55; // smaller than this is unreadable; the map scrolls sideways instead
  const scale = avail && avail < geo.width ? Math.max(MIN_SCALE, avail / geo.width) : 1;

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
      <div className="map-scroll" ref={scrollRef}>
        <div className="ship-fit" style={{ width: geo.width * scale, height: geo.height * scale }}>
          <div style={{ transform: `scale(${scale})`, transformOrigin: 'top left', width: geo.width }}>
            <ShipCanvas geo={geo} planner={planner} />
          </div>
        </div>
      </div>
      <ShipOverview board={board} open={ui.overviewOpen} onToggle={actions.toggleOverview} onSelect={actions.select} />
      <div className="map-hint">
        <Dot size={7} color={locked ? COLORS.brand : COLORS.gray} />
        {hint}
      </div>
    </div>
  );
}
