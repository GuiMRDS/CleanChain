import { bytesLabel, formatBytes, formatCount, fileName } from '../agent/format.js';
import './ScanCard.css';

// Cleanup opportunities found by the scan → shortcuts that ask the agent about them.
function opportunities(insights) {
  if (!insights) return [];
  const list = [
    {
      id: 'caches',
      label: 'Caches',
      bytes: insights.reclaimable_total,
      ask: 'Quais caches e temporários eu posso limpar com segurança?',
    },
    {
      id: 'dups',
      label: 'Duplicados',
      bytes: insights.duplicates?.wasted_total ?? 0,
      ask: 'Me mostre os arquivos duplicados que posso apagar.',
    },
    {
      id: 'old',
      label: 'Esquecidos',
      bytes: insights.old_files?.total_bytes ?? 0,
      ask: 'Quais arquivos grandes estão esquecidos há mais de um ano?',
    },
  ];
  return list.filter((o) => o.bytes > 0);
}

// Result of the real disk scan: total analysed, largest files, size per top folder,
// and what could be freed (each opportunity opens a chat with the agent about it).
export default function ScanCard({ scan, onRescan, onAsk }) {
  const ops = opportunities(scan.insights);
  const savings = scan.insights?.estimated_savings ?? 0;
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
          <i
            key={c.name}
            className={i === 0 ? 'is-blue' : undefined}
            style={{ '--h': `${Math.max(6, (c.bytes / maxFolder) * 100)}%`, '--d': `${i * 40}ms` }}
            title={`${c.name} · ${bytesLabel(c.bytes)}`}
          />
        ))}
      </div>

      {ops.length > 0 && (
        <div className="scan-card__savings">
          <p>
            Pode liberar <b>~{bytesLabel(savings + (scan.insights.old_files?.total_bytes ?? 0))}</b>
          </p>
          <ul className="scan-card__chips">
            {ops.map((o) => (
              <li key={o.id}>
                <button
                  type="button"
                  className="chip chip--action"
                  onClick={() => onAsk?.(o.ask)}
                  title={`Perguntar ao agente: ${o.ask}`}
                >
                  {o.label} <strong>{bytesLabel(o.bytes)}</strong> <span aria-hidden="true">→</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="scan-card__meta">
        {formatCount(scan.files_scanned)} arquivos · {scan.seconds}s ·{' '}
        {scan.partial ? <span className="is-warn">parcial</span> : <span className="is-ok">completo</span>}
      </p>
    </section>
  );
}
