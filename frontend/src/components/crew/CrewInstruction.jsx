import { COLORS } from '../../domain/constants';
import { Dot } from '../common';
import { effectLine } from './crewText';

/** Crew view (Astronaut Bailey): the latest stowage instruction from Isaac, with "Mark as stowed". */
export default function CrewInstruction({ planner }) {
  const { crewMsgs, actions } = planner;
  const msg = crewMsgs[crewMsgs.length - 1];

  if (!msg) {
    return (
      <section className="container crew-wrap">
        <div className="crew-empty">No stowage instructions from the ground right now.</div>
      </section>
    );
  }
  const done = msg.status === 'done';
  return (
    <section className="container crew-wrap">
      <div className="crew-card">
        <div className="crew-card__main">
          <div className="row gap-10 wrap">
            <span className="crew-chip mono">STOWAGE INSTRUCTION</span>
            <span className="text-sm muted nowrap">From Isaac · Inventory and Stowage Officer · {msg.at}</span>
          </div>
          <div className="crew-card__text">{msg.text}</div>
          <div className="row gap-6 wrap">
            <span className="crew-pill">
              {msg.item}
              {msg.dims ? ` · ${msg.dims} cm` : ''}
            </span>
            <span className="crew-pill">{msg.from}</span>
            <span className="muted">→</span>
            <span className="crew-pill crew-pill--to">{msg.to}</span>
          </div>
        </div>
        <div className="crew-card__side">
          <div className="mono text-sm">{effectLine(msg)}</div>
          {done ? (
            <div className="row gap-6 nowrap">
              <Dot color={COLORS.green} />
              Stowed · confirmed {msg.doneAt} · Isaac notified
            </div>
          ) : (
            <>
              <button className="btn btn--dark crew-card__done nowrap" onClick={() => actions.markStowed(msg.id)}>
                Mark as stowed
              </button>
              <div className="text-sm muted">Isaac sees your confirmation right away.</div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
