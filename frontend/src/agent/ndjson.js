// POST JSON and read an NDJSON stream (one JSON event per line) from the backend.
// In dev, Vite proxies /api to http://127.0.0.1:8000 (see vite.config.js).

export async function postNdjson(url, body, onEvent, { signal } = {}) {
  let res;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new Error('Não consegui conectar ao backend. Ele está rodando? (cd backend · uv run uvicorn app.server:app --port 8000)');
  }
  if (!res.ok || !res.body) throw new Error(`O backend respondeu com erro ${res.status}.`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const flush = (line) => {
    if (line.trim()) onEvent(JSON.parse(line));
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let nl;
    while ((nl = buffer.indexOf('\n')) >= 0) {
      flush(buffer.slice(0, nl));
      buffer = buffer.slice(nl + 1);
    }
  }
  flush(buffer);
}
