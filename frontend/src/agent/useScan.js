import { useCallback, useEffect, useRef, useState } from 'react';
import { postNdjson } from './ndjson.js';

// Disk scan lifecycle: idle → scanning → done | error  (cancel → back to previous state).
// POST /api/scan streams { type: 'start', expected_bytes } → { type: 'progress', current, files,
// bytes, seconds, pct? }* → { type: 'result', scan } | { type: 'cancelled' } | { type: 'error', text }.
export function useScan() {
  const [phase, setPhase] = useState('idle');
  const [progress, setProgress] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [root, setRoot] = useState(null);
  const abortRef = useRef(null);
  const resultRef = useRef(null);
  resultRef.current = result;

  useEffect(() => () => abortRef.current?.abort(), []);

  const start = useCallback(async (path) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setPhase('scanning');
    setRoot(path ?? null);
    setProgress({ files: 0, bytes: 0, seconds: 0, current: null, pct: null });
    setError(null);

    try {
      let finished = false;
      await postNdjson(
        '/api/scan',
        path ? { path } : {},
        (event) => {
          if (event.type === 'start') setRoot(event.path);
          else if (event.type === 'progress') setProgress(event);
          else if (event.type === 'result') {
            finished = true;
            setResult(event.scan);
            setPhase('done');
          } else if (event.type === 'cancelled') {
            finished = true;
            setPhase(resultRef.current ? 'done' : 'idle');
          } else if (event.type === 'error') {
            finished = true;
            setError(event.text);
            setPhase('error');
          }
        },
        { signal: controller.signal }
      );
      if (!finished) throw new Error('O scan terminou sem resultado.');
    } catch (err) {
      if (err.name === 'AbortError') return;
      setError(err.message);
      setPhase('error');
    }
  }, []);

  // Stop the running scan (backend stops walking the disk; nothing is saved).
  const cancel = useCallback(() => {
    fetch('/api/scan/cancel', { method: 'POST' }).catch(() => {});
    abortRef.current?.abort();
    setPhase(resultRef.current ? 'done' : 'idle');
  }, []);

  // Back to the start screen to pick another disk (keeps the last result for cancel).
  const choose = useCallback(() => {
    setError(null);
    setPhase('idle');
  }, []);

  return { phase, progress, result, error, root, start, cancel, choose };
}
