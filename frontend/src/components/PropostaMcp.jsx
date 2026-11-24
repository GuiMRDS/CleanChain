import { ApprovalCard } from './ChatThread.jsx';
import './PropostaMcp.css';

// A cleanup proposal from an MCP client (Claude Desktop, Cursor…), shown with the same approval
// card as the chat plus the "Proposta via MCP: <client>" badge. Nothing is deleted until the
// user clicks here; the backend revalidates every item before sending it to the Trash.
const ESTADO_CARTAO = { pendente: 'pending', aprovada: 'approved', recusada: 'rejected', expirada: 'rejected' };

function minutos(s) {
  const m = Math.max(1, Math.round((s ?? 0) / 60));
  return `${m} min`;
}

export default function PropostaMcp({ proposta, ultima, restantes, decidindo, onDecide, onFechar, lixeira }) {
  const p = proposta ?? ultima;
  if (!p) return null;
  const pendente = Boolean(proposta);
  const aprovacao = {
    items: p.itens ?? [],
    blocked: [],
    total_bytes: p.total_bytes ?? 0,
    reason: p.motivo,
    status: ESTADO_CARTAO[p.estado] ?? 'rejected',
  };

  return (
    <section className="proposta-mcp hud-frame" aria-labelledby="proposta-mcp-titulo">
      <p className="panel-head">
        <span id="proposta-mcp-titulo">Proposta de limpeza</span>
        <span className="mono">
          {pendente ? `expira em ${minutos(p.expira_em_s)}` : p.estado}
          {pendente && restantes > 0 ? ` · +${restantes} na fila` : ''}
        </span>
      </p>
      <div className="proposta-mcp__corpo">
        <ApprovalCard
          approval={aprovacao}
          selo={`Proposta via MCP: ${p.cliente || 'cliente MCP'}`}
          lixeira={lixeira}
          disabled={decidindo === p.id}
          onDecide={(aprovar) => onDecide(p.id, aprovar)}
        />
        {!pendente && p.resultado && (
          <p className="proposta-mcp__resultado">
            {p.resultado.deleted?.length ?? 0} item(ns) na Lixeira · {p.resultado.freed} liberados
            {p.resultado.skipped?.length ? ` · ${p.resultado.skipped.length} ignorado(s) na revalidação` : ''}
          </p>
        )}
        {!pendente && p.estado === 'erro' && <p className="start-scan__error">{p.erro}</p>}
      </div>
      <p className="proposta-mcp__nota">
        Um programa conectado ao CleanChain pelo MCP sugeriu esta limpeza. Ele não consegue apagar nada: só você
        decide, aqui.
      </p>
      {!pendente && (
        <button type="button" className="link-btn" onClick={onFechar}>
          fechar
        </button>
      )}
    </section>
  );
}
