import { useState } from 'react';
import './ConfigChave.css';
import './ConfigLicenca.css';

// "Licença" (desktop menu). The CleanChain is complete and free for everyone; a license (one-time
// payment) only hides the occasional invite and shows "Licensed to <name>". The key is checked
// offline by the Electron main process (Ed25519 signature) and never leaves this computer.
const mensagem = (err, padrao) => err?.message?.replace(/^Error invoking remote method '[^']+': (Error: )?/, '') || padrao;

export default function ConfigLicenca({ licenca, onRegistrar, onRemover, onFechar }) {
  const [chave, setChave] = useState('');
  const [estado, setEstado] = useState('idle'); // idle | salvando | erro
  const [erro, setErro] = useState('');

  const registrar = async (e) => {
    e.preventDefault();
    if (!chave.trim()) return;
    setEstado('salvando');
    setErro('');
    try {
      await onRegistrar(chave.trim());
      setChave('');
      setEstado('idle');
    } catch (err) {
      setEstado('erro');
      setErro(mensagem(err, 'Não consegui registrar a chave.'));
    }
  };

  return (
    <section className="config-chave config-licenca hud-frame" aria-labelledby="config-licenca-titulo">
      <p className="panel-head">
        <span id="config-licenca-titulo">Licença</span>
        {onFechar && (
          <button type="button" className="link-btn" onClick={onFechar}>
            fechar
          </button>
        )}
      </p>

      {licenca?.licenciado ? (
        <>
          <p className="config-licenca__selo" role="status">
            ✓ Licenciado para <strong>{licenca.nome}</strong>
          </p>
          <p className="start-scan__desc">Obrigado por apoiar o CleanChain! O convite para comprar não aparece mais.</p>
          <div className="config-chave__actions">
            <button type="button" className="config-chave__no" onClick={onRemover}>
              Remover licença deste computador
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="start-scan__desc">
            O CleanChain é <strong>completo e gratuito</strong>, sem prazo e sem recursos bloqueados. Se ele te ajuda, compre uma
            licença (pagamento único): o convite deixa de aparecer e o app mostra o seu nome.
          </p>
          <div className="config-chave__actions">
            <a
              className="config-chave__go config-licenca__comprar"
              href={licenca?.paginaDeCompra}
              target="_blank"
              rel="noreferrer"
            >
              Comprar uma licença
            </a>
          </div>

          <form className="config-chave__form" onSubmit={registrar}>
            <label className="config-chave__label" htmlFor="config-licenca-campo">
              Já comprou? Cole a sua chave (CC1-…)
            </label>
            <textarea
              id="config-licenca-campo"
              className="config-chave__input config-licenca__campo"
              rows={3}
              spellCheck="false"
              placeholder="CC1-…"
              value={chave}
              onChange={(e) => setChave(e.target.value)}
              disabled={estado === 'salvando'}
            />
            {estado === 'erro' && (
              <p className="start-scan__error" role="alert">
                {erro}
              </p>
            )}
            <div className="config-chave__actions">
              <button type="submit" className="config-chave__go" disabled={!chave.trim() || estado === 'salvando'}>
                {estado === 'salvando' ? 'Conferindo…' : 'Registrar licença'}
              </button>
            </div>
          </form>
        </>
      )}

      <p className="config-chave__note">A chave é conferida neste computador e não é enviada a lugar nenhum.</p>
    </section>
  );
}
