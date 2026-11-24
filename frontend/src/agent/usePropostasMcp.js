import { useCallback, useEffect, useState } from 'react';

// Cleanup proposals from MCP clients (GET /api/propostas, cookie-authenticated like the rest of
// the UI). The Electron app pings us (window.cleanchain.aoPropostaMcp) when one arrives; a slow
// poll keeps expirations in sync. Deciding = POST /api/propostas/{id}/decisao — only the user,
// here in the app, can approve; the backend revalidates every item before the Trash.
const POLL_MS = 15000;
const bridge = typeof window !== 'undefined' ? window.cleanchain : undefined;

export function usePropostasMcp() {
  const [propostas, setPropostas] = useState([]);
  const [decidindo, setDecidindo] = useState(null); // id being decided
  const [ultima, setUltima] = useState(null); // last decided proposal (result card)

  const carregar = useCallback(async () => {
    try {
      const r = await fetch('/api/propostas');
      if (r.ok) setPropostas((await r.json()).propostas ?? []);
    } catch {
      /* backend restarting: try again on the next tick */
    }
  }, []);

  useEffect(() => {
    if (!bridge) return undefined; // MCP only exists in the desktop app
    carregar();
    const parar = bridge.aoPropostaMcp?.(() => carregar());
    const t = setInterval(carregar, POLL_MS);
    return () => {
      parar?.();
      clearInterval(t);
    };
  }, [carregar]);

  const decidir = useCallback(
    async (id, aprovar) => {
      setDecidindo(id);
      try {
        const r = await fetch(`/api/propostas/${encodeURIComponent(id)}/decisao`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ aprovar }),
        });
        const corpo = await r.json().catch(() => ({}));
        setUltima(r.ok ? corpo : { id, estado: 'erro', erro: corpo.detail ?? 'Não consegui registrar a decisão.' });
      } finally {
        setDecidindo(null);
        carregar();
      }
    },
    [carregar]
  );

  return { atual: propostas[0] ?? null, restantes: Math.max(0, propostas.length - 1), decidindo, decidir, ultima, fecharUltima: () => setUltima(null) };
}
