import { COLORS } from '../../domain/constants';
import { Dot } from '../common';
import { effectLine } from '../crew/crewText';

/** Engineer side of the crew instruction: draft from the last applied move, send, then status. */
function CrewOutbox({ planner }) {
  const { crewDraft, crewMsgs, actions } = planner;
  if (!crewDraft && !crewMsgs.length) return null;
  return (
    <div className="crew-outbox col gap-10">
      {crewDraft && (
        <div className="crew-draft col gap-8">
          <div className="eyebrow">INSTRUCTION FOR ASTRONAUT BAILEY</div>
          <div className="text-md">“{crewDraft.text}”</div>
          <div className="mono text-sm muted">{effectLine(crewDraft)} · about 5 minutes of crew time</div>
          <div className="row gap-8">
            <button className="btn btn--dark btn--xs nowrap" onClick={actions.sendToCrew}>
              Send to Bailey
            </button>
            <button className="btn btn--light btn--xs nowrap" onClick={actions.discardCrewDraft}>
              Discard
            </button>
          </div>
        </div>
      )}
      {crewMsgs
        .slice()
        .reverse()
        .map((m) => (
          <div key={m.id} className="row gap-10 crew-sent">
            <span className="signoff-chip nowrap">
              <Dot size={7} color={m.status === 'done' ? COLORS.green : COLORS.brand} />
              {m.status === 'done' ? `Bailey confirmed stowed · ${m.doneAt}` : `Sent to Bailey · ${m.at} · awaiting confirmation`}
            </span>
            <span className="text-sm muted">
              {m.item}: {m.from} → {m.to}
            </span>
          </div>
        ))}
    </div>
  );
}

export default function MovesTab({ moves, planner }) {
  const { locked, actions } = planner;
  return (
    <div className="card card--pad-lg col gap-12" style={{ maxWidth: 880 }}>
      <div className="eyebrow">SUGGESTED ITEM MOVES</div>
      <div className="text-help">Item moves the agent recommends to lower combined risk across both phases.</div>
      {!locked && <CrewOutbox planner={planner} />}
      {!moves.length && (
        <div className="empty-note">
          No safe moves. Every space without ignition or oxygen sources is already High, or would become High. Try the room
          fixes, or add a stowage module in an empty bay.
        </div>
      )}
      {moves.map((mv) => (
        <div key={mv.key} className="move-row">
          <div className="move-row__text">
            <span className="text-md strong-500">{mv.item}</span>
            <span className="text-sm muted">
              {mv.from} → {mv.to}
            </span>
            <span className="text-sm muted lh-14">{mv.reason}</span>
          </div>
          <span className="mono move-row__delta">{mv.delta}</span>
          <button
            className="btn btn--brand btn--xs"
            onClick={() => (locked ? actions.applyAction(mv.action) : actions.applyMove(mv))}
          >
            Apply
          </button>
        </div>
      ))}
    </div>
  );
}
