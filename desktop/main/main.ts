// Processo principal do CleanChain: inicia o backend local, abre a janela na interface servida
// por ele e garante que nada fica rodando quando o app fecha.
import { app, BrowserWindow, Menu, screen, session } from 'electron';
import log from 'electron-log/main';
import path from 'node:path';
import { EstadoAtualizacao, iniciarAtualizacao } from './atualizacao';
import { Backend, Conexao } from './backend';
import { icone, telaEstado, urlDev } from './caminhos';
import { CANAIS, registrarIpc } from './ipc';
import { FECHAR_JANELA_ENCERRA, menuNativo, opcoesDeJanela } from './plataforma';
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

/** Tela local no visual do app: abertura enquanto o backend sobe, ou aviso de erro. */
async function mostrarEstado(estado: 'iniciando' | 'reiniciando' | 'erro', mensagem = ''): Promise<void> {
  if (!janela || saindo) return;
  await janela.loadFile(telaEstado(), { query: { estado, mensagem } }).catch(() => {});
}

// ---------------------------------------------------------------- backend

let iniciando = false;

/** Inicia o backend e abre a interface; se falhar, a tela de erro oferece Reiniciar. */
async function iniciarBackend(estado: 'iniciando' | 'reiniciando' = 'iniciando'): Promise<void> {
  if (iniciando) return;
  iniciando = true;
  try {
    await mostrarEstado(estado);
    const conexao = await backend.iniciar(segredos.envDoBackend());
    await janela?.loadURL(urlBootstrap(conexao));
  } catch (err) {
    logMain.error('não consegui iniciar o backend:', (err as Error).message);
    await mostrarEstado('erro', `Não consegui iniciar o serviço: ${(err as Error).message}`);
  } finally {
    iniciando = false;
  }
}

async function reiniciarBackend(): Promise<void> {
  await backend.parar();
  await iniciarBackend('reiniciando');
}

backend.on('caiu', (codigo: number | null) => {
  if (saindo) return;
  logMain.warn(`o backend caiu (código ${codigo})`);
  void mostrarEstado('erro', `O serviço terminou de forma inesperada (código ${codigo ?? '?'}).`);
});

// ---------------------------------------------------------------- janela

function criarJanela(): BrowserWindow {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  const win = new BrowserWindow({
    width: Math.min(1600, width),
    height: Math.min(900, height),
    minWidth: Math.min(1280, width),
    minHeight: Math.min(760, height),
    backgroundColor: '#f6fafe', // --bg da interface: sem flash de outra cor ao abrir
    title: 'CleanChain',
    icon: icone(), // mesma marca do instalador e do site
    ...opcoesDeJanela(), // barra de título integrada (botões à direita; no macOS, à esquerda)
    show: false,
    webPreferences: { ...preferenciasSeguras(path.join(__dirname, '..', 'preload', 'preload.js')), devTools: !app.isPackaged },
  });
  win.once('ready-to-show', () => win.show()); // a tela de abertura já pintou: nada de janela vazia
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

/** Menu nativo de cada sistema (invisível no Windows/Linux; o do app no macOS). */
function montarMenu(): void {
  Menu.setApplicationMenu(Menu.buildFromTemplate(menuNativo()));
}

function avisarAtualizacao(estado: EstadoAtualizacao): void {
  janela?.webContents.send(CANAIS.eventoAtualizacao, estado);
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
    await iniciarBackend();
    iniciarAtualizacao(avisarAtualizacao);
  });

  // Windows/Linux: fechar a janela encerra o app. macOS: o app continua ativo (com o backend
  // rodando) e o Dock reabre a janela; o cookie de sessão continua valendo enquanto o app vive.
  app.on('window-all-closed', () => {
    if (FECHAR_JANELA_ENCERRA) app.quit();
  });
  app.on('activate', () => {
    if (janela || !app.isReady()) return;
    janela = criarJanela();
    const origem = origemApp();
    if (backend.rodando && origem) void janela.loadURL(`${origem}/`);
    else void iniciarBackend();
  });

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
