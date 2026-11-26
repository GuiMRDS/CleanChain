import { useCallback, useEffect, useRef, useState } from 'react';

export const UI_STEP_MS = 900; // gap between agent screen commands, so each transition is visible

// The agent's focus_folder calls arrive as 'ui' events; they're queued and applied one by one,
// UI_STEP_MS apart, so the user sees each folder open. `comando` is what the sunburst follows.
// limpar(): a new scan starts from a clean map (drop pending and last commands).
export function useFilaDeTela() {
  const [comando, setComando] = useState(null);
  const filaRef = useRef([]);
  const timerRef = useRef(null);

  // Named function: it schedules itself for the next command.
  const drenar = useCallback(function proximoComando() {
    const proximo = filaRef.current.shift();
    if (!proximo) {
      timerRef.current = null;
      return;
    }
    setComando({ seq: Date.now() + Math.random(), path: proximo.args?.path });
    timerRef.current = setTimeout(proximoComando, UI_STEP_MS);
  }, []);

  const receber = useCallback(
    (evento) => {
      if (evento.command !== 'focus_folder') return;
      filaRef.current.push(evento);
      if (!timerRef.current) drenar();
    },
    [drenar]
  );

  const limpar = useCallback(() => {
    filaRef.current = [];
    clearTimeout(timerRef.current);
    timerRef.current = null;
    setComando(null);
  }, []);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  return { comando, receber, limpar };
}
