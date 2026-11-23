// Atualização automática pelos GitHub Releases (só no app empacotado). O estado vai para a
// interface (menu do app), sem caixas de diálogo do Windows.
import { app } from 'electron';
import log from 'electron-log/main';
import { autoUpdater } from 'electron-updater';

const logAtu = log.scope('atualizacao');

export type EstadoAtualizacao =
  | { estado: 'indisponivel'; mensagem: string } // desenvolvimento
  | { estado: 'parado' }
  | { estado: 'verificando' }
  | { estado: 'atualizado'; versao: string }
  | { estado: 'baixando'; versao: string }
  | { estado: 'pronta'; versao: string }
  | { estado: 'erro'; mensagem: string };

let atual: EstadoAtualizacao = app.isPackaged
  ? { estado: 'parado' }
  : { estado: 'indisponivel', mensagem: 'Atualizações só funcionam no app instalado.' };
let avisar: (estado: EstadoAtualizacao) => void = () => {};
let configurado = false;

function mudar(novo: EstadoAtualizacao): void {
  atual = novo;
  avisar(novo);
}

function configurar(): void {
  if (configurado || !app.isPackaged) return;
  configurado = true;
  autoUpdater.logger = logAtu;
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true; // se o usuário não reiniciar agora, instala ao fechar
  autoUpdater.on('checking-for-update', () => mudar({ estado: 'verificando' }));
  autoUpdater.on('update-not-available', () => mudar({ estado: 'atualizado', versao: app.getVersion() }));
  autoUpdater.on('update-available', (info) => mudar({ estado: 'baixando', versao: info.version }));
  autoUpdater.on('update-downloaded', (info) => mudar({ estado: 'pronta', versao: info.version }));
  autoUpdater.on('error', (err) => {
    logAtu.warn('falha ao atualizar:', err?.message);
    mudar({ estado: 'erro', mensagem: 'Não consegui verificar atualizações agora.' });
  });
}

/** `aoMudar` recebe cada mudança de estado (a janela repassa para a interface). */
export function iniciarAtualizacao(aoMudar: (estado: EstadoAtualizacao) => void): void {
  avisar = aoMudar;
  if (!app.isPackaged) return;
  configurar();
  autoUpdater.checkForUpdates().catch(() => {}); // erros chegam pelo evento 'error'
}

export function estadoAtualizacao(): EstadoAtualizacao {
  return atual;
}

/** Menu do app › Verificar atualizações. */
export async function verificarAgora(): Promise<EstadoAtualizacao> {
  if (!app.isPackaged) return atual;
  configurar();
  if (atual.estado === 'pronta' || atual.estado === 'baixando') return atual;
  try {
    await autoUpdater.checkForUpdates();
  } catch {
    /* o evento 'error' já atualizou o estado */
  }
  return atual;
}

/** Reinicia e instala a versão já baixada. */
export function instalarAgora(): void {
  if (atual.estado === 'pronta') autoUpdater.quitAndInstall();
}
