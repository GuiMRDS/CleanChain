import { bytesLabel, formatCount } from '../agent/format.js';
import './AgentStatus.css';

// Top-right pill reflecting what the agent is doing right now.
// Priority: chat reasoning > disk scan > scan result > idle.
export default function AgentStatus({ scan, thinking, currentTool, awaitingApproval }) {
  let state;
  if (awaitingApproval) {
    state = { kind: 'error', label: 'agente pausado ·', detail: 'aguardando sua confirmação' };
  } else if (thinking) {
    state = { kind: 'thinking', label: 'agente pensando', detail: currentTool ? `▸ ${currentTool}` : 'raciocinando…' };
  } else if (scan.phase === 'scanning') {
    state = {
      kind: 'scanning',
      label: 'agente ativo · analisando',
      detail: scan.progress?.current ?? scan.root ?? '…',
      isPath: true,
      extra: `${formatCount(scan.progress?.files ?? 0)} arq.`,
    };
  } else if (scan.phase === 'done') {
    state = { kind: 'idle', label: 'agente ativo · scan concluído ·', detail: `${bytesLabel(scan.result.total_bytes)} analisados` };
  } else if (scan.phase === 'error') {
    state = { kind: 'error', label: 'scan interrompido ·', detail: 'tente de novo' };
  } else {
    state = { kind: 'ready', label: 'agente pronto ·', detail: 'aguardando scan' };
  }

  return (
    <div className={`agent-status is-${state.kind}`} role="status" aria-live="polite">
      <span className="agent-status__dot" aria-hidden="true" />
      <span className="agent-status__label">{state.label}</span>
      <span className={`agent-status__detail${state.isPath ? ' is-path' : ''}`} key={state.kind}>
        {state.detail}
      </span>
      {state.extra && <span className="agent-status__pct">{state.extra}</span>}
      {state.kind === 'scanning' && (
        <span className="agent-status__bar is-indeterminate" aria-hidden="true">
          <span />
        </span>
      )}
    </div>
  );
}
