import { COLORS } from '../../domain/constants';
import { Dot } from '../common';
import MissionEditor from './MissionEditor';

export default function MissionBar({ planner }) {
  const { mission: M, ui, actions } = planner;
  const A = M.atmosphere;
  const B = M.destination;
  const summary = [
    { label: 'Destination', value: `${B.body} · ${B.g} g` },
    { label: 'Cruise', value: `0 g · 14.7 psia · 21% O₂ · ${M.preVent} vent · ${M.pad} d` },
    { label: 'Surface', value: `${A.label} · ${M.stay} d stay · ${M.eva} EVA-prep` },
  ];

  return (
    <div className={`mission-bar ${M.confirmed ? '' : 'is-unconfirmed'}`}>
      <div className="container mission-bar__row">
        <span className="mission-bar__title">Mission</span>
        <div className="mission-bar__items">
          {summary.map((s) => (
            <div key={s.label} className="mission-bar__item">
              <span className="text-xs muted">{s.label}</span>
              <span className="mono mission-bar__value">{s.value}</span>
            </div>
          ))}
        </div>
        <span className="status" style={{ color: M.confirmed ? COLORS.ink : COLORS.amberText }}>
          <Dot color={M.confirmed ? COLORS.green : COLORS.amber} />
          {M.confirmed ? 'Confirmed' : 'Not confirmed'}
        </span>
        <button className={`btn btn--outline-dark ${ui.missionOpen ? 'is-active' : ''}`} onClick={actions.toggleMission}>
          {ui.missionOpen ? 'Close' : 'Edit conditions'}
        </button>
      </div>
      {ui.missionOpen && <MissionEditor mission={M} onChange={actions.setMissionField} />}
    </div>
  );
}
