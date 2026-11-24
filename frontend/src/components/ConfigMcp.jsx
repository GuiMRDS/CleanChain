import { useState } from 'react';
import './ConfigChave.css';
import './ConfigMcp.css';

// "Integração MCP" (desktop menu): turn the MCP server on/off (off by default), show the
// executable path and copy ready-made configs for the most common MCP clients.
const CLIENTES = [
  { id: 'claude-desktop', nome: 'Claude Desktop', dica: 'Cole em claude_desktop_config.json' },
  { id: 'claude-code', nome: 'Claude Code', dica: 'Rode o comando no terminal' },
  { id: 'cursor', nome: 'Cursor', dica: 'Cole em ~/.cursor/mcp.json' },
];

export default function ConfigMcp({ mcp, onDefinir, onCopiar, onFechar }) {
  const [salvando, setSalvando] = useState(false);
  const [copiado, setCopiado] = useState(null);
  const ativo = Boolean(mcp?.ativo);

  const alternar = async () => {
    setSalvando(true);
    try {
      await onDefinir(!ativo);
    } finally {
      setSalvando(false);
    }
  };

  const copiar = async (id) => {
    await onCopiar(id);
    setCopiado(id);
    setTimeout(() => setCopiado((c) => (c === id ? null : c)), 2000);
  };

  const dica = CLIENTES.find((c) => c.id === copiado)?.dica;

  return (
    <section className="config-chave config-mcp hud-frame" aria-labelledby="config-mcp-titulo">
      <p className="panel-head">
        <span id="config-mcp-titulo">Integração MCP</span>
        {onFechar && (
          <button type="button" className="link-btn" onClick={onFechar}>
            ✕ fechar
          </button>
        )}
      </p>
      <p className="start-scan__desc">
        Outros assistentes (Claude, Cursor, VS Code…) consultam suas análises e <b>propõem</b> limpezas. Eles nunca
        apagam nada: cada proposta aparece aqui e só você aprova.
      </p>

      <button
        type="button"
        role="switch"
        aria-checked={ativo}
        className={`config-mcp__switch${ativo ? ' is-on' : ''}`}
        onClick={alternar}
        disabled={salvando || !mcp}
      >
        <span className="config-mcp__trilho" aria-hidden="true">
          <span />
        </span>
        {ativo ? 'Servidor MCP ligado' : 'Servidor MCP desligado'}
      </button>

      <label className="config-chave__label" htmlFor="config-mcp-exe">
        Executável (stdio)
      </label>
      <input id="config-mcp-exe" name="executavel" className="config-chave__input" readOnly value={mcp?.executavel ?? '…'} title={mcp?.executavel} />
      {mcp && !mcp.instalado && <p className="start-scan__error">O executável não foi encontrado: reinstale o CleanChain.</p>}
      {mcp?.aviso && <p className="start-scan__error">{mcp.aviso}</p>}

      <p className="config-chave__label">Copiar configuração</p>
      <div className="config-mcp__clientes">
        {CLIENTES.map((c) => (
          <button key={c.id} type="button" className="config-chave__no" onClick={() => copiar(c.id)} disabled={!mcp} title={c.dica}>
            {copiado === c.id ? '✓ copiado' : `⧉ ${c.nome}`}
          </button>
        ))}
      </div>

      <p className="config-chave__note">
        {dica ? `${dica} e reinicie o cliente.` : ativo ? 'Com o app aberto, os clientes configurados já enxergam o CleanChain.' : 'Desligado: o CleanChain recusa qualquer conexão MCP.'}
      </p>
    </section>
  );
}
