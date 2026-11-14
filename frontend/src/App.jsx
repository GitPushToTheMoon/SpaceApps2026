import { usePlanner } from './hooks/usePlanner';
import AppHeader from './components/header/AppHeader';
import ShipMap from './components/map/ShipMap';
import RoomPanel from './components/room/RoomPanel';
import ResultsSection from './components/results/ResultsSection';

export default function App() {
  const planner = usePlanner({ initialLayout: 'iss', cardDetail: 'Full', riskColouring: true });

  if (planner.loading) return <div className="app-loading">Loading planner…</div>;

  return (
    <>
      <AppHeader planner={planner} />

      {planner.loadError && <div className="container banner-error">Couldn’t load data: {planner.loadError}</div>}

      <section className="container workspace">
        <div className="workspace__row">
          <ShipMap planner={planner} />
          {planner.selectedRoom && <RoomPanel planner={planner} room={planner.selectedRoom} />}
        </div>
      </section>

      <ResultsSection planner={planner} />
    </>
  );
}
