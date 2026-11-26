import './ConfigLicenca.css';

// Optional license invite (WinRAR model): after 30 days of use, at most once a week, a slim strip
// above the scan card on the start screen. It never replaces a screen nor waits for an answer:
// scan, chat and the agent work exactly the same with or without a license. "agora não" hides it
// for a week.
export default function ConviteLicenca({ paginaDeCompra, onVerLicenca, onFechar }) {
  return (
    <aside className="convite-licenca hud-frame" aria-label="Apoie o CleanChain">
      <p className="convite-licenca__texto">
        <strong>Gostando do CleanChain?</strong> Ele continua completo e gratuito. Se quiser apoiar, a licença é opcional
        (pagamento único).
      </p>
      <div className="convite-licenca__acoes">
        <a className="link-btn" href={paginaDeCompra} target="_blank" rel="noreferrer" onClick={onFechar}>
          apoiar
        </a>
        <button type="button" className="link-btn" onClick={onVerLicenca}>
          tenho uma chave
        </button>
        <button type="button" className="link-btn" onClick={onFechar} aria-label="Fechar o convite">
          agora não
        </button>
      </div>
    </aside>
  );
}
