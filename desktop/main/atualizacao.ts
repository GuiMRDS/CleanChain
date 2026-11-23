// Atualização automática pelos GitHub Releases (só no app empacotado).
import { app, dialog } from 'electron';
import log from 'electron-log/main';
import { autoUpdater } from 'electron-updater';

const logAtu = log.scope('atualizacao');
let configurado = false;

function configurar(): void {
  if (configurado) return;
  configurado = true;
  autoUpdater.logger = logAtu;
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.on('update-downloaded', async (info) => {
    const { response } = await dialog.showMessageBox({
      type: 'info',
      title: 'Atualização pronta',
      message: `A versão ${info.version} do CleanChain foi baixada.`,
      detail: 'Reinicie para instalar agora, ou ela será instalada quando você fechar o app.',
      buttons: ['Reiniciar agora', 'Depois'],
      defaultId: 0,
      cancelId: 1,
    });
    if (response === 0) autoUpdater.quitAndInstall();
  });
  autoUpdater.on('error', (err) => logAtu.warn('falha ao atualizar:', err?.message));
}

/** Verifica em segundo plano ao abrir o app. */
export function verificarAoIniciar(): void {
  if (!app.isPackaged) return;
  configurar();
  autoUpdater.checkForUpdates().catch((err) => logAtu.warn('verificação falhou:', err?.message));
}

/** Menu Ajuda › Verificar atualizações: avisa também quando não há nada novo. */
export async function verificarAgora(): Promise<void> {
  if (!app.isPackaged) {
    await dialog.showMessageBox({ type: 'info', message: 'Atualizações só funcionam no app instalado.' });
    return;
  }
  configurar();
  try {
    const resultado = await autoUpdater.checkForUpdates();
    const nova = resultado?.updateInfo?.version;
    if (!nova || nova === app.getVersion()) {
      await dialog.showMessageBox({ type: 'info', message: `Você já tem a versão mais recente (${app.getVersion()}).` });
    } else {
      await dialog.showMessageBox({ type: 'info', message: `Baixando a versão ${nova}…`, detail: 'Você será avisado quando ela estiver pronta.' });
    }
  } catch (err) {
    await dialog.showMessageBox({ type: 'warning', message: 'Não consegui verificar atualizações.', detail: (err as Error).message });
  }
}
