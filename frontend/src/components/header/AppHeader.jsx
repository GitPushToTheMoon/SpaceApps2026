import { BrandMark, Segmented } from '../common';
import MissionBar from './MissionBar';

export default function AppHeader({ planner }) {
  const { ui, actions } = planner;
  return (
    <header className="app-header">
      <div className="container app-header__top">
        <div className="brand">
          <BrandMark />
          <div className="brand__text">
            <div className="brand__title">Stowage Fire-Risk Planner</div>
            <div className="brand__sub mono">FLAME IN FREEFALL · CRUISE + SURFACE</div>
          </div>
        </div>
        <div className="spacer" />
        <div className="row gap-10">
          <span className="text-sm muted">Mode</span>
          <Segmented
            options={[
              ['eng', 'Engineer'],
              ['crew', 'Crew handoff'],
            ]}
            value={ui.mode}
            onChange={actions.setMode}
          />
        </div>
      </div>
      <MissionBar planner={planner} />
    </header>
  );
}
