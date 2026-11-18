import { bytesLabel, formatBytes, formatCount, fileName } from '../agent/format.js';
import './ScanCard.css';

// Result of the real disk scan: total analysed, largest files, size per top folder.
export default function ScanCard({ scan, onRescan }) {
  const { value, unit } = formatBytes(scan.total_bytes ?? 0);
  const folders = (scan.tree.children ?? []).filter((c) => c.bytes > 0);
  const maxFolder = Math.max(1, ...folders.map((c) => c.bytes));

  return (
    <section className="scan-card hud-frame" aria-label="Resultado do scan">
      <header className="panel-head">
        <span>Espaço analisado</span>
        <button type="button" className="link-btn" onClick={onRescan}>
          ↻ novo scan
        </button>
      </header>

      <div className="scan-card__body">
        <p className="scan-card__value">
          {value}
          <small>{unit}</small>
        </p>

        <ol className="react-log" aria-label="Maiores arquivos">
          {scan.largest_files.slice(0, 3).map((f, i) => (
            <li key={f.path} className={i ? 'react-log__dim' : undefined} title={f.path}>
              {i === 0 && <b>▸ maior: </b>}
              {fileName(f.path)} · {f.bytes != null ? bytesLabel(f.bytes) : f.size}
            </li>
          ))}
        </ol>
      </div>

      <div className="scan-card__bars" role="img" aria-label="Tamanho das maiores pastas">
        {folders.map((c, i) => (
          <i key={c.name} className={i === 0 ? 'is-blue' : undefined} style={{ '--h': `${Math.max(6, (c.bytes / maxFolder) * 100)}%`, '--d': `${i * 40}ms` }} title={`${c.name} · ${bytesLabel(c.bytes)}`} />
        ))}
      </div>

      <ul className="scan-card__chips">
        <li className="chip">
          <strong>{formatCount(scan.files_scanned)}</strong> arquivos
        </li>
        <li className="chip">
          <strong>{scan.seconds}s</strong> de scan
        </li>
        {scan.partial ? (
          <li className="chip is-warn" title="O scan atingiu o tempo limite; os números são parciais.">
            parcial
          </li>
        ) : (
          <li className="chip">
            <i style={{ background: 'var(--green)' }} />
            completo
          </li>
        )}
      </ul>
    </section>
  );
}
