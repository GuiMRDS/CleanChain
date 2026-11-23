// Canais IPC permitidos (lista fechada). Cada handler confere quem chama — a interface do app
// (origem do backend local) ou a tela local de estado — e valida os argumentos; qualquer
// outro canal simplesmente não existe.
import { app, ipcMain, IpcMainInvokeEvent, shell } from 'electron';
import log from 'electron-log/main';
import { estadoAtualizacao, instalarAgora, verificarAgora } from './atualizacao';
import { pastaLogs } from './caminhos';
import { daOrigemDoApp } from './seguranca';
import * as segredos from './segredos';
import { ehTela as ehTelaLocal } from './tela';

const logIpc = log.scope('ipc');

export const CANAIS = {
  chaveStatus: 'chave:status',
  chaveSalvar: 'chave:salvar',
  chaveRemover: 'chave:remover',
  versao: 'app:versao',
  abrirLogs: 'app:abrirLogs',
  reiniciarServico: 'app:reiniciarServico',
  atualizacao: 'app:atualizacao',
  verificarAtualizacoes: 'app:verificarAtualizacoes',
  instalarAtualizacao: 'app:instalarAtualizacao',
  eventoAtualizacao: 'atualizacao:estado', // main → interface
} as const;

interface Dependencias {
  origemApp: () => string | undefined;
  /** Reinicia o backend (com a chave atual) e recarrega a janela. */
  reiniciarBackend: () => Promise<void>;
}

type Quem = 'app' | 'tela';

/** Quem chamou: a interface do app, a tela local de estado, ou ninguém confiável (lança). */
function exigirOrigem(event: IpcMainInvokeEvent, origemApp: () => string | undefined, aceita: Quem[]): void {
  const url = event.senderFrame?.url ?? '';
  const ehApp = daOrigemDoApp(url, origemApp);
  const ehTela = ehTelaLocal(url);
  if ((ehApp && aceita.includes('app')) || (ehTela && aceita.includes('tela'))) return;
  logIpc.warn('chamada IPC recusada de', url);
  throw new Error('Origem não permitida.');
}

export function registrarIpc({ origemApp, reiniciarBackend }: Dependencias): void {
  const so = (aceita: Quem[], fn: (event: IpcMainInvokeEvent, arg: unknown) => unknown) =>
    (event: IpcMainInvokeEvent, arg: unknown) => {
      exigirOrigem(event, origemApp, aceita);
      return fn(event, arg);
    };

  ipcMain.handle(CANAIS.chaveStatus, so(['app'], () => segredos.status()));

  ipcMain.handle(
    CANAIS.chaveSalvar,
    so(['app'], async (_event, arg) => {
      const { provedor, chave } = (arg ?? {}) as { provedor?: unknown; chave?: unknown };
      const valido = segredos.validar(provedor, chave); // lança Error com mensagem para a tela
      segredos.salvar(valido.provedor, valido.chave);
      logIpc.info(`chave do provedor ${valido.provedor} salva (cifrada)`); // nunca a chave
      await reiniciarBackend();
      return segredos.status();
    })
  );

  ipcMain.handle(
    CANAIS.chaveRemover,
    so(['app'], async () => {
      segredos.remover();
      logIpc.info('chave removida');
      await reiniciarBackend();
      return segredos.status();
    })
  );

  ipcMain.handle(CANAIS.versao, so(['app', 'tela'], () => app.getVersion()));
  ipcMain.handle(CANAIS.abrirLogs, so(['app', 'tela'], () => shell.openPath(pastaLogs()).then(() => undefined)));
  ipcMain.handle(CANAIS.reiniciarServico, so(['app', 'tela'], () => reiniciarBackend()));
  ipcMain.handle(CANAIS.atualizacao, so(['app'], () => estadoAtualizacao()));
  ipcMain.handle(CANAIS.verificarAtualizacoes, so(['app'], () => verificarAgora()));
  ipcMain.handle(CANAIS.instalarAtualizacao, so(['app'], () => instalarAgora()));
}
