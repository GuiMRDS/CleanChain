import { bytesLabel, formatCount } from '../agent/format.js';
import './StartScan.css';

// Entry point of the app: pick a disk (or the home folder) and hit the "Start scan" orb.
// While scanning, the same panel turns into live progress (with % for whole disks) + cancel.
export default function StartScan({ phase, progress, error, targets, targetsStatus, target, onTarget, onStart, onCancel }) {
  const scanning = phase === 'scanning';
  const current = targets.find((t) => t.path === target) ?? targets[0];
  const pct = progress?.pct;

  return (
    <section className={`start-scan hud-frame${scanning ? ' is-scanning' : ''}`} aria-live="polite">
      <button type="button" className="orb" onClick={() => onStart(current?.path)} disabled={scanning || !current} aria-label={scanning ? 'Scan em andamento' : `Start scan em ${current?.title ?? ''}`}>
        <span className="orb__halo" aria-hidden="true" />
        <span className="orb__ring" aria-hidden="true" />
        <span className="orb__core">
          {scanning ? (
            <>
              <strong className="orb__time">{pct != null ? `${Math.floor(pct)}%` : `${Math.floor(progress?.seconds ?? 0)}s`}</strong>
              <small>{pct != null ? `${Math.floor(progress?.seconds ?? 0)}s` : 'analisando'}</small>
            </>
          ) : (
            <>
              <svg className="orb__icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
                <circle cx="11" cy="11" r="6.5" />
                <path d="M16 16l4.5 4.5" />
                <path d="M8.5 11h5M11 8.5v5" opacity="0.55" />
              </svg>
              <strong>Start scan</strong>
              <small>{current ? current.short : '…'}</small>
            </>
          )}
        </span>
      </button>

      <div className="start-scan__info">
        {scanning ? (
          <>
            <p className="panel-head">
              <span>Mapeando {current?.short ?? 'arquivos'}</span>
              <button type="button" className="link-btn" onClick={onCancel}>
                ✕ cancelar
              </button>
            </p>
            <p className="start-scan__count">
              {formatCount(progress?.files ?? 0)}
              <small>arquivos · {bytesLabel(progress?.bytes ?? 0)}</small>
            </p>
            <p className="start-scan__path" title={progress?.current ?? ''}>
              <b>▸</b>
              <span>{progress?.current ?? 'iniciando…'}</span>
            </p>
            <div className={`start-scan__track${pct != null ? ' is-determinate' : ''}`} aria-hidden="true">
              <div style={pct != null ? { transform: `scaleX(${pct / 100})` } : undefined} />
            </div>
          </>
        ) : (
          <>
            <p className="panel-head">
              <span>O que analisar</span>
              <span className="mono">scan profundo</span>
            </p>
            {targets.length === 0 && (
              <p className={`targets__empty${targetsStatus === 'error' ? ' is-error' : ''}`} role="status">
                {targetsStatus === 'error'
                  ? 'Não consegui falar com o backend. Ele está rodando? (cd backend · uv run uvicorn app.server:app --port 8000) — tentando de novo…'
                  : 'Procurando os discos…'}
              </p>
            )}
            <div className="targets" role="radiogroup" aria-label="Disco para analisar">
              {targets.map((t) => (
                <button
                  key={t.path}
                  type="button"
                  role="radio"
                  aria-checked={t.path === current?.path}
                  className={`target${t.path === current?.path ? ' is-selected' : ''}`}
                  onClick={() => onTarget(t.path)}
                  title={t.path}
                >
                  <span className="target__badge">{t.badge}</span>
                  <span className="target__body">
                    <span className="target__title">
                      {t.title}
                      {t.tag && <em>{t.tag}</em>}
                    </span>
                    {t.total ? (
                      <>
                        <span className="target__meter" aria-hidden="true">
                          <span style={{ width: `${Math.round((t.used / t.total) * 100)}%` }} className={t.used / t.total > 0.9 ? 'is-full' : undefined} />
                        </span>
                        <span className="target__meta">
                          {bytesLabel(t.free)} livres de {bytesLabel(t.total)}
                        </span>
                      </>
                    ) : (
                      <span className="target__meta">{t.path}</span>
                    )}
                  </span>
                </button>
              ))}
            </div>
            {error ? (
              <p className="start-scan__error">{error}</p>
            ) : (
              <p className="start-scan__desc">Somente leitura: nada é apagado nem movido. Um disco inteiro pode levar alguns minutos.</p>
            )}
          </>
        )}
      </div>
    </section>
  );
}
