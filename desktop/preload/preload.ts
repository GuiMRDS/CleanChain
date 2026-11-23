// Ponte mínima entre a interface e o processo principal (contextIsolation + sandbox).
// Só estes métodos existem em window.cleanchain; nada de ipcRenderer cru, nada de Node.
import { contextBridge, ipcRenderer } from 'electron';

// Os nomes repetem desktop/main/ipc.ts: o preload em sandbox não pode importar outros arquivos.
const CANAIS = {
  chaveStatus: 'chave:status',
  chaveSalvar: 'chave:salvar',
  chaveRemover: 'chave:remover',
  versao: 'app:versao',
  abrirLogs: 'app:abrirLogs',
  reiniciarServico: 'app:reiniciarServico',
  atualizacao: 'app:atualizacao',
  verificarAtualizacoes: 'app:verificarAtualizacoes',
  instalarAtualizacao: 'app:instalarAtualizacao',
  eventoAtualizacao: 'atualizacao:estado',
} as const;

contextBridge.exposeInMainWorld('cleanchain', {
  chave: {
    status: () => ipcRenderer.invoke(CANAIS.chaveStatus),
    salvar: (provedor: string, chave: string) => ipcRenderer.invoke(CANAIS.chaveSalvar, { provedor: String(provedor), chave: String(chave) }),
    remover: () => ipcRenderer.invoke(CANAIS.chaveRemover),
  },
  app: {
    versao: (): Promise<string> => ipcRenderer.invoke(CANAIS.versao),
    abrirLogs: () => ipcRenderer.invoke(CANAIS.abrirLogs),
    reiniciarServico: () => ipcRenderer.invoke(CANAIS.reiniciarServico),
    atualizacao: () => ipcRenderer.invoke(CANAIS.atualizacao),
    verificarAtualizacoes: () => ipcRenderer.invoke(CANAIS.verificarAtualizacoes),
    instalarAtualizacao: () => ipcRenderer.invoke(CANAIS.instalarAtualizacao),
  },
  /** Mudanças no estado da atualização automática. Devolve a função que cancela a inscrição. */
  aoAtualizacao: (callback: (estado: unknown) => void) => {
    if (typeof callback !== 'function') return () => {};
    const ouvinte = (_e: unknown, estado: unknown) => callback(estado);
    ipcRenderer.on(CANAIS.eventoAtualizacao, ouvinte);
    return () => {
      ipcRenderer.removeListener(CANAIS.eventoAtualizacao, ouvinte);
    };
  },
});
