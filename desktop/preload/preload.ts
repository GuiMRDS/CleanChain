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
  mcpStatus: 'mcp:status',
  mcpDefinir: 'mcp:definir',
  mcpCopiar: 'mcp:copiar',
  eventoPropostaMcp: 'mcp:proposta',
} as const;

contextBridge.exposeInMainWorld('cleanchain', {
  /** 'win32' | 'darwin' | 'linux': só para a interface ajustar a barra de título. */
  sistema: process.platform,
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
  /** Integração MCP: status, ligar/desligar e copiar a configuração de um cliente. */
  mcp: {
    status: () => ipcRenderer.invoke(CANAIS.mcpStatus),
    definir: (ativo: boolean) => ipcRenderer.invoke(CANAIS.mcpDefinir, Boolean(ativo)),
    copiar: (cliente: string) => ipcRenderer.invoke(CANAIS.mcpCopiar, String(cliente)),
  },
  /** Chegou uma proposta de limpeza via MCP. Devolve a função que cancela a inscrição. */
  aoPropostaMcp: (callback: (info: unknown) => void) => {
    if (typeof callback !== 'function') return () => {};
    const ouvinte = (_e: unknown, info: unknown) => callback(info);
    ipcRenderer.on(CANAIS.eventoPropostaMcp, ouvinte);
    return () => {
      ipcRenderer.removeListener(CANAIS.eventoPropostaMcp, ouvinte);
    };
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
