// Ponte mínima entre a interface e o processo principal (contextIsolation + sandbox).
// Só estes métodos existem em window.cleanchain; nada de ipcRenderer cru, nada de Node.
import { contextBridge, ipcRenderer } from 'electron';

// Os nomes repetem desktop/main/ipc.ts: o preload em sandbox não pode importar outros arquivos.
const CANAIS = {
  chaveStatus: 'chave:status',
  chaveSalvar: 'chave:salvar',
  chaveRemover: 'chave:remover',
  chaveModelosLocais: 'chave:modelosLocais',
  chaveUsarLocal: 'chave:usarLocal',
  chaveUsarNuvem: 'chave:usarNuvem',
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
  licencaStatus: 'licenca:status',
  licencaRegistrar: 'licenca:registrar',
  licencaRemover: 'licenca:remover',
  licencaAdiarConvite: 'licenca:adiarConvite',
  eventoPropostaMcp: 'mcp:proposta',
} as const;

/** Chama um canal e desembrulha a resposta: erro de uso vira um Error comum para a tela. */
async function chamar<T = unknown>(canal: string, arg?: unknown): Promise<T> {
  const r = await ipcRenderer.invoke(canal, arg);
  if (r && typeof r === 'object' && r.ok === false) throw new Error(String(r.erro));
  return (r && typeof r === 'object' && r.ok === true ? r.valor : undefined) as T;
}

contextBridge.exposeInMainWorld('cleanchain', {
  /** 'win32' | 'darwin' | 'linux': só para a interface ajustar a barra de título. */
  sistema: process.platform,
  chave: {
    status: () => chamar(CANAIS.chaveStatus),
    salvar: (provedor: string, chave: string) => chamar(CANAIS.chaveSalvar, { provedor: String(provedor), chave: String(chave) }),
    remover: () => chamar(CANAIS.chaveRemover),
    /** IA local (Ollama/LM Studio neste computador): listar modelos, usar um, voltar para a nuvem. */
    modelosLocais: (provedor: string, porta?: number) =>
      chamar(CANAIS.chaveModelosLocais, {
        provedor: String(provedor),
        porta: porta === undefined ? undefined : Number(porta),
      }),
    usarLocal: (provedor: string, modelo: string, porta?: number) =>
      chamar(CANAIS.chaveUsarLocal, {
        provedor: String(provedor),
        modelo: String(modelo),
        porta: porta === undefined ? undefined : Number(porta),
      }),
    usarNuvem: () => chamar(CANAIS.chaveUsarNuvem),
  },
  app: {
    versao: (): Promise<string> => chamar(CANAIS.versao),
    abrirLogs: () => chamar(CANAIS.abrirLogs),
    reiniciarServico: () => chamar(CANAIS.reiniciarServico),
    atualizacao: () => chamar(CANAIS.atualizacao),
    verificarAtualizacoes: () => chamar(CANAIS.verificarAtualizacoes),
    instalarAtualizacao: () => chamar(CANAIS.instalarAtualizacao),
  },
  /** Integração MCP: status, ligar/desligar e copiar a configuração de um cliente. */
  mcp: {
    status: () => chamar(CANAIS.mcpStatus),
    definir: (ativo: boolean) => chamar(CANAIS.mcpDefinir, Boolean(ativo)),
    copiar: (cliente: string) => chamar(CANAIS.mcpCopiar, String(cliente)),
  },
  /** Licença opcional (modelo WinRAR): o app é igual para todos; a licença só tira o convite. */
  licenca: {
    status: () => chamar(CANAIS.licencaStatus),
    registrar: (chave: string) => chamar(CANAIS.licencaRegistrar, String(chave)),
    remover: () => chamar(CANAIS.licencaRemover),
    adiarConvite: () => chamar(CANAIS.licencaAdiarConvite),
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
