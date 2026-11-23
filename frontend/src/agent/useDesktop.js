import { useCallback, useEffect, useState } from 'react';

// Bridge to the Electron app (desktop/preload/preload.ts exposes window.cleanchain).
// In the browser (dev mode with Vite) the bridge doesn't exist and nothing changes:
// the LLM key comes from backend/.env as before.
const bridge = typeof window !== 'undefined' ? window.cleanchain : undefined;

export function useDesktop() {
  const [chave, setChave] = useState(null); // { configurada, provedor } once known
  const [configAberta, setConfigAberta] = useState(false);

  useEffect(() => {
    if (!bridge) return undefined;
    let vivo = true;
    bridge.chave.status().then((s) => vivo && setChave(s)).catch(() => {});
    const parar = bridge.aoAbrirConfiguracao(() => setConfigAberta(true)); // menu Arquivo › Configurar chave
    return () => {
      vivo = false;
      parar?.();
    };
  }, []);

  // The main process encrypts the key and restarts the backend; the window reloads after.
  const salvarChave = useCallback((provedor, valor) => bridge.chave.salvar(provedor, valor), []);

  const precisaChave = Boolean(bridge && chave && !chave.configurada);
  return {
    desktop: Boolean(bridge),
    chave,
    mostrarConfig: precisaChave || configAberta,
    precisaChave,
    salvarChave,
    fecharConfig: chave?.configurada ? () => setConfigAberta(false) : null,
  };
}
