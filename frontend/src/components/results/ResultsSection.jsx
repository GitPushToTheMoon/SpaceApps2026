import { CHAT_TABS } from '../../domain/constants';
import { BrandMark, Dot } from '../common';
import { agentStatus } from './agentStatus';
import AgentChat from './AgentChat';
import FactorsTab from './FactorsTab';
import MovesTab from './MovesTab';
import OverallTab from './OverallTab';
import SpaceTable from './SpaceTable';

export default function ResultsSection({ planner }) {
  const { board, ui, agent, reqKey, selectedRoom, actions } = planner;
  const status = agentStatus(agent, reqKey);
  const tab = CHAT_TABS[ui.tab] ? ui.tab : 'overall';
  const moves = board.moves();

  const tabs = [
    ['overall', 'Overall fire risk', board.ship.overall],
    ['factors', 'Risk factors', ''],
    ['moves', 'Suggested moves', moves.length || ''],
    ['table', 'Space by space', board.ranked.length],
  ];

  return (
    <section className="container results">
      <div className="card agent-card">
        {/* 1. Agent header */}
        <div className="agent-card__head">
          <BrandMark size={28} />
          <div className="col gap-1 flex-1">
            <span className="agent-card__title">Fire-safety agent</span>
            <span className="text-sm muted">
              {CHAT_TABS[tab].name} · {status.short}
            </span>
          </div>
          <span className="tag tag--amber mono nowrap">AGENT RESULT</span>
        </div>

        {/* 2. Tab bar, inside the agent box */}
        <div className="results__tabs">
          {tabs.map(([key, label, badge]) => (
            <button key={key} className={`tab ${tab === key ? 'is-active' : ''}`} onClick={() => actions.setTab(key)}>
              {label}
              <span className="mono tab__badge">{badge}</span>
            </button>
          ))}
          <div className="spacer" />
          <div className="row gap-10 results__status">
            <span className="row gap-6 text-sm muted">
              <Dot size={7} color={status.dot} />
              {status.text}
            </span>
            <button className="btn btn--light btn--xs nowrap" disabled={status.state === 'run'} onClick={actions.reassess}>
              Re-assess
            </button>
          </div>
        </div>

        <div className="agent-card__result">
          {tab === 'overall' && <OverallTab board={board} />}
          {tab === 'factors' && <FactorsTab board={board} phase={ui.factorPhase} onPhase={actions.setFactorPhase} selectedRoom={selectedRoom} />}
          {tab === 'moves' && <MovesTab moves={moves} onApply={actions.applyAction} />}
          {tab === 'table' && <SpaceTable rows={board.tableRows()} onSelect={actions.select} />}
        </div>

        <AgentChat planner={planner} tab={tab} />
      </div>
    </section>
  );
}
