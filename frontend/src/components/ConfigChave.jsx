import { useState } from 'react';
import './StartScan.css';
import './ConfigChave.css';

// First run of the desktop app (and menu "Configurar chave do LLM"): choose the provider and
// paste the API key. The key goes straight to the Electron main process (window.cleanchain),
// which encrypts it with safeStorage and restarts the backend; it never stays in the UI.
const PROVEDORES = [
  { id: 'groq', badge: 'GQ', title: 'Groq', tag: 'gratuito · rápido', prefix: 'gsk_', link: 'https://console.groq.com/keys' },
  { id: 'openai', badge: 'AI', title: 'OpenAI', tag: 'pago', prefix: 'sk-', link: 'https://platform.openai.com/api-keys' },
];

export default function ConfigChave({ atual, onSalvar, onCancelar }) {
  const [provedor, setProvedor] = useState(atual?.provedor ?? 'groq');
  const [chave, setChave] = useState('');
  const [estado, setEstado] = useState('idle'); // idle | salvando | erro
  const [erro, setErro] = useState('');
  const escolhido = PROVEDORES.find((p) => p.id === provedor);
  // Linux without a keyring (GNOME Keyring/KWallet): the key can't be stored safely, so saving is off.
  const semCofre = atual?.cofre === false;

  const salvar = async (e) => {
    e.preventDefault();
    const valor = chave.trim();
    if (!valor) return;
    setEstado('salvando');
    setErro('');
    try {
      await onSalvar(provedor, valor);
      setChave(''); // the app reloads with the new backend; nothing stays in memory here
    } catch (err) {
      setEstado('erro');
      setErro(err?.message?.replace(/^Error invoking remote method '[^']+': (Error: )?/, '') || 'Não consegui salvar a chave.');
    }
  };

  return (
    <section className="config-chave hud-frame" aria-labelledby="config-chave-titulo">
      <p className="panel-head">
        <span id="config-chave-titulo">Conectar o agente</span>
        <span className="mono">{atual?.configurada ? 'trocar chave' : 'primeiro uso'}</span>
      </p>
      <p className="start-scan__desc">
        O agente conversa por um modelo de linguagem. Escolha o provedor e cole a sua chave de API.
      </p>

      <form className="config-chave__form" onSubmit={salvar}>
        <div className="targets" role="radiogroup" aria-label="Provedor do modelo">
          {PROVEDORES.map((p) => (
            <button
              key={p.id}
              type="button"
              role="radio"
              aria-checked={p.id === provedor}
              className={`target${p.id === provedor ? ' is-selected' : ''}`}
              onClick={() => setProvedor(p.id)}
            >
              <span className="target__badge">{p.badge}</span>
              <span className="target__body">
                <span className="target__title">
                  {p.title}
                  <em>{p.tag}</em>
                </span>
              </span>
            </button>
          ))}
        </div>

        <label className="config-chave__label" htmlFor="config-chave-campo">
          Chave de API ({escolhido.prefix}…)
          <a href={escolhido.link} target="_blank" rel="noreferrer">
            onde consigo uma?
          </a>
        </label>
        <input
          id="config-chave-campo"
          name="chave"
          className="config-chave__input"
          type="password"
          autoComplete="off"
          spellCheck="false"
          placeholder={`${escolhido.prefix}…`}
          value={chave}
          onChange={(e) => setChave(e.target.value)}
          disabled={estado === 'salvando'}
        />

        {semCofre && <p className="start-scan__error" role="alert">{atual.motivoCofre}</p>}
        {estado === 'erro' && <p className="start-scan__error" role="alert">{erro}</p>}

        <div className="config-chave__actions">
          <button type="submit" className="config-chave__go" disabled={semCofre || !chave.trim() || estado === 'salvando'}>
            {estado === 'salvando' ? 'Conectando…' : 'Salvar e conectar'}
          </button>
          {onCancelar && (
            <button type="button" className="config-chave__no" onClick={onCancelar} disabled={estado === 'salvando'}>
              Cancelar
            </button>
          )}
        </div>
      </form>

      <p className="config-chave__note">
        A chave fica criptografada neste computador e só é usada pelo CleanChain. Trocar a chave reinicia o agente e
        começa uma conversa nova.
      </p>
    </section>
  );
}
