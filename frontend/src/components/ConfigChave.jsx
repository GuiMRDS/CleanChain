import { useCallback, useEffect, useState } from 'react';
import './StartScan.css';
import './ConfigChave.css';

// First run of the desktop app (and menu "Modelo de IA"): choose where the agent's model runs.
// - Cloud (Groq/OpenAI): paste the API key. It goes straight to the Electron main process
//   (window.cleanchain), which encrypts it with safeStorage; it never stays in the UI.
// - Local (Ollama/LM Studio on this computer): pick an installed model. Nothing leaves the PC.
// Either way the main process restarts the backend and the window reloads.
const PROVEDORES = [
  { id: 'groq', badge: 'GQ', title: 'Groq', tag: 'nuvem · gratuito', prefix: 'gsk_', link: 'https://console.groq.com/keys' },
  {
    id: 'openai',
    badge: 'AI',
    title: 'OpenAI',
    tag: 'nuvem · pago',
    prefix: 'sk-',
    link: 'https://platform.openai.com/api-keys',
  },
  {
    id: 'ollama',
    badge: 'OL',
    title: 'Ollama',
    tag: 'local · privado',
    local: true,
    porta: 11434,
    link: 'https://ollama.com/download',
  },
  {
    id: 'lmstudio',
    badge: 'LM',
    title: 'LM Studio',
    tag: 'local · privado',
    local: true,
    porta: 1234,
    link: 'https://lmstudio.ai',
  },
];

const mensagem = (err, padrao) => err?.message?.replace(/^Error invoking remote method '[^']+': (Error: )?/, '') || padrao;

