// Endurecimento da janela e da sessão: CSP, navegação, pop-ups e permissões.
import { Session, WebContents, shell } from 'electron';
import log from 'electron-log/main';

const logSeg = log.scope('seguranca');

// Mesma política que o backend manda (backend/app/interface.py). O Electron também a aplica,
// para valer mesmo se uma resposta chegar sem o cabeçalho.
export const CSP = [
  "default-src 'self'",
  "script-src 'self' 'wasm-unsafe-eval'",
  "worker-src 'self' blob:",
  "style-src 'self'",
  "img-src 'self' data: blob:",
  "media-src 'self' blob:",
  "font-src 'self'",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "frame-ancestors 'none'",
].join('; ');

function origemDe(url: string | undefined): string | undefined {
  try {
    return url ? new URL(url).origin : undefined;
  } catch {
    return undefined;
  }
}

/** True se `url` é da origem atual do app (o backend local, ou o Vite em desenvolvimento). */
export function daOrigemDoApp(url: string | undefined, origemApp: () => string | undefined): boolean {
  const atual = origemApp();
  return Boolean(atual && origemDe(url) === atual);
}

/** Links externos: só https, sempre no navegador padrão. */
function abrirFora(url: string): void {
  if (origemDe(url) && new URL(url).protocol === 'https:') {
    void shell.openExternal(url);
  } else {
    logSeg.warn('link externo recusado (só https):', url);
  }
}

/**
 * Sessão do app: nega todas as permissões, exceto o microfone (entrada por voz) pedido pela
 * própria interface; aplica a CSP nas páginas do app (fora do modo de desenvolvimento).
 */
export function protegerSessao(ses: Session, origemApp: () => string | undefined, aplicarCsp: boolean): void {
  ses.setPermissionRequestHandler((_wc, permission, callback, details) => {
    const ok =
      permission === 'media' &&
      daOrigemDoApp(details.requestingUrl, origemApp) &&
      'mediaTypes' in details &&
      Array.isArray(details.mediaTypes) &&
      details.mediaTypes.length > 0 &&
      details.mediaTypes.every((t) => t === 'audio');
    if (!ok) logSeg.warn(`permissão negada: ${permission} (${details.requestingUrl})`);
    callback(ok);
  });
  ses.setPermissionCheckHandler((_wc, permission, requestingOrigin, details) => {
    return permission === 'media' && details.mediaType === 'audio' && origemDe(requestingOrigin) === origemApp();
  });
  ses.setDevicePermissionHandler(() => false); // HID, USB, serial: nunca

  if (aplicarCsp) {
    ses.webRequest.onHeadersReceived((details, callback) => {
      const headers = { ...details.responseHeaders };
      if (details.resourceType === 'mainFrame' && daOrigemDoApp(details.url, origemApp)) {
        headers['Content-Security-Policy'] = [CSP];
      }
      callback({ responseHeaders: headers });
    });
  }
}

/** Janela: nada de navegar para fora do app, nada de pop-ups, nada de <webview>. */
export function protegerConteudo(contents: WebContents, origemApp: () => string | undefined): void {
  contents.on('will-navigate', (event, url) => {
    if (daOrigemDoApp(url, origemApp)) return;
    event.preventDefault();
    abrirFora(url);
  });
  contents.on('will-redirect', (event, url) => {
    if (!daOrigemDoApp(url, origemApp)) event.preventDefault();
  });
  contents.setWindowOpenHandler(({ url }) => {
    abrirFora(url);
    return { action: 'deny' };
  });
  contents.on('will-attach-webview', (event) => event.preventDefault());
}

/** Preferências fixas de toda janela do app. */
export function preferenciasSeguras(preload: string): Electron.WebPreferences {
  return {
    preload,
    contextIsolation: true,
    sandbox: true,
    nodeIntegration: false,
    nodeIntegrationInWorker: false,
    nodeIntegrationInSubFrames: false,
    webSecurity: true,
    allowRunningInsecureContent: false,
    webviewTag: false,
    navigateOnDragDrop: false,
    spellcheck: false,
    partition: 'cleanchain', // sem "persist:": o cookie de sessão morre quando o app fecha
  };
}
