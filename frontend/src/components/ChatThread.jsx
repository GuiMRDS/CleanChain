import { useLayoutEffect, useRef, useState } from 'react';
import { bytesLabel, formatCount } from '../agent/format.js';
import './ChatThread.css';

const STEP_LABEL = { thought: 'Pensamento', action: 'Ação', observation: 'Observação' };
const STICK_PX = 48; // "at the bottom" tolerance

// Minimal inline markdown for agent answers: **bold**, *italic* and `code`. Line breaks via CSS.
function RichText({ text }) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g).map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) return <code key={i}>{part.slice(1, -1)}</code>;
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) return <em key={i}>{part.slice(1, -1)}</em>;
    return part;
  });
}

// Human-in-the-loop card: nothing is deleted until the user clicks "Mover para a Lixeira".
function ApprovalCard({ approval, onDecide, disabled, lixeira }) {
  const { items = [], blocked = [], total_bytes: total = 0, reason, status } = approval;
  const pending = status === 'pending';

  return (
    <div className={`approval is-${status}`} role="group" aria-label="Confirmar exclusão">
      <header className="approval__head">
        <span className="approval__icon" aria-hidden="true">!</span>
        <span>Confirmar limpeza</span>
        <b>{bytesLabel(total)}</b>
      </header>
      {reason && <p className="approval__reason">{reason}</p>}

      {items.length > 0 && (
        <ul className="approval__list">
          {items.map((it) => (
            <li key={it.path} title={it.path}>
              <span className="approval__kind" aria-hidden="true">{it.is_dir ? '▣' : '▤'}</span>
              <span className="approval__name">
                {it.name}
                <small>{it.path}</small>
              </span>
              <span className="approval__size">{bytesLabel(it.bytes)}</span>
            </li>
          ))}
        </ul>
      )}

      {blocked.length > 0 && (
        <details className="approval__blocked">
          <summary>{formatCount(blocked.length)} item(ns) protegido(s) não serão apagados</summary>
          <ul>
            {blocked.map((b) => (
              <li key={b.path}>
                {b.path} — {b.reason}
              </li>
            ))}
          </ul>
        </details>
      )}

      {pending ? (
        <div className="approval__actions">
          <button type="button" className="approval__go" onClick={() => onDecide(true)} disabled={disabled || items.length === 0}>
            Mover {formatCount(items.length)} {items.length === 1 ? 'item' : 'itens'} para a Lixeira
          </button>
          <button type="button" className="approval__no" onClick={() => onDecide(false)} disabled={disabled}>
            Cancelar
          </button>
        </div>
      ) : (
        <p className="approval__result">{status === 'approved' ? '✓ Aprovado — itens enviados para a Lixeira.' : '✕ Cancelado — nada foi apagado.'}</p>
      )}
      {pending && <p className="approval__note">Dá para restaurar pela {lixeira}.</p>}
    </div>
  );
}

function AgentMessage({ message, onDecide, busy, lixeira }) {
  const { steps, text, status, error, approval } = message;
  return (
    <div className="msg msg--agent">
      <div className="msg__tag">
        <span className={`msg__pulse${status === 'done' || status === 'error' ? ' is-idle' : ''}${status === 'waiting' ? ' is-waiting' : ''}`} />
        {status === 'waiting' ? 'agente · aguardando sua confirmação' : 'agente'}
      </div>

      {steps.length > 0 && (
        <ol className="trace">
          {steps.map((s, i) => (
            <li key={i} className={`trace__step trace__step--${s.type}`}>
              {s.type === 'action' ? <b>▸ {STEP_LABEL[s.type]}:</b> : `${STEP_LABEL[s.type]}:`} {s.text}
            </li>
          ))}
        </ol>
      )}

      {status === 'thinking' && steps.length === 0 && <p className="msg__text msg__text--dim">Pensando…</p>}
      {text && (
        <p className="msg__text msg__text--rich">
          <RichText text={text.trim()} />
          {status === 'answering' && <span className="msg__caret" aria-hidden="true" />}
        </p>
      )}
      {approval && <ApprovalCard approval={approval} onDecide={onDecide} disabled={busy} lixeira={lixeira} />}
      {error && <p className="msg__error">{error}</p>}
    </div>
  );
}

export default function ChatThread({ messages, onReset, onDecide, busy, lixeira = 'Lixeira' }) {
  const scrollRef = useRef(null);
  const stickRef = useRef(true); // follow new content only while the user is at the bottom
  const [unread, setUnread] = useState(false);

  // Scroll the thread itself (never the page): long answers stay inside the card.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (stickRef.current) {
      el.scrollTop = el.scrollHeight;
      setUnread(false);
    } else {
      setUnread(true);
    }
  }, [messages]);

  const onScroll = () => {
    const el = scrollRef.current;
    stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < STICK_PX;
    if (stickRef.current) setUnread(false);
  };

  const jumpToEnd = () => {
    const el = scrollRef.current;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    stickRef.current = true;
    setUnread(false);
  };

  return (
    <section className="chat-thread hud-frame" aria-label="Conversa com o agente">
      <header className="chat-thread__head">
        <span>Conversa · ReAct</span>
        <button type="button" onClick={onReset}>
          ← resumo do PC
        </button>
      </header>

      <div className="chat-thread__scroll" ref={scrollRef} onScroll={onScroll} aria-live="polite">
        {messages.map((m) =>
          m.role === 'user' ? (
            <div key={m.id} className="msg msg--user">
              <p className="msg__text">{m.text}</p>
            </div>
          ) : (
            <AgentMessage key={m.id} message={m} onDecide={onDecide} busy={busy} lixeira={lixeira} />
          )
        )}
      </div>

      {unread && (
        <button type="button" className="chat-thread__jump" onClick={jumpToEnd}>
          ↓ nova resposta
        </button>
      )}
    </section>
  );
}
