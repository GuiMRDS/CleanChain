// Canais IPC permitidos (lista fechada). Cada handler confere a origem de quem chama e
// valida os argumentos; qualquer outro canal simplesmente não existe.
import { app, ipcMain, IpcMainInvokeEvent } from 'electron';
import log from 'electron-log/main';
import { daOrigemDoApp } from './seguranca';
import * as segredos from './segredos';

const logIpc = log.scope('ipc');

export const CANAIS = {
  chaveStatus: 'chave:status',
  chaveSalvar: 'chave:salvar',
  chaveRemover: 'chave:remover',
  versao: 'app:versao',
  abrirConfig: 'config:abrir', // main → interface (menu Arquivo › Configurar chave)
} as const;

interface Dependencias {
  origemApp: () => string | undefined;
  /** Reinicia o backend com a chave nova e recarrega a janela. */
  reiniciarBackend: () => Promise<void>;
}

function exigirOrigem(event: IpcMainInvokeEvent, origemApp: () => string | undefined): void {
  const url = event.senderFrame?.url;
  if (!daOrigemDoApp(url, origemApp)) {
    logIpc.warn('chamada IPC recusada de', url);
    throw new Error('Origem não permitida.');
  }
}

export function registrarIpc({ origemApp, reiniciarBackend }: Dependencias): void {
  ipcMain.handle(CANAIS.chaveStatus, (event) => {
    exigirOrigem(event, origemApp);
    return segredos.status();
  });

  ipcMain.handle(CANAIS.chaveSalvar, async (event, arg: unknown) => {
    exigirOrigem(event, origemApp);
    const { provedor, chave } = (arg ?? {}) as { provedor?: unknown; chave?: unknown };
    const valido = segredos.validar(provedor, chave); // lança Error com mensagem para a tela
    segredos.salvar(valido.provedor, valido.chave);
    logIpc.info(`chave do provedor ${valido.provedor} salva (cifrada)`); // nunca a chave
    await reiniciarBackend();
    return segredos.status();
  });

  ipcMain.handle(CANAIS.chaveRemover, async (event) => {
    exigirOrigem(event, origemApp);
    segredos.remover();
    logIpc.info('chave removida');
    await reiniciarBackend();
    return segredos.status();
  });

  ipcMain.handle(CANAIS.versao, (event) => {
    exigirOrigem(event, origemApp);
    return app.getVersion();
  });
}
