// Processo principal do CleanChain: inicia o backend local, abre a janela na interface servida
// por ele e garante que nada fica rodando quando o app fecha.
import { app, BrowserWindow, dialog, Menu, MenuItemConstructorOptions, screen, session, shell } from 'electron';
import log from 'electron-log/main';
import path from 'node:path';
import { verificarAgora, verificarAoIniciar } from './atualizacao';
import { Backend, Conexao } from './backend';
import { urlDev } from './caminhos';
import { CANAIS, registrarIpc } from './ipc';
import * as segredos from './segredos';
import { preferenciasSeguras, protegerConteudo, protegerSessao } from './seguranca';

// Perfil isolado (testes de fumaça): precisa vir antes de qualquer uso de userData.
if (process.env.CLEANCHAIN_PERFIL) app.setPath('userData', path.resolve(process.env.CLEANCHAIN_PERFIL));

log.initialize();
log.transports.file.level = 'info';
log.errorHandler.startCatching();
const logMain = log.scope('main');

const APP_ID = 'com.guimrds.cleanchain';
const backend = new Backend();
let janela: BrowserWindow | undefined;
let saindo = false;

/** Origem da interface: o backend local, ou o Vite em desenvolvimento. */
function origemApp(): string | undefined {
  const dev = urlDev();
  if (dev) return new URL(dev).origin;
  return backend.conexao ? `http://127.0.0.1:${backend.conexao.porta}` : undefined;
}

function urlBootstrap({ porta, token }: Conexao): string {
  const base = urlDev() ?? `http://127.0.0.1:${porta}`;
  return `${base}/bootstrap?t=${encodeURIComponent(token)}`;
}

const pastaLogs = () => path.dirname(log.transports.file.getFile().path);

// ---------------------------------------------------------------- backend

async function iniciarBackend(): Promise<void> {
  janela?.setTitle('CleanChain — iniciando…');
  const conexao = await backend.iniciar(segredos.envDoBackend());
  await janela?.loadURL(urlBootstrap(conexao));
  janela?.setTitle('CleanChain');
}

async function reiniciarBackend(): Promise<void> {
  await backend.parar();
  await iniciarComAviso();
}

/** Inicia o backend; se falhar, explica e oferece tentar de novo, sem fechar o app. */
async function iniciarComAviso(): Promise<void> {
  try {
    await iniciarBackend();
  } catch (err) {
    logMain.error('não consegui iniciar o backend:', (err as Error).message);
    await avisarProblema('Não consegui iniciar o serviço do CleanChain.', (err as Error).message);
  }
}

async function avisarProblema(mensagem: string, detalhe: string): Promise<void> {
  if (saindo || !janela) return;
  const { response } = await dialog.showMessageBox(janela, {
    type: 'error',
    title: 'CleanChain',
    message: mensagem,
    detail: `${detalhe}\n\nSeus scans salvos não foram afetados. A conversa atual com o agente é reiniciada.`,
    buttons: ['Reiniciar', 'Abrir pasta de logs', 'Sair'],
    defaultId: 0,
    cancelId: 2,
    noLink: true,
  });
  if (response === 0) return reiniciarBackend();
  if (response === 1) {
    await shell.openPath(pastaLogs());
    return avisarProblema(mensagem, detalhe);
  }
  app.quit();
}

backend.on('caiu', (codigo: number | null) => {
  if (saindo) return;
  logMain.warn(`o backend caiu (código ${codigo})`);
  void avisarProblema('O serviço do CleanChain parou.', `Ele terminou de forma inesperada (código ${codigo ?? '?'}).`);
});

// ---------------------------------------------------------------- janela e menu

function criarJanela(): BrowserWindow {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  const win = new BrowserWindow({
    width: Math.min(1600, width),
    height: Math.min(900, height),
    minWidth: Math.min(1280, width),
    minHeight: Math.min(760, height),
    backgroundColor: '#f6fafe', // --bg da interface: sem flash branco enquanto o backend sobe
    title: 'CleanChain — iniciando…',
    show: true,
    webPreferences: { ...preferenciasSeguras(path.join(__dirname, '..', 'preload', 'preload.js')), devTools: !app.isPackaged },
  });
  win.on('page-title-updated', (event) => event.preventDefault()); // o título é do app
  win.webContents.on('render-process-gone', (_e, details) => {
    logMain.warn('interface caiu:', details.reason);
    if (!saindo && details.reason !== 'clean-exit') win.reload();
  });
  win.on('closed', () => {
    janela = undefined;
  });
  return win;
}

function montarMenu(): void {
  const template: MenuItemConstructorOptions[] = [
    {
      label: 'Arquivo',
      submenu: [
        { label: 'Configurar chave do LLM…', click: () => janela?.webContents.send(CANAIS.abrirConfig) },
        { label: 'Abrir pasta de logs', click: () => void shell.openPath(pastaLogs()) },
        { type: 'separator' },
        { role: 'quit', label: 'Sair' },
      ],
    },
    {
      label: 'Exibir',
      submenu: [
        { role: 'resetZoom', label: 'Tamanho original' },
        { role: 'zoomIn', label: 'Aumentar' },
        { role: 'zoomOut', label: 'Diminuir' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: 'Tela cheia' },
        ...(app.isPackaged ? [] : ([{ type: 'separator' }, { role: 'reload' }, { role: 'toggleDevTools' }] as MenuItemConstructorOptions[])),
      ],
    },
    {
      label: 'Ajuda',
      submenu: [
        { label: 'Verificar atualizações…', click: () => void verificarAgora() },
        {
          label: 'Sobre o CleanChain',
          click: () =>
            void dialog.showMessageBox({
              type: 'info',
              title: 'Sobre o CleanChain',
              message: `CleanChain ${app.getVersion()}`,
              detail: 'Limpeza de disco com um agente de IA que só apaga com a sua aprovação. Tudo roda neste computador; só as mensagens do chat vão ao provedor do modelo.',
            }),
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ---------------------------------------------------------------- ciclo de vida

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.setAppUserModelId(APP_ID);

  app.on('second-instance', () => {
    if (!janela) return;
    if (janela.isMinimized()) janela.restore();
    janela.focus();
  });

  // Toda janela/conteúdo criado passa pelas mesmas travas.
  app.on('web-contents-created', (_event, contents) => protegerConteudo(contents, origemApp));

  app.whenReady().then(async () => {
    logMain.info(`CleanChain ${app.getVersion()} (${app.isPackaged ? 'instalado' : 'desenvolvimento'})`);
    protegerSessao(session.defaultSession, origemApp, !urlDev());
    registrarIpc({ origemApp, reiniciarBackend });
    montarMenu();
    janela = criarJanela();
    await iniciarComAviso();
    verificarAoIniciar();
  });

  app.on('window-all-closed', () => app.quit());

  // Antes de sair: encerra o backend e toda a árvore de processos dele.
  app.on('before-quit', (event) => {
    if (saindo) return;
    saindo = true;
    event.preventDefault();
    backend
      .parar()
      .catch((err) => logMain.error('falha ao encerrar o backend:', err))
      .finally(() => app.quit());
  });
}
