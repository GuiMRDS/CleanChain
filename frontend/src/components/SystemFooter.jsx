import { bytesLabel } from '../agent/format.js';
import { useSystemStats } from '../agent/useSystemStats.js';
import './SystemFooter.css';

const pct = (used, total) => (total ? Math.round((used / total) * 100) : 0);

// Live machine status: system disk, RAM and the user's temp folder.
export default function SystemFooter({ refreshKey }) {
  const stats = useSystemStats(refreshKey);
  const disk = stats?.disk;
  const ram = stats?.memory;
  const temp = stats?.temp;

  const items = [
    {
      id: 'disk',
      label: disk ? `Disco ${disk.letter}` : 'Disco',
      ratio: disk ? disk.used / disk.total : 0,
      value: disk ? `${pct(disk.used, disk.total)}% · ${bytesLabel(disk.free)} livres` : '—',
      warn: disk && disk.used / disk.total > 0.9,
    },
    {
      id: 'ram',
      label: 'RAM',
      ratio: ram ? ram.used / ram.total : 0,
      value: ram ? `${bytesLabel(ram.used)} / ${bytesLabel(ram.total)}` : '—',
      warn: ram && ram.used / ram.total > 0.9,
    },
    {
      id: 'temp',
      label: 'Temporários',
      ratio: null,
      value: temp ? `${temp.partial ? '≥ ' : ''}${bytesLabel(temp.bytes)}` : '—',
    },
  ];

  return (
    <footer className="system-footer">
      {items.map((s) => (
        <div key={s.id} className="stat">
          <span>{s.label}</span>
          {s.ratio != null && (
            <div className="stat__meter" aria-hidden="true">
              <div className={s.warn ? 'is-warn' : undefined} style={{ width: `${Math.round(s.ratio * 100)}%` }} />
            </div>
          )}
          <b>{s.value}</b>
        </div>
      ))}
      <span className="system-footer__spacer" />
      <span className="system-footer__tag">ReAct · langchain</span>
    </footer>
  );
}
