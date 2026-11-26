import './ConfigChave.css';
import './ConfigLicenca.css';

// Occasional invite (WinRAR model): after 30 days of use, at most once a week, when the app
// opens — never during a scan, a chat or a cleanup. One click closes it for a week; nothing is
// blocked either way.
export default function ConviteLicenca({ paginaDeCompra, onVerLicenca, onFechar }) {
  return (
    <section className="config-chave config-licenca hud-frame" aria-labelledby="convite-licenca-titulo">
      <p className="panel-head">
        <span id="convite-licenca-titulo">Apoie o CleanChain</span>
        <button type="button" className="link-btn" onClick={onFechar} aria-label="Fechar o convite">
          agora não
        </button>
      </p>
      <p className="start-scan__desc">
        Você usa o CleanChain há mais de um mês. Ele continua <strong>completo e gratuito</strong>; se ele te ajuda a manter o
        computador leve, considere comprar uma licença (pagamento único). Com ela, este convite não aparece mais.
      </p>
      <div className="config-chave__actions">
        <a
          className="config-chave__go config-licenca__comprar"
          href={paginaDeCompra}
          target="_blank"
          rel="noreferrer"
          onClick={onFechar}
        >
          Comprar uma licença
        </a>
        <button type="button" className="config-chave__no" onClick={onVerLicenca}>
          Já tenho uma chave
        </button>
      </div>
    </section>
  );
}
