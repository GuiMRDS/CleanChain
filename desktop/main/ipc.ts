// Canais IPC permitidos (lista fechada). Cada handler confere quem chama — a interface do app
// (origem do backend local) ou a tela local de estado — e valida os argumentos; qualquer
// outro canal simplesmente não existe.
import { app, clipboard, ipcMain, IpcMainInvokeEvent, shell } from 'electron';
import log from 'electron-log/main';
import { estadoAtualizacao, instalarAgora, verificarAgora } from './atualizacao';
import { pastaLogs } from './caminhos';
import * as ia from './ia';
import * as licenca from './licenca';
import * as mcp from './mcp';
import { daOrigemDoApp } from './seguranca';
import * as segredos from './segredos';
import { ehTela as ehTelaLocal } from './tela';

const logIpc = log.scope('ipc');

export const CANAIS = {
  chaveStatus: 'chave:status',
  chaveSalvar: 'chave:salvar',
  chaveRemover: 'chave:remover',
  chaveModelosLocais: 'chave:modelosLocais', // IA local: modelos do Ollama/LM Studio (só 127.0.0.1)
  chaveUsarLocal: 'chave:usarLocal',
  chaveUsarNuvem: 'chave:usarNuvem',
  versao: 'app:versao',
  abrirLogs: 'app:abrirLogs',
  reiniciarServico: 'app:reiniciarServico',
  atualizacao: 'app:atualizacao',
  verificarAtualizacoes: 'app:verificarAtualizacoes',
  instalarAtualizacao: 'app:instalarAtualizacao',
  eventoAtualizacao: 'atualizacao:estado', // main → interface
  mcpStatus: 'mcp:status',
  mcpDefinir: 'mcp:definir',
  mcpCopiar: 'mcp:copiar',
  eventoPropostaMcp: 'mcp:proposta', // main → interface: chegou uma proposta de limpeza via MCP
  licencaStatus: 'licenca:status', // licença opcional (modelo WinRAR): só tira o convite
  licencaRegistrar: 'licenca:registrar',
  licencaRemover: 'licenca:remover',
  licencaAdiarConvite: 'licenca:adiarConvite',
} as const;

interface Dependencias {
  origemApp: () => string | undefined;
  /** Reinicia o backend (com a chave atual) e recarrega a janela. */
  reiniciarBackend: () => Promise<void>;
  /** Porta do backend no ar (para o runtime.json da integração MCP). */
  portaBackend: () => number | undefined;
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

export function registrarIpc({ origemApp, reiniciarBackend, portaBackend }: Dependencias): void {
  const so =
    (aceita: Quem[], fn: (event: IpcMainInvokeEvent, arg: unknown) => unknown) => (event: IpcMainInvokeEvent, arg: unknown) => {
      exigirOrigem(event, origemApp, aceita);
      return fn(event, arg);
    };

  ipcMain.handle(
    CANAIS.chaveStatus,
    so(['app'], () => ia.status())
  );

  ipcMain.handle(
    CANAIS.chaveSalvar,
    so(['app'], async (_event, arg) => {
      const { provedor, chave } = (arg ?? {}) as { provedor?: unknown; chave?: unknown };
      const valido = segredos.validar(provedor, chave); // lança Error com mensagem para a tela
      segredos.salvar(valido.provedor, valido.chave);
      ia.usarNuvem(); // colar uma chave = usar a nuvem
      logIpc.info(`chave do provedor ${valido.provedor} salva (cifrada)`); // nunca a chave
      await reiniciarBackend();
      return ia.status();
    })
  );

  ipcMain.handle(
    CANAIS.chaveRemover,
    so(['app'], async () => {
      segredos.remover();
      logIpc.info('chave removida');
      await reiniciarBackend();
      return ia.status();
    })
  );

  ipcMain.handle(
    CANAIS.chaveModelosLocais,
    so(['app'], (_event, arg) => {
      const { provedor, porta } = (arg ?? {}) as { provedor?: unknown; porta?: unknown };
      return ia.modelosLocais(provedor, porta); // valida e só consulta 127.0.0.1
    })
  );

  ipcMain.handle(
    CANAIS.chaveUsarLocal,
    so(['app'], async (_event, arg) => {
      const { provedor, modelo, porta } = (arg ?? {}) as { provedor?: unknown; modelo?: unknown; porta?: unknown };
      ia.usarLocal(provedor, modelo, porta); // lança Error com mensagem para a tela
      await reiniciarBackend();
      return ia.status();
    })
  );

  ipcMain.handle(
    CANAIS.chaveUsarNuvem,
    so(['app'], async () => {
      ia.usarNuvem();
      await reiniciarBackend();
      return ia.status();
    })
  );

  ipcMain.handle(
    CANAIS.versao,
    so(['app', 'tela'], () => app.getVersion())
  );
  ipcMain.handle(
    CANAIS.abrirLogs,
    so(['app', 'tela'], () => shell.openPath(pastaLogs()).then(() => undefined))
  );
  ipcMain.handle(
    CANAIS.reiniciarServico,
    so(['app', 'tela'], () => reiniciarBackend())
  );
  ipcMain.handle(
    CANAIS.atualizacao,
    so(['app'], () => estadoAtualizacao())
  );
  ipcMain.handle(
    CANAIS.verificarAtualizacoes,
    so(['app'], () => verificarAgora())
  );
  ipcMain.handle(
    CANAIS.instalarAtualizacao,
    so(['app'], () => instalarAgora())
  );

  // Integração MCP: só a interface do app liga, desliga e copia a configuração.
  ipcMain.handle(
    CANAIS.mcpStatus,
    so(['app'], () => mcp.status())
  );
  ipcMain.handle(
    CANAIS.mcpDefinir,
    so(['app'], (_event, arg) => {
      if (typeof arg !== 'boolean') throw new Error('Valor inválido.');
      mcp.definir(arg, portaBackend());
      return mcp.status();
    })
  );
  ipcMain.handle(
    CANAIS.mcpCopiar,
    so(['app'], (_event, arg) => {
      if (typeof arg !== 'string' || !(mcp.CLIENTES as readonly string[]).includes(arg)) throw new Error('Cliente inválido.');
      clipboard.writeText(mcp.configuracao(arg as mcp.ClienteMcp));
      return true;
    })
  );

  ipcMain.handle(
    CANAIS.licencaStatus,
    so(['app'], () => licenca.status())
  );
  ipcMain.handle(
    CANAIS.licencaRegistrar,
    so(['app'], (_event, arg) => {
      if (typeof arg !== 'string' || arg.length > 2000) throw new Error('Chave inválida.');
      return licenca.registrar(arg); // confere a assinatura; lança Error com mensagem para a tela
    })
  );
  ipcMain.handle(
    CANAIS.licencaRemover,
    so(['app'], () => licenca.remover())
  );
  ipcMain.handle(
    CANAIS.licencaAdiarConvite,
    so(['app'], () => licenca.adiarConvite())
  );
}
