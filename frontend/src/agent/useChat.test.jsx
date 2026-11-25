// Fluxo do chat e da aprovação humana no useChat (o backend é simulado pelo fetch).
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useChat } from './useChat.js';

const linhas = (...eventos) => eventos.map((e) => JSON.stringify(e)).join('\n') + '\n';

/** fetch simulado: cada chamada devolve o próximo corpo NDJSON da fila e registra o pedido. */
function backend(...respostas) {
  const pedidos = [];
  const fetch = vi.fn(async (url, init) => {
    pedidos.push({ url, corpo: JSON.parse(init.body) });
    return new Response(respostas.shift() ?? linhas({ type: 'done', awaiting_approval: false }));
  });
  vi.stubGlobal('fetch', fetch);
  return pedidos;
}

beforeEach(() => vi.stubGlobal('crypto', { randomUUID: () => 'conversa-1' }));
afterEach(() => vi.unstubAllGlobals());

const agente = (result) => result.current.messages.find((m) => m.role === 'agent');

describe('useChat', () => {
  it('monta a mensagem do agente com os passos e a resposta, e manda a pasta aberta', async () => {
    const pedidos = backend(
      linhas(
        { type: 'action', id: 'c1', text: 'read_last_scan()' },
        { type: 'observation', text: 'scan: 10 GB' },
        { type: 'answer', text: 'Seus vídeos ' },
        { type: 'answer', text: 'ocupam 6 GB.' },
        { type: 'done', awaiting_approval: false }
      )
    );
    const { result } = renderHook(() => useChat({ getUiState: () => ({ open_folder: 'C:\\Videos' }) }));
    await act(() => result.current.send('onde foi meu espaço?'));

    expect(pedidos[0]).toEqual({ url: '/api/chat', corpo: { message: 'onde foi meu espaço?', thread_id: 'conversa-1', ui_state: { open_folder: 'C:\\Videos' } } });
    const msg = agente(result);
    expect(msg.steps.map((s) => s.type)).toEqual(['action', 'observation']);
    expect(msg.text).toBe('Seus vídeos ocupam 6 GB.');
    expect(msg.status).toBe('done');
    expect(result.current.busy).toBe(false);
  });

  it('comandos de tela vão para onUi', async () => {
    backend(linhas({ type: 'ui', command: 'focus_folder', args: { path: 'C:\\Videos' } }, { type: 'done' }));
    const onUi = vi.fn();
    const { result } = renderHook(() => useChat({ onUi }));
    await act(() => result.current.send('abre os vídeos'));
    expect(onUi).toHaveBeenCalledWith({ type: 'ui', command: 'focus_folder', args: { path: 'C:\\Videos' } });
  });

  it('com uma exclusão aguardando aprovação, não aceita mensagem nova', async () => {
    const pedidos = backend(
      linhas({ type: 'action', id: 'c2', text: 'delete_files(...)' }, { type: 'approval', items: [{ path: 'a.iso' }] }, { type: 'done', awaiting_approval: true })
    );
    const { result } = renderHook(() => useChat());
    await act(() => result.current.send('apaga a.iso'));

    expect(result.current.awaitingApproval).toBe(true);
    expect(agente(result).approval.status).toBe('pending');
    expect(agente(result).status).toBe('waiting');
    await act(() => result.current.send('outra coisa'));
    expect(pedidos).toHaveLength(1); // nada foi enviado
  });

  it.each([
    [true, 'approved'],
    [false, 'rejected'],
  ])('decidir (%s) retoma o agente pela rota de aprovação', async (aprovar, estado) => {
    const pedidos = backend(
      linhas({ type: 'approval', items: [{ path: 'a.iso' }] }, { type: 'done', awaiting_approval: true }),
      linhas({ type: 'action', id: 'c2', text: 'delete_files(...)' }, { type: 'answer', text: 'Pronto.' }, { type: 'done', awaiting_approval: false })
    );
    const { result } = renderHook(() => useChat());
    await act(() => result.current.send('apaga a.iso'));
    await act(() => result.current.decide(aprovar));

    expect(pedidos[1]).toEqual({ url: '/api/chat/approval', corpo: { thread_id: 'conversa-1', approve: aprovar } });
    expect(agente(result).approval.status).toBe(estado);
    expect(result.current.awaitingApproval).toBe(false);
    expect(agente(result).text).toContain('Pronto.');
  });

  it('decidir sem nada pendente não faz nada', async () => {
    const pedidos = backend();
    const { result } = renderHook(() => useChat());
    await act(() => result.current.decide(true));
    expect(pedidos).toHaveLength(0);
  });

  it('erro do backend aparece na mensagem do agente', async () => {
    backend(linhas({ type: 'error', text: 'O modelo atingiu o limite de uso por minuto.' }, { type: 'done' }));
    const { result } = renderHook(() => useChat());
    await act(() => result.current.send('oi'));
    expect(agente(result).status).toBe('error');
    expect(agente(result).error).toContain('limite de uso');
  });
});
