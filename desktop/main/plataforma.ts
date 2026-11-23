// Tudo o que muda por sistema no lado Electron, num lugar só (como backend/app/plataforma).
// O resto do processo principal não testa process.platform.
import { ChildProcess, execFile } from 'node:child_process';
import { app, BrowserWindowConstructorOptions, MenuItemConstructorOptions, safeStorage, systemPreferences } from 'electron';
import log from 'electron-log/main';

const logPlat = log.scope('plataforma');

export type Sistema = 'windows' | 'macos' | 'linux';
export const SISTEMA: Sistema = process.platform === 'win32' ? 'windows' : process.platform === 'darwin' ? 'macos' : 'linux';

const ESPERA_SIGTERM_MS = 5000;

// ------------------------------------------------------------------ backend

/** Nome do executável do backend gerado pelo PyInstaller. */
export const EXECUTAVEL_BACKEND = SISTEMA === 'windows' ? 'cleanchain-backend.exe' : 'cleanchain-backend';

/**
 * Opções de spawn do backend. Fora do Windows ele nasce num grupo de processos próprio
 * (detached), para o encerramento alcançar também os filhos.
 */
export const OPCOES_SPAWN = { windowsHide: true, detached: SISTEMA !== 'windows' } as const;

function saiu(proc: ChildProcess, ms: number): Promise<boolean> {
  if (proc.exitCode !== null || proc.signalCode !== null) return Promise.resolve(true);
  return new Promise((resolve) => {
    const t = setTimeout(() => resolve(false), ms);
    proc.once('exit', () => {
      clearTimeout(t);
      resolve(true);
    });
  });
}

function sinalNoGrupo(pid: number, sinal: NodeJS.Signals): void {
  try {
    process.kill(-pid, sinal); // o grupo inteiro (pid negativo)
  } catch {
    try {
      process.kill(pid, sinal);
    } catch {
      /* já tinha saído */
    }
  }
}

/**
 * Encerra o backend e todos os filhos dele.
 * Windows: a árvore de processos com taskkill /T /F.
 * macOS e Linux: SIGTERM no grupo e, se não sair em 5 s, SIGKILL.
 */
export async function encerrarArvore(proc: ChildProcess): Promise<void> {
  const pid = proc.pid;
  if (pid === undefined) return;
  if (SISTEMA === 'windows') {
    await new Promise<void>((resolve) => execFile('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true }, () => resolve()));
    await saiu(proc, ESPERA_SIGTERM_MS);
    return;
  }
  sinalNoGrupo(pid, 'SIGTERM');
  if (!(await saiu(proc, ESPERA_SIGTERM_MS))) {
    logPlat.warn('o backend não saiu com SIGTERM; enviando SIGKILL');
    sinalNoGrupo(pid, 'SIGKILL');
    await saiu(proc, 2000);
  }
}

// ------------------------------------------------------------------ janela

/** Barra de título integrada ao design (ver frontend/src/components/DesktopMenu.css). */
export function opcoesDeJanela(): BrowserWindowConstructorOptions {
  if (SISTEMA === 'macos') {
    // Botões do macOS à esquerda, na mesma linha do cabeçalho; a interface desvia deles.
    return { titleBarStyle: 'hiddenInset', trafficLightPosition: { x: 18, y: 20 } };
  }
  return { titleBarStyle: 'hidden', titleBarOverlay: { height: 56, color: '#00000000', symbolColor: '#3a4152' } };
}

/** No macOS o app continua ativo sem janelas (o Dock reabre); nos outros, fechar encerra. */
export const FECHAR_JANELA_ENCERRA = SISTEMA !== 'macos';

/**
 * Menu nativo. Windows/Linux: invisível, só atalhos (as ações ficam no menu do app).
 * macOS: o menu do app é obrigatório, e o menu Editar é o que faz Cmd+C/V funcionarem.
 */
export function menuNativo(): MenuItemConstructorOptions[] {
  const exibir: MenuItemConstructorOptions = {
    label: 'Exibir',
    submenu: [
      { role: 'resetZoom', label: 'Tamanho original' },
      { role: 'zoomIn', label: 'Aumentar' },
      { role: 'zoomIn', accelerator: 'CommandOrControl+=', visible: false },
      { role: 'zoomOut', label: 'Diminuir' },
      { type: 'separator' },
      { role: 'togglefullscreen', label: 'Tela cheia' },
      ...(app.isPackaged ? [] : ([{ type: 'separator' }, { role: 'reload' }, { role: 'toggleDevTools' }] as MenuItemConstructorOptions[])),
    ],
  };
  if (SISTEMA !== 'macos') return [exibir];
  return [
    {
      label: 'CleanChain',
      submenu: [
        { role: 'about', label: 'Sobre o CleanChain' },
        { type: 'separator' },
        { role: 'hide', label: 'Ocultar CleanChain' },
        { role: 'hideOthers', label: 'Ocultar outros' },
        { role: 'unhide', label: 'Mostrar tudo' },
        { type: 'separator' },
        { role: 'quit', label: 'Encerrar CleanChain' },
      ],
    },
    {
      label: 'Editar',
      submenu: [
        { role: 'undo', label: 'Desfazer' },
        { role: 'redo', label: 'Refazer' },
        { type: 'separator' },
        { role: 'cut', label: 'Recortar' },
        { role: 'copy', label: 'Copiar' },
        { role: 'paste', label: 'Colar' },
        { role: 'selectAll', label: 'Selecionar tudo' },
      ],
    },
    exibir,
    { role: 'windowMenu', label: 'Janela' },
  ];
}

// ------------------------------------------------------------------ chave do LLM

/**
 * O cofre do sistema protege de verdade a chave? Windows (DPAPI) e macOS (Keychain): sim.
 * Linux: só com libsecret/KWallet; sem eles o Electron usa "basic_text", uma senha fixa no
 * código — equivalente a texto puro. Nesse caso o app NÃO salva a chave (recurso desativado).
 */
export function cofreSeguro(): { ok: boolean; motivo?: string } {
  if (!safeStorage.isEncryptionAvailable()) {
    return { ok: false, motivo: 'A criptografia do sistema não está disponível.' };
  }
  if (SISTEMA === 'linux') {
    const backend = safeStorage.getSelectedStorageBackend();
    if (backend === 'basic_text' || backend === 'unknown') {
      return {
        ok: false,
        motivo: 'Nenhum cofre de senhas encontrado (GNOME Keyring ou KWallet). Instale um e abra o CleanChain de novo para guardar a chave com segurança.',
      };
    }
  }
  return { ok: true };
}

// ------------------------------------------------------------------ microfone

/** macOS: além da permissão do Chromium, o sistema precisa autorizar o microfone. */
export async function autorizarMicrofone(): Promise<boolean> {
  if (SISTEMA !== 'macos') return true;
  try {
    return await systemPreferences.askForMediaAccess('microphone');
  } catch {
    return false;
  }
}

// ------------------------------------------------------------------ atualização

/**
 * Como atualizar:
 *  - 'automatica': baixa e instala sozinho (Windows, AppImage no Linux);
 *  - 'manual': só avisa e abre a página de downloads. No macOS, o Squirrel.Mac exige app
 *    assinado pela Apple; no .deb, instalar pediria a senha de administrador.
 */
export function modoDeAtualizacao(): 'automatica' | 'manual' {
  if (SISTEMA === 'windows') return 'automatica';
  if (SISTEMA === 'linux' && process.env.APPIMAGE) return 'automatica';
  return 'manual';
}

export const PAGINA_DE_DOWNLOADS = 'https://github.com/GuiMRDS/CleanChain/releases/latest';
