import { useEffect, useRef, useState } from 'react';
import './DesktopMenu.css';

// App menu of the desktop build (replaces the native "Arquivo / Exibir / Ajuda" bar): a glass
// chip next to the agent status that opens a HUD panel with the app actions.
const PROVEDOR = { groq: 'Groq', openai: 'OpenAI', ollama: 'Ollama (local)', lmstudio: 'LM Studio (local)' };

function textoAtualizacao(a) {
  switch (a?.estado) {
    case 'verificando':
      return 'verificando…';
    case 'atualizado':
      return 'você está na versão mais recente';
    case 'baixando':
      return `baixando a versão ${a.versao}…`;
    case 'pronta':
      return `versão ${a.versao} pronta para instalar`;
    case 'disponivel':
      return `versão ${a.versao} disponível para baixar`;
    case 'erro':
    case 'indisponivel':
      return a.mensagem;
    default:
      return 'verificar se há versão nova';
  }
}

export default function DesktopMenu({ desktop }) {
  const [aberto, setAberto] = useState(false);
  const raiz = useRef(null);
  const { chave, versao, atualizacao } = desktop;
  const pronta = atualizacao?.estado === 'pronta' || atualizacao?.estado === 'disponivel';
  const rotuloAtualizar = atualizacao?.estado === 'disponivel' ? 'Baixar a versão nova' : 'Reiniciar e atualizar';
  const alerta = pronta || desktop.precisaChave;

  useEffect(() => {
    if (!aberto) return undefined;
    const fora = (e) => raiz.current && !raiz.current.contains(e.target) && setAberto(false);
    const esc = (e) => e.key === 'Escape' && setAberto(false);
    document.addEventListener('pointerdown', fora);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('pointerdown', fora);
      document.removeEventListener('keydown', esc);
    };
  }, [aberto]);

  const acao = (fn) => () => {
    setAberto(false);
    fn();
  };

  return (
    <div className="desktop-menu" ref={raiz}>
      <button
        type="button"
        className={`desktop-menu__chip${aberto ? ' is-open' : ''}`}
        aria-label="Menu do CleanChain"
        aria-haspopup="menu"
        aria-expanded={aberto}
        onClick={() => setAberto((v) => !v)}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          aria-hidden="true"
        >
          <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
          <circle cx="16" cy="7" r="2" />
          <circle cx="8" cy="17" r="2" />
        </svg>
        {alerta && <span className="desktop-menu__dot" aria-hidden="true" />}
      </button>

      {aberto && (
        <div className="desktop-menu__panel hud-frame" role="menu" aria-label="CleanChain">
          <p className="panel-head">
            <span>CleanChain</span>
            <span className="mono">{versao ? `v${versao}` : ''}</span>
          </p>

          <button type="button" role="menuitem" className="desktop-menu__item" onClick={acao(desktop.abrirConfig)}>
            <span className="desktop-menu__icon" aria-hidden="true">
              ⚿
            </span>
            <span className="desktop-menu__text">
              <strong>Modelo de IA</strong>
              <small className={desktop.precisaChave ? 'is-warn' : undefined}>
                {chave?.configurada ? `${PROVEDOR[chave.provedor] ?? chave.provedor} · trocar` : 'não configurada · conectar'}
              </small>
            </span>
          </button>

          <button
            type="button"
            role="menuitem"
            className={`desktop-menu__item${pronta ? ' is-highlight' : ''}`}
            onClick={pronta ? desktop.instalarAtualizacao : desktop.verificarAtualizacoes}
            disabled={atualizacao?.estado === 'verificando' || atualizacao?.estado === 'indisponivel'}
          >
            <span className="desktop-menu__icon" aria-hidden="true">
              ↻
            </span>
            <span className="desktop-menu__text">
              <strong>{pronta ? rotuloAtualizar : 'Atualizações'}</strong>
              <small>{textoAtualizacao(atualizacao)}</small>
            </span>
          </button>

          <button type="button" role="menuitem" className="desktop-menu__item" onClick={acao(desktop.abrirMcp)}>
            <span className="desktop-menu__icon" aria-hidden="true">
              ⇄
            </span>
            <span className="desktop-menu__text">
              <strong>Integração MCP</strong>
              <small>{desktop.mcp?.ativo ? 'ligada · Claude, Cursor e outros' : 'desligada · conectar outros assistentes'}</small>
            </span>
          </button>

          <button type="button" role="menuitem" className="desktop-menu__item" onClick={acao(desktop.abrirLicenca)}>
            <span className="desktop-menu__icon" aria-hidden="true">
              ◈
            </span>
            <span className="desktop-menu__text">
              <strong>Licença</strong>
              <small>
                {desktop.licenca?.licenciado ? `licenciado para ${desktop.licenca.nome}` : 'versão gratuita · apoiar o projeto'}
              </small>
            </span>
          </button>

          <button type="button" role="menuitem" className="desktop-menu__item" onClick={acao(desktop.abrirLogs)}>
            <span className="desktop-menu__icon" aria-hidden="true">
              ▤
            </span>
            <span className="desktop-menu__text">
              <strong>Pasta de logs</strong>
              <small>para diagnosticar problemas</small>
            </span>
          </button>

          <p className="desktop-menu__note">Tudo roda neste computador; só as mensagens do chat vão ao provedor do modelo.</p>
        </div>
      )}
    </div>
  );
}
