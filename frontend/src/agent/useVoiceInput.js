import { useCallback, useEffect, useRef, useState } from 'react';

const MAX_SECONDS = 60;

function pickMimeType() {
  const options = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
  return options.find((t) => window.MediaRecorder?.isTypeSupported?.(t)) ?? '';
}

// Push-to-talk: record from the mic, send to POST /api/transcribe (Whisper), hand back text.
// status: idle | recording | transcribing | error
export function useVoiceInput(onText) {
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0); // 0..1, live mic level for the meter

  const recRef = useRef(null);
  const discardRef = useRef(false);
  const cleanupRef = useRef(() => {});
  const onTextRef = useRef(onText);
  onTextRef.current = onText;

  const cleanup = () => {
    cleanupRef.current();
    cleanupRef.current = () => {};
  };

  useEffect(() => () => {
    discardRef.current = true;
    recRef.current?.state === 'recording' && recRef.current.stop();
    cleanup();
  }, []);

  const transcribe = async (blob) => {
    setStatus('transcribing');
    try {
      const form = new FormData();
      const ext = blob.type.includes('ogg') ? 'ogg' : blob.type.includes('mp4') ? 'm4a' : 'webm';
      form.append('audio', blob, `fala.${ext}`);
      const res = await fetch('/api/transcribe', { method: 'POST', body: form });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `erro ${res.status}`);
      if (body.text) onTextRef.current?.(body.text);
      else throw new Error('Não entendi o áudio. Tente de novo, mais perto do microfone.');
      setStatus('idle');
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  const start = useCallback(async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError('Este navegador não suporta gravação de áudio.');
      setStatus('error');
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      setError('Permita o acesso ao microfone para falar com o agente.');
      setStatus('error');
      return;
    }

    const mimeType = pickMimeType();
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    const chunks = [];
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    recorder.onstop = () => {
      cleanup();
      if (discardRef.current) {
        setStatus('idle');
        return;
      }
      transcribe(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }));
    };

    // Live level meter + timer (+ auto-stop at MAX_SECONDS).
    const ctx = new AudioContext();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const buf = new Uint8Array(analyser.fftSize);
    let raf = 0;
    const t0 = performance.now();
    const tick = () => {
      analyser.getByteTimeDomainData(buf);
      let peak = 0;
      for (const v of buf) peak = Math.max(peak, Math.abs(v - 128));
      setLevel(Math.min(1, peak / 64));
      const s = (performance.now() - t0) / 1000;
      setSeconds(s);
      if (s >= MAX_SECONDS && recorder.state === 'recording') recorder.stop();
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    cleanupRef.current = () => {
      cancelAnimationFrame(raf);
      stream.getTracks().forEach((t) => t.stop());
      ctx.close().catch(() => {});
      setLevel(0);
    };

    discardRef.current = false;
    recRef.current = recorder;
    recorder.start();
    setSeconds(0);
    setStatus('recording');
  }, []);

  const stop = useCallback(() => {
    if (recRef.current?.state === 'recording') recRef.current.stop();
  }, []);

  const cancel = useCallback(() => {
    discardRef.current = true;
    if (recRef.current?.state === 'recording') recRef.current.stop();
    else setStatus('idle');
    setError(null);
  }, []);

  return { status, error, seconds, level, start, stop, cancel, dismissError: () => (setError(null), setStatus('idle')) };
}