export default function ConfigChave({ atual, onSalvar, onUsarLocal, onUsarNuvem, onModelosLocais, onCancelar }) {
  const [provedor, setProvedor] = useState(atual?.provedor ?? 'groq');
  const [chave, setChave] = useState('');
  const [estado, setEstado] = useState('idle'); // idle | salvando | erro
  const [erro, setErro] = useState('');
  const escolhido = PROVEDORES.find((p) => p.id === provedor) ?? PROVEDORES[0];
  // Linux without a keyring (GNOME Keyring/KWallet): a cloud key can't be stored safely.
  const semCofre = atual?.cofre === false;

  // --- Local AI: port + installed models -------------------------------------------------
  const localAtual = atual?.local?.provedor === provedor ? atual.local : null;
  const [porta, setPorta] = useState(localAtual?.porta ?? escolhido.porta ?? '');
  const [modelos, setModelos] = useState(null); // null = not loaded; [] = none installed
  // Opened on a local provider: it starts already "searching" (the effect below lists the models).
  const [buscando, setBuscando] = useState(Boolean(escolhido.local));
  const [modelo, setModelo] = useState(localAtual?.modelo ?? '');

  // Asks the local server for its models; the state only changes when the answer arrives.
  const buscarModelos = useCallback(
    (id, p) =>
      onModelosLocais(id, Number(p))
        .then((lista) => {
          setModelos(lista);
          setModelo((m) => (lista.some((x) => x.nome === m) ? m : (lista.find((x) => x.ferramentas !== false)?.nome ?? '')));
        })
        .catch((err) => {
          setModelos(null);
          setEstado('erro');
          setErro(mensagem(err, 'Não consegui falar com o servidor local.'));
        })
        .finally(() => setBuscando(false)),
    [onModelosLocais]
  );

  const procurar = (id, p) => {
    setBuscando(true);
    setErro('');
    setEstado('idle');
    return buscarModelos(id, p);
  };

  const escolher = (p) => {
    setProvedor(p.id);
    setErro('');
    setEstado('idle');
    setModelos(null);
    if (p.local) {
      const anterior = atual?.local?.provedor === p.id ? atual.local : null;
      const novaPorta = anterior?.porta ?? p.porta;
      setPorta(novaPorta);
      setModelo(anterior?.modelo ?? '');
      procurar(p.id, novaPorta);
    }
  };

  // Opened on a local provider (menu → Modelo de IA): list its models right away.
  useEffect(() => {
    if (escolhido.local) buscarModelos(escolhido.id, porta);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on open
  }, []);

  const executar = async (acao) => {
    setEstado('salvando');
    setErro('');
    try {
      await acao();
      setChave(''); // the app reloads with the new backend; nothing stays in memory here
    } catch (err) {
      setEstado('erro');
      setErro(mensagem(err, 'Não consegui conectar.'));
    }
  };

  const salvar = (e) => {
    e.preventDefault();
    if (escolhido.local) {
      if (modelo) executar(() => onUsarLocal(provedor, modelo, Number(porta)));
    } else if (chave.trim()) {
      executar(() => onSalvar(provedor, chave.trim()));
    }
  };

  // Cloud key already saved for this provider, but a local AI is active: switch back without retyping.
  const podeVoltarParaNuvem =
    !escolhido.local && atual?.ativo !== 'nuvem' && atual?.nuvemConfigurada && atual?.provedorNuvem === provedor;
  const modeloEscolhido = modelos?.find((m) => m.nome === modelo);
  const salvando = estado === 'salvando';

  return (
    <section className="config-chave hud-frame" aria-labelledby="config-chave-titulo">
      <p className="panel-head">
        <span id="config-chave-titulo">Conectar o agente</span>
        <span className="mono">{atual?.configurada ? 'trocar modelo' : 'primeiro uso'}</span>
      </p>
      <p className="start-scan__desc">
        O agente conversa por um modelo de linguagem: na nuvem, com a sua chave de API, ou numa IA instalada neste computador.
      </p>

      <form className="config-chave__form" onSubmit={salvar}>
        <div className="targets config-chave__provedores" role="radiogroup" aria-label="Onde o modelo roda">
          {PROVEDORES.map((p) => (
            <button
              key={p.id}
              type="button"
              role="radio"
              aria-checked={p.id === provedor}
              className={`target${p.id === provedor ? ' is-selected' : ''}`}
              onClick={() => escolher(p)}
              disabled={salvando}
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

        {escolhido.local ? (
          <>
            <div className="config-chave__label">
              <span>
                Modelo instalado no {escolhido.title} · porta{' '}
                <input
                  className="config-chave__porta"
                  aria-label="Porta do servidor local"
                  inputMode="numeric"
                  value={porta}
                  onChange={(e) => setPorta(e.target.value.replace(/\D/g, '').slice(0, 5))}
                  onBlur={() => porta && procurar(provedor, porta)}
                  disabled={salvando}
                />
              </span>
              <a href={escolhido.link} target="_blank" rel="noreferrer">
                instalar o {escolhido.title}
              </a>
            </div>

            {buscando ? (
              <p className="config-chave__note">Procurando modelos em 127.0.0.1:{porta}…</p>
            ) : modelos?.length === 0 ? (
              <p className="start-scan__error" role="alert">
                O {escolhido.title} está aberto, mas não tem nenhum modelo. Baixe um que use ferramentas (por exemplo, Qwen 3 ou
                Llama 3.1) e clique em procurar de novo.
              </p>
            ) : modelos ? (
              <div className="config-chave__modelos" role="radiogroup" aria-label="Modelo local">
                {modelos.map((m) => (
                  <label
                    key={m.nome}
                    className={`config-chave__modelo${m.nome === modelo ? ' is-selected' : ''}${m.ferramentas === false ? ' is-off' : ''}`}
                  >
                    <input
                      type="radio"
                      name="modelo-local"
                      value={m.nome}
                      checked={m.nome === modelo}
                      onChange={() => setModelo(m.nome)}
                      disabled={salvando || m.ferramentas === false}
                    />
                    <span className="config-chave__modelo-nome">{m.nome}</span>
                    <em>
                      {m.ferramentas === true ? 'usa ferramentas' : m.ferramentas === false ? 'sem ferramentas' : 'não informa'}
                    </em>
                  </label>
                ))}
              </div>
            ) : null}

            {modeloEscolhido?.ferramentas === null && (
              <p className="config-chave__note">
                O {escolhido.title} não informa se este modelo sabe usar ferramentas. Se o agente não conseguir abrir pastas nem
                propor limpezas, escolha outro.
              </p>
            )}
          </>
        ) : (
          <>
            <label className="config-chave__label" htmlFor="config-chave-campo">
              {podeVoltarParaNuvem
                ? `Chave de API (${escolhido.prefix}…) — já salva; cole outra só para trocar`
                : `Chave de API (${escolhido.prefix}…)`}
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
              disabled={salvando}
            />
            {semCofre && (
              <p className="start-scan__error" role="alert">
                {atual.motivoCofre}
              </p>
            )}
          </>
        )}

        {estado === 'erro' && (
          <p className="start-scan__error" role="alert">
            {erro}
          </p>
        )}

        <div className="config-chave__actions">
          {escolhido.local ? (
            <>
              <button type="submit" className="config-chave__go" disabled={!modelo || buscando || salvando}>
                {salvando ? 'Conectando…' : 'Usar este modelo'}
              </button>
              <button
                type="button"
                className="config-chave__no"
                onClick={() => procurar(provedor, porta)}
                disabled={buscando || salvando || !porta}
              >
                Procurar de novo
              </button>
            </>
          ) : podeVoltarParaNuvem && !chave.trim() ? (
            <button type="button" className="config-chave__go" onClick={() => executar(onUsarNuvem)} disabled={salvando}>
              {salvando ? 'Conectando…' : `Voltar para ${escolhido.title}`}
            </button>
          ) : (
            <button type="submit" className="config-chave__go" disabled={semCofre || !chave.trim() || salvando}>
              {salvando ? 'Conectando…' : 'Salvar e conectar'}
            </button>
          )}
          {onCancelar && (
            <button type="button" className="config-chave__no" onClick={onCancelar} disabled={salvando}>
              Cancelar
            </button>
          )}
        </div>
      </form>

      <p className="config-chave__note">
        {escolhido.local
          ? `Tudo roda neste computador: a conversa e a análise não saem daqui. O microfone fica desligado (a transcrição de voz é na nuvem).`
          : 'A chave fica criptografada neste computador e só é usada pelo CleanChain.'}{' '}
        Trocar o modelo reinicia o agente e começa uma conversa nova.
      </p>
    </section>
  );
}
