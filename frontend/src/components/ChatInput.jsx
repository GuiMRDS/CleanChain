import { useEffect, useRef, useState } from 'react';
import { suggestions } from '../agent/suggestions.js';
import { useVoiceInput } from '../agent/useVoiceInput.js';
import './ChatInput.css';

const BARS = 7;
const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

export default function ChatInput({ onSend, busy, locked = false, showSuggestions = true, vozDisponivel = true }) {
  const [text, setText] = useState('');
  const fieldRef = useRef(null);

  // Voice → text: the transcript lands in the field so the user can review it before sending.
  const voice = useVoiceInput((spoken) => {
    setText((t) => (t.trim() ? `${t.trim()} ${spoken}` : spoken));
    requestAnimationFrame(() => fieldRef.current?.focus());
  });
  const recording = voice.status === 'recording';
  const transcribing = voice.status === 'transcribing';

  const { cancel: cancelVoice, stop: stopVoice } = voice;
  useEffect(() => {
    if (!recording) return;
    const onKey = (e) => {
      if (e.key === 'Escape') cancelVoice();
      if (e.key === 'Enter') {
        e.preventDefault();
        stopVoice();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [recording, cancelVoice, stopVoice]);

  const submit = (value) => {
    if (busy || locked || !value.trim()) return;
    onSend(value);
    setText('');
  };

  const placeholder = locked
    ? 'Confirme ou cancele a limpeza acima para continuar'
    : transcribing
      ? 'Transcrevendo sua fala…'
      : busy
        ? 'O agente está analisando…'
        : vozDisponivel
          ? 'Pergunte ao agente… ou fale com ele'
          : 'Pergunte ao agente…';

  return (
    <div className="chat-input">
      <form
        className={`capsule${recording ? ' is-recording' : ''}${transcribing ? ' is-transcribing' : ''}`}
        onSubmit={(e) => {
          e.preventDefault();
          submit(text);
        }}
      >
        <span className="capsule__spark" aria-hidden="true">✦</span>

        {recording ? (
          <div className="voice" role="status" aria-live="polite">
            <span className="voice__dot" aria-hidden="true" />
            <span className="voice__time">{clock(voice.seconds)}</span>
            <span className="voice__bars" aria-hidden="true">
              {Array.from({ length: BARS }, (_, i) => {
                const shape = 1 - Math.abs(i - (BARS - 1) / 2) / BARS; // taller in the middle
                return <i key={i} style={{ transform: `scaleY(${0.15 + voice.level * shape * (0.7 + 0.3 * Math.sin(voice.seconds * 9 + i))})` }} />;
              })}
            </span>
            <span className="voice__hint">ouvindo… Enter para concluir · Esc cancela</span>
          </div>
        ) : (
          <input
            ref={fieldRef}
            className="capsule__field"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={placeholder}
            aria-label="Mensagem para o agente"
            autoComplete="off"
            disabled={transcribing || locked}
          />
        )}

        <button
          type="button"
          className={`capsule__icon capsule__mic${recording ? ' is-on' : ''}`}
          onClick={recording ? voice.stop : voice.start}
          disabled={transcribing || locked || !vozDisponivel}
          aria-label={!vozDisponivel ? 'Voz desligada com a IA local' : recording ? 'Parar e transcrever' : 'Falar com o agente'}
          title={
            !vozDisponivel
              ? 'Com a IA local, a voz fica desligada: nada sai deste computador.'
              : recording
                ? 'Parar e transcrever'
                : 'Falar com o agente'
          }
          aria-pressed={recording}
        >
          {transcribing ? (
            <span className="capsule__spinner" aria-hidden="true" />
          ) : recording ? (
            <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
              <rect x="6" y="6" width="12" height="12" rx="2.5" fill="currentColor" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
              <rect x="9" y="3" width="6" height="12" rx="3" />
              <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
            </svg>
          )}
        </button>
        <button type="submit" className="capsule__send" aria-label="Enviar" disabled={busy || recording || transcribing || !text.trim()}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </button>
      </form>

      {voice.status === 'error' && (
        <p className="voice__error" role="alert">
          {voice.error}
          <button type="button" className="link-btn" onClick={voice.dismissError}>
            ok
          </button>
        </p>
      )}

      {showSuggestions && (
        <div className="suggestions">
          {suggestions.map((s) => (
            <button key={s} type="button" className="suggestion" onClick={() => submit(s)} disabled={busy || locked}>
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
