import { systemStats } from '../agent/mockData.js';
import './SystemFooter.css';

export default function SystemFooter() {
  return (
    <footer className="system-footer">
      {systemStats.map((s) => (
        <div key={s.id} className="stat">
          <span>{s.label}</span>
          <div className="stat__meter" aria-hidden="true">
            <div style={{ width: `${s.ratio * 100}%` }} />
          </div>
          <b>{s.value}</b>
        </div>
      ))}
      <span className="system-footer__spacer" />
      <span className="system-footer__tag">ReAct · langchain</span>
    </footer>
  );
}
