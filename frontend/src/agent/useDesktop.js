import { useCallback, useEffect, useState } from 'react';

// Bridge to the Electron app (desktop/preload/preload.ts exposes window.cleanchain).
// In the browser (dev mode with Vite) the bridge doesn't exist and nothing changes:
// the LLM key comes from backend/.env as before.
const bridge = typeof window !== 'undefined' ? window.cleanchain : undefined;

export const isDesktop = Boolean(bridge);

export function useDesktop() {
  const [chave, setChave] = useState(null); // { configurada, provedor } once known
  const [configAberta, setConfigAberta] = useState(false);
  const [versao, setVersao] = useState('');
  const [atualizacao, setAtualizacao] = useState(null); // see desktop/main/atualizacao.ts
  const [mcp, setMcp] = useState(null); // { ativo, executavel, instalado, configuracoes }
  const [mcpAberta, setMcpAberta] = useState(false);

  useEffect(() => {
    if (!bridge) return undefined;
    let vivo = true;
    bridge.chave
      .status()
      .then((s) => vivo && setChave(s))
      .catch(() => {});
    bridge.app
      .versao()
      .then((v) => vivo && setVersao(v))
      .catch(() => {});
    bridge.app
      .atualizacao()
      .then((a) => vivo && setAtualizacao(a))
      .catch(() => {});
    bridge.mcp
      ?.status()
      .then((m) => vivo && setMcp(m))
      .catch(() => {});
    const parar = bridge.aoAtualizacao((a) => setAtualizacao(a));
    return () => {
      vivo = false;
      parar?.();
    };
  }, []);

  // The main process encrypts the key and restarts the backend; the window reloads after.
  const salvarChave = useCallback((provedor, valor) => bridge.chave.salvar(provedor, valor), []);
  // Local AI (Ollama/LM Studio on this computer): list installed models, use one, or go back to the cloud.
  const modelosLocais = useCallback((provedor, porta) => bridge.chave.modelosLocais(provedor, porta), []);
  const usarLocal = useCallback((provedor, modelo, porta) => bridge.chave.usarLocal(provedor, modelo, porta), []);
  const usarNuvem = useCallback(() => bridge.chave.usarNuvem(), []);
  const verificarAtualizacoes = useCallback(async () => {
    setAtualizacao({ estado: 'verificando' });
    setAtualizacao(await bridge.app.verificarAtualizacoes());
  }, []);
  const definirMcp = useCallback(async (ativo) => setMcp(await bridge.mcp.definir(ativo)), []);
  const copiarMcp = useCallback((cliente) => bridge.mcp.copiar(cliente), []);

  const precisaChave = Boolean(bridge && chave && !chave.configurada);
  return {
    desktop: isDesktop,
    chave,
    versao,
    atualizacao,
    mostrarConfig: precisaChave || configAberta,
    precisaChave,
    salvarChave,
    modelosLocais,
    usarLocal,
    usarNuvem,
    // With a local AI nothing leaves the computer, not even audio: the mic is off.
    iaLocal: Boolean(chave && chave.ativo && chave.ativo !== 'nuvem'),
    abrirConfig: () => {
      setMcpAberta(false);
      setConfigAberta(true);
    },
    fecharConfig: chave?.configurada ? () => setConfigAberta(false) : null,
    verificarAtualizacoes,
    instalarAtualizacao: () => bridge?.app.instalarAtualizacao(),
    abrirLogs: () => bridge?.app.abrirLogs(),
    // Integração MCP
    mcp,
    mcpAberta: Boolean(bridge) && mcpAberta,
    abrirMcp: () => {
      setConfigAberta(false);
      setMcpAberta(true);
    },
    fecharMcp: () => setMcpAberta(false),
    definirMcp,
    copiarMcp,
  };
}
