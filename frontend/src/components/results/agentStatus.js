import { COLORS } from '../../domain/constants';

/** Turns the assessment request state into a display status. */
export function agentStatus(agent, reqKey) {
  const has = !!agent.result;
  const pending = !agent.key || agent.key !== reqKey;
  const state =
    agent.status === 'running' ? 'run' : agent.status === 'error' ? (has ? 'errOld' : 'err') : has && pending ? 'stale' : has ? 'ok' : 'wait';
  const hhmm = agent.at ? agent.at.toTimeString().slice(0, 5) : '';
  // Scores always come from code; "template" means the AI was busy, so the explanations are plain text.
  const plain = agent.result?.textSource === 'template';

  return {
    state,
    dot: { run: COLORS.brand, err: COLORS.red, errOld: COLORS.red, stale: COLORS.brand, ok: COLORS.green, wait: COLORS.gray }[state],
    text: {
      run: 'Assessing…',
      err: 'Backend unreachable · no assessment yet',
      errOld: 'Backend unreachable · showing last assessment',
      stale: 'Layout changed · re-assessing shortly',
      ok: plain ? `Assessed · ${hhmm} · AI busy, plain explanations` : `Assessed by agent · ${hhmm}`,
      wait: 'Waiting for first assessment',
    }[state],
    short:
      state === 'ok' ? `assessed ${hhmm}` : state === 'run' ? 'assessing…' : state === 'stale' ? 're-assessing shortly' : state === 'errOld' ? 'last assessment shown' : 'no assessment yet',
  };
}
