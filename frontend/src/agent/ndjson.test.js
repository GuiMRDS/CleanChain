// Leitor do stream NDJSON: o contrato de eventos do chat (invariante 5 do AGENTS.md).
import { afterEach, describe, expect, it, vi } from 'vitest';
import { postNdjson } from './ndjson.js';

/** Resposta do fetch com o corpo chegando nos pedaços dados (como na rede). */
function resposta(pedacos, { status = 200 } = {}) {
  const enc = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      for (const p of pedacos) controller.enqueue(enc.encode(p));
      controller.close();
    },
  });
  return new Response(body, { status });
}

afterEach(() => vi.unstubAllGlobals());

describe('postNdjson', () => {
  it('entrega cada evento, mesmo partido entre pedaços da rede', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => resposta(['{"type":"act', 'ion","text":"a"}\n{"type":"answ', 'er","text":"oi"}\n'])));
    const eventos = [];
    await postNdjson('/api/chat', { message: 'x' }, (e) => eventos.push(e));
    expect(eventos).toEqual([
      { type: 'action', text: 'a' },
      { type: 'answer', text: 'oi' },
    ]);
  });

  it('entrega a última linha sem quebra no fim e ignora linhas vazias', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => resposta(['\n{"type":"ui","command":"focus_folder"}\n\n', '{"type":"done","awaiting_approval":false}'])));
    const eventos = [];
    await postNdjson('/api/chat', {}, (e) => eventos.push(e));
    expect(eventos.map((e) => e.type)).toEqual(['ui', 'done']);
  });

  it('manda o corpo em JSON por POST', async () => {
    const fetch = vi.fn(async () => resposta(['']));
    vi.stubGlobal('fetch', fetch);
    await postNdjson('/api/chat/approval', { thread_id: 't', approve: true }, () => {});
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe('/api/chat/approval');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ thread_id: 't', approve: true });
  });

  it('erro HTTP vira mensagem clara', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => resposta([''], { status: 401 })));
    await expect(postNdjson('/api/chat', {}, () => {})).rejects.toThrow('erro 401');
  });

  it('backend fora do ar vira mensagem clara; cancelamento continua sendo cancelamento', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))));
    await expect(postNdjson('/api/chat', {}, () => {})).rejects.toThrow('Não consegui conectar ao backend');
    const abort = Object.assign(new Error('aborted'), { name: 'AbortError' });
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(abort)));
    await expect(postNdjson('/api/chat', {}, () => {})).rejects.toBe(abort);
  });
});
