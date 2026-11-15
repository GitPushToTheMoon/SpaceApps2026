import { useEffect, useRef } from 'react';
import { CHAT_TABS } from '../../domain/constants';
import { arr } from '../../domain/utils';

export default function AgentChat({ planner, tab }) {
  const { chat, board, actions } = planner;
  const thread = chat.threads[tab] || [];
  const scrollRef = useRef(null);
  const canSend = chat.draft.trim() && !chat.busy;
  const tabName = CHAT_TABS[tab].name;

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [thread.length, chat.busy, tab]);

  return (
    <>
      <div ref={scrollRef} className="chat">
        {!thread.length && (
          <>
            <div className="text-md-sm muted lh-15">
              Ask about this result. The agent sees the full layout, both phases and its latest assessment, and can propose changes you apply in one click.
            </div>
            <div className="row gap-6 wrap">
              {CHAT_TABS[tab].prompts.map((p) => (
                <button key={p} className="prompt-chip" onClick={() => actions.sendChat(p)}>
                  {p}
                </button>
              ))}
            </div>
          </>
        )}

        {thread.map((m, i) => {
          const isUser = m.role === 'user';
          // Only show action buttons that are still valid for the current layout.
          const acts = arr(m.actions)
            .map((a) => ({ action: a, label: board.resolver.describe(a) }))
            .filter((x) => x.label);
          return (
            <div key={i} className={`chat__msg ${isUser ? 'is-user' : 'is-agent'}`}>
              <div className="chat__bubble">{m.text}</div>
              {arr(m.citations).length > 0 && (
                <div className="chat__sources text-xs muted">
                  Sources:{' '}
                  {arr(m.citations).map((c, j) => (
                    <span key={c.id}>
                      {j > 0 && ' · '}
                      <a href={c.source_url} target="_blank" rel="noreferrer" title={`${c.material} · ${c.investigation}`}>
                        {c.id}
                      </a>
                    </span>
                  ))}
                </div>
              )}
              {acts.length > 0 && (
                <div className="chat__acts">
                  {acts.map((x, j) => (
                    <button key={j} className="btn btn--brand btn--xs" onClick={() => actions.applyAction(x.action)}>
                      {x.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {chat.busy === tab && <div className="text-md-sm muted">Agent is thinking…</div>}
      </div>

      <div className="chat__composer">
        <input
          className="input chat__input"
          value={chat.draft}
          placeholder={`Ask about the ${tabName.toLowerCase()}…`}
          onChange={(e) => actions.setChatDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              actions.sendChat(chat.draft);
            }
          }}
        />
        <button className={`btn chat__send ${canSend ? 'btn--brand' : 'btn--muted'}`} onClick={() => actions.sendChat(chat.draft)}>
          Send
        </button>
      </div>
    </>
  );
}
