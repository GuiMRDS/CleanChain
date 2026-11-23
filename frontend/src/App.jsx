import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import HeroIntro from './components/HeroIntro.jsx';
import StartScan from './components/StartScan.jsx';
import ScanCard from './components/ScanCard.jsx';
import Sunburst from './components/Sunburst.jsx';
import FileTypesChart from './components/FileTypesChart.jsx';
import ChatThread from './components/ChatThread.jsx';
import ChatInput from './components/ChatInput.jsx';
import SystemFooter from './components/SystemFooter.jsx';
import AgentStatus from './components/AgentStatus.jsx';
import ConfigChave from './components/ConfigChave.jsx';
import DesktopMenu from './components/DesktopMenu.jsx';
import { useChat } from './agent/useChat.js';
import { useDesktop } from './agent/useDesktop.js';
import { useScan } from './agent/useScan.js';
import { useDrives } from './agent/useDrives.js';
import { bytesLabel, formatCount } from './agent/format.js';
import './App.css';

// Three.js (~600 KB) loads in its own chunk: the UI paints first, the 3D scene fades in.
const AgentScene = lazy(() => import('./components/AgentScene.jsx'));

const GREETINGS = {
  idle: 'Oi! Escolha um disco e eu faço um raio-x completo dele.',
  setup: 'Oi! Antes de começar, me conecte a um modelo de linguagem.',
  error: 'Não consegui terminar o scan. Vamos tentar de novo?',
};

// Scan targets for the picker: every local disk (whole drive, deep scan) + the home folder.
function buildTargets(drives, home) {
  const list = drives.map((d) => ({
    path: d.root,
    badge: d.letter,
    title: d.label,
    tag: d.system ? 'sistema' : d.kind === 'removível' ? 'removível' : null,
    short: d.short ?? `${d.letter} inteiro`,
    total: d.total,
    used: d.used,
    free: d.free,
  }));
  if (home) list.push({ path: home, badge: '~', title: 'Minha pasta', tag: 'mais rápido', short: 'minha pasta' });
  return list;
}

const UI_STEP_MS = 900; // gap between agent screen commands, so each transition is visible

export default function App() {
  const scan = useScan();
  const desktop = useDesktop(); // Electron only: LLM key setup (first run / menu)

  // --- Agent ⇄ screen -------------------------------------------------------
  // The agent's focus_folder calls arrive as 'ui' events; they're queued and applied
  // one by one. The open folder goes back to the agent with every message.
  const [sunburstCommand, setSunburstCommand] = useState(null);
  const openFolderRef = useRef(null);
  const queueRef = useRef([]);
  const timerRef = useRef(null);

  const drainQueue = useCallback(() => {
    const next = queueRef.current.shift();
    if (!next) {
      timerRef.current = null;
      return;
    }
    setSunburstCommand({ seq: Date.now() + Math.random(), path: next.args?.path });
    timerRef.current = setTimeout(drainQueue, UI_STEP_MS);
  }, []);

  const handleUi = useCallback(
    (event) => {
      if (event.command !== 'focus_folder') return;
      queueRef.current.push(event);
      if (!timerRef.current) drainQueue();
    },
    [drainQueue]
  );

  useEffect(() => () => clearTimeout(timerRef.current), []);

  // A new scan starts from a clean map: drop pending/last agent commands.
  useEffect(() => {
    if (scan.phase !== 'scanning') return;
    queueRef.current = [];
    clearTimeout(timerRef.current);
    timerRef.current = null;
    setSunburstCommand(null);
  }, [scan.phase]);

  const handleFolderChange = useCallback((path) => {
    openFolderRef.current = path;
  }, []);

  const { messages, busy, send, reset, decide, awaitingApproval } = useChat({
    onUi: handleUi,
    getUiState: () => ({ open_folder: openFolderRef.current }),
  });
  const cardsRowRef = useRef(null);
  const chatting = messages.length > 0;
  const scanned = scan.phase === 'done' && scan.result;

  // Disk picker: defaults to the system disk.
  const { drives, home, status: drivesStatus, plataforma } = useDrives();
  const targets = useMemo(() => buildTargets(drives, home), [drives, home]);
  const [target, setTarget] = useState(null);
  const chosen = targets.find((t) => t.path === target) ?? targets.find((t) => t.tag === 'sistema') ?? targets[0];

  // Latest tool call of the agent message currently being produced.
  const live = busy ? messages.at(-1) : null;
  const currentTool = live?.steps.findLast((s) => s.type === 'action')?.text;

  const greeting = desktop.precisaChave
    ? GREETINGS.setup
    : scanned
      ? `Pronto! ${formatCount(scan.result.files_scanned)} arquivos analisados (${bytesLabel(scan.result.total_bytes)}).`
      : scan.phase === 'scanning'
        ? `Escaneando ${chosen?.short ?? 'seus arquivos'}… pode levar alguns minutos.`
        : GREETINGS[scan.phase] ?? GREETINGS.idle;

  const mainCard = desktop.mostrarConfig ? (
    <ConfigChave atual={desktop.chave} onSalvar={desktop.salvarChave} onCancelar={desktop.fecharConfig} />
  ) : chatting ? (
    <ChatThread messages={messages} onReset={reset} onDecide={decide} busy={busy} lixeira={plataforma.lixeira} />
  ) : scanned ? (
    <ScanCard scan={scan.result} onRescan={scan.choose} onAsk={send} />
  ) : (
    <StartScan
      phase={scan.phase}
      progress={scan.progress}
      error={scan.error}
      targets={targets}
      targetsStatus={drivesStatus}
      target={chosen?.path}
      onTarget={setTarget}
      onStart={scan.start}
      onCancel={scan.cancel}
    />
  );

  return (
    <main className="app">
      <Suspense fallback={null}>
        <AgentScene clearOfRef={cardsRowRef} />
      </Suspense>

      {desktop.desktop && <div className="desktop-drag" aria-hidden="true" />}

      <header className="brand">
        <span className="brand__mark" aria-hidden="true" />
        cleanchain
      </header>

      <AgentStatus scan={scan} thinking={busy} currentTool={currentTool} awaitingApproval={awaitingApproval} />
      {desktop.desktop && <DesktopMenu desktop={desktop} />}

      <section className={`left${chatting ? ' is-chatting' : ''}`}>
        <HeroIntro compact={chatting} greeting={greeting} titulo={plataforma.titulo} />
        {/* Main card + scan charts share one row, vertically centred together. */}
        <div className="insights-row" ref={cardsRowRef}>
          {mainCard}
          {scanned && (
            <div className="insights-side">
              <Sunburst
                scan={scan.result}
                command={sunburstCommand}
                onFolderChange={handleFolderChange}
                ignoraMaiusculas={plataforma.ignora_maiusculas}
              />
              <FileTypesChart byType={scan.result.by_type} totalBytes={scan.result.total_bytes} />
            </div>
          )}
        </div>
        <ChatInput onSend={send} busy={busy} locked={awaitingApproval} showSuggestions={!chatting} />
      </section>

      <SystemFooter refreshKey={`${scan.result?.file ?? ''}:${busy}`} />
    </main>
  );
}
