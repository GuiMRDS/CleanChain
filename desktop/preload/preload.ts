// Ponte mínima entre a interface e o processo principal (contextIsolation + sandbox).
// Só estes métodos existem em window.cleanchain; nada de ipcRenderer cru, nada de Node.
import { contextBridge, ipcRenderer } from 'electron';

// Os nomes repetem desktop/main/ipc.ts: o preload em sandbox não pode importar outros arquivos.
const CANAIS = {
  chaveStatus: 'chave:status',
  chaveSalvar: 'chave:salvar',
  chaveRemover: 'chave:remover',
  versao: 'app:versao',
  abrirConfig: 'config:abrir',
} as const;

contextBridge.exposeInMainWorld('cleanchain', {
  versao: (): Promise<string> => ipcRenderer.invoke(CANAIS.versao),
  chave: {
    status: () => ipcRenderer.invoke(CANAIS.chaveStatus),
    salvar: (provedor: string, chave: string) => ipcRenderer.invoke(CANAIS.chaveSalvar, { provedor: String(provedor), chave: String(chave) }),
    remover: () => ipcRenderer.invoke(CANAIS.chaveRemover),
  },
  /** Menu Arquivo › Configurar chave. Devolve a função que cancela a inscrição. */
  aoAbrirConfiguracao: (callback: () => void) => {
    if (typeof callback !== 'function') return () => {};
    const ouvinte = () => callback();
    ipcRenderer.on(CANAIS.abrirConfig, ouvinte);
    return () => {
      ipcRenderer.removeListener(CANAIS.abrirConfig, ouvinte);
    };
  },
});
