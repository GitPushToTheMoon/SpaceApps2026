import { COLORS } from '../../domain/constants';

/** Turns the agent state into a display status. */
export function agentStatus(agent, reqKey) {
  const has = !!agent.result;
  const pending = !agent.key || agent.key !== reqKey;
  const state =
    agent.status === 'running' ? 'run' : agent.status === 'error' ? (has ? 'errOld' : 'err') : has && pending ? 'stale' : has ? 'ok' : 'wait';
  const hhmm = agent.at ? agent.at.toTimeString().slice(0, 5) : '';

  return {
    state,
    dot: { run: COLORS.amber, err: COLORS.red, errOld: COLORS.red, stale: COLORS.amber, ok: COLORS.green, wait: COLORS.gray }[state],
    text: {
      run: 'Agent assessing…',
      err: 'Agent unavailable · showing baseline rules',
      errOld: 'Agent unreachable · showing last assessment',
      stale: 'Layout changed · re-assessing shortly',
      ok: `Assessed by agent · ${hhmm}`,
      wait: 'Baseline rules · waiting for agent',
    }[state],
    short: state === 'ok' ? `assessed ${hhmm}` : state === 'run' ? 'assessing…' : state === 'stale' ? 're-assessing shortly' : 'baseline rules shown',
  };
}
