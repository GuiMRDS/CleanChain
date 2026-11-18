import { useMemo, useState } from 'react';
import { bytesLabel, percentages } from '../agent/format.js';
import './FileTypesChart.css';

const SIZE = 172;
const STROKE = 22;
const R = (SIZE - STROKE) / 2;
const C = 2 * Math.PI * R;
const GAP = 2; // surface gap between slices (px along the circumference)

// Fixed colour per file type (validated palette); every other type folds into "Outros".
const TYPES = [
  { id: 'videos', label: 'Vídeos', color: '#2a78d6' },
  { id: 'instaladores', label: 'Instaladores', color: '#e5489a' },
  { id: 'imagens', label: 'Imagens', color: '#6250d6' },
  { id: 'documentos', label: 'Documentos', color: '#1baf7a' },
];
const OTHER = { id: 'outros', label: 'Outros', color: '#b4b9c4' };

// byType: scan.by_type from the backend → [{ type, bytes, size, pct }]
function toItems(byType) {
  const bytesOf = (id) => byType.find((t) => t.type === id)?.bytes ?? 0;
  const named = TYPES.map((t) => ({ ...t, bytes: bytesOf(t.id) })).filter((t) => t.bytes > 0);
  const known = new Set(TYPES.map((t) => t.id));
  const rest = byType.filter((t) => !known.has(t.type));
  const restBytes = rest.reduce((sum, t) => sum + t.bytes, 0);
  const hint = rest
    .filter((t) => t.bytes > 0)
    .slice(0, 4)
    .map((t) => t.type.replaceAll('_', ' '))
    .join(', ');
  return restBytes > 0 ? [...named, { ...OTHER, bytes: restBytes, hint }] : named;
}

export default function FileTypesChart({ byType, totalBytes }) {
  const [active, setActive] = useState(null);

  const slices = useMemo(() => {
    const items = toItems(byType);
    const total = items.reduce((a, b) => a + b.bytes, 0) || 1;
    const pcts = percentages(items.map((i) => i.bytes));
    let offset = 0;
    return items.map((item, i) => {
      const len = (item.bytes / total) * C;
      const slice = { ...item, size: bytesLabel(item.bytes), pct: pcts[i], dash: Math.max(0, len - GAP), offset, delay: i * 90 };
      offset += len;
      return slice;
    });
  }, [byType]);

  const focus = slices.find((s) => s.id === active);

  return (
    <section className="filetypes hud-frame" aria-labelledby="filetypes-title">
      <header className="panel-head">
        <span id="filetypes-title">Tipos de arquivo</span>
        <span>{bytesLabel(totalBytes)}</span>
      </header>

      <div className="filetypes__chart" onPointerLeave={() => setActive(null)}>
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label="Uso do disco por tipo de arquivo">
          <g transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}>
            <circle className="filetypes__track" cx={SIZE / 2} cy={SIZE / 2} r={R} strokeWidth={STROKE} />
            {slices.map((s) => (
              <circle
                key={s.id}
                className={`filetypes__slice${active && active !== s.id ? ' is-dim' : ''}${active === s.id ? ' is-active' : ''}`}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={R}
                stroke={s.color}
                strokeWidth={STROKE}
                strokeDasharray={`${s.dash} ${C - s.dash}`}
                strokeDashoffset={-s.offset}
                style={{ '--len': s.dash, '--c': C, animationDelay: `${s.delay}ms` }}
                onPointerEnter={() => setActive(s.id)}
              >
                <title>{`${s.label}: ${s.size} (${s.pct}%)`}</title>
              </circle>
            ))}
          </g>
        </svg>

        <div className="filetypes__center" aria-hidden="true">
          <strong>{focus ? `${focus.pct}%` : slices.length}</strong>
          <span>{focus ? focus.label : 'tipos'}</span>
        </div>
      </div>

      <ul className="filetypes__legend">
        {slices.map((s) => (
          <li
            key={s.id}
            className={active && active !== s.id ? 'is-dim' : undefined}
            onPointerEnter={() => setActive(s.id)}
            onPointerLeave={() => setActive(null)}
            title={s.hint}
          >
            <i style={{ background: s.color }} aria-hidden="true" />
            <span className="filetypes__name">{s.label}</span>
            <span className="filetypes__gb">{s.size}</span>
            <b className="filetypes__pct">{s.pct}%</b>
          </li>
        ))}
      </ul>
    </section>
  );
}
