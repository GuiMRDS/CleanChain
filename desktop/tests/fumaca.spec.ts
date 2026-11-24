// Teste de fumaça: o app abre, a interface carrega, a rota de saúde responde, as travas de
// segurança estão de pé e, ao fechar, o backend não continua rodando.
//
//   npm run test:fumaca
//       Electron via Playwright (_electron) com o processo principal compilado (dist/main).
//       Backend: uv (desenvolvimento) ou CLEANCHAIN_BACKEND_EXE=../backend/dist/cleanchain-backend/cleanchain-backend.exe
//
//   CLEANCHAIN_EXE=<executável empacotado> npm run test:fumaca
//       O app empacotado, com os Fuses ligados. Os Fuses desligam o --inspect que o _electron
//       usa, então o Playwright se conecta pelo protocolo do Chromium (CDP). Executáveis:
//         Windows  release/win-unpacked/CleanChain.exe
//         macOS    release/mac-arm64/CleanChain.app/Contents/MacOS/CleanChain
//         Linux    release/linux-unpacked/cleanchain
//
//   No Linux sem tela (CI), rode com xvfb-run.
//
// Usa um perfil vazio e temporário (CLEANCHAIN_PERFIL): não toca na chave nem nos scans reais.
import { _electron as electron, Browser, chromium, expect, Page, test } from '@playwright/test';
import { ChildProcess, execFile, execFileSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';

const DESKTOP = path.resolve(__dirname, '..');
const URL_DO_APP = /^http:\/\/127\.0\.0\.1:\d+\/$/;
const WINDOWS = process.platform === 'win32';

function processoVivo(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

/** Mata à força o processo que escuta na porta (simula o backend travando). */
function matarQuemEscuta(porta: string): void {
  if (WINDOWS) {
    const pid = execFileSync('powershell', [
      '-NoProfile',
      '-Command',
      `(Get-NetTCPConnection -LocalPort ${porta} -State Listen | Select-Object -First 1).OwningProcess`,
    ])
      .toString()
      .trim();
    execFileSync('taskkill', ['/PID', pid, '/F']);
    return;
  }
  const pid = execFileSync('lsof', ['-t', `-iTCP:${porta}`, '-sTCP:LISTEN']).toString().trim().split('\n')[0];
  process.kill(Number(pid), 'SIGKILL');
}

interface AppAberto {
  page: Page;
  perfil: string;
  fechar: () => Promise<void>;
}

function portaLivre(): Promise<number> {
  return new Promise((resolve) => {
    const srv = net.createServer().listen(0, '127.0.0.1', () => {
      const { port } = srv.address() as net.AddressInfo;
      srv.close(() => resolve(port));
    });
  });
}

async function primeiraPaginaDoApp(browser: Browser): Promise<Page> {
  for (let i = 0; i < 240; i++) {
    const page = browser.contexts().flatMap((c) => c.pages()).find((p) => URL_DO_APP.test(p.url()));
    if (page) return page;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error('a janela do app não carregou a interface');
}

async function abrirApp(): Promise<AppAberto> {
  const perfil = fs.mkdtempSync(path.join(os.tmpdir(), 'cleanchain-fumaca-'));
  const env: Record<string, string> = { ...(process.env as Record<string, string>), CLEANCHAIN_PERFIL: perfil };
  delete env.CLEANCHAIN_DEV_URL; // sempre a interface servida pelo backend, como no app instalado
  const exe = process.env.CLEANCHAIN_EXE;

  if (!exe) {
    const app = await electron.launch({ args: [DESKTOP], cwd: DESKTOP, env });
    const page = await app.firstWindow();
    await page.waitForURL(URL_DO_APP, { timeout: 60_000 });
    return { page, perfil, fechar: () => app.close() };
  }

  // App empacotado: abre com a porta de depuração do Chromium e conecta pelo CDP.
  const porta = await portaLivre();
  const proc: ChildProcess = spawn(path.resolve(DESKTOP, exe), [`--remote-debugging-port=${porta}`], { env, stdio: 'ignore' });
  let browser: Browser | undefined;
  for (let i = 0; i < 120 && !browser; i++) {
    browser = await chromium.connectOverCDP(`http://127.0.0.1:${porta}`).catch(() => undefined);
    if (!browser) await new Promise((r) => setTimeout(r, 250));
  }
  if (!browser) throw new Error('não consegui conectar ao app empacotado');
  const page = await primeiraPaginaDoApp(browser);
  const fechar = async () => {
    // Fecha como o usuário fecharia (a janela), para exercitar o encerramento do backend.
    const saiu = new Promise<void>((r) => proc.once('exit', () => r()));
    await page.evaluate(() => window.close()).catch(() => {});
    await Promise.race([saiu, new Promise((r) => setTimeout(r, 15_000))]);
    if (proc.exitCode === null && proc.signalCode === null && proc.pid) {
      if (WINDOWS) execFile('taskkill', ['/PID', String(proc.pid), '/T', '/F']);
      else proc.kill('SIGKILL');
      // Espera o processo sair de fato: logo após o kill o PID ainda existe até ser recolhido.
      await Promise.race([saiu, new Promise((r) => setTimeout(r, 10_000))]);
    }
    await browser?.close().catch(() => {});
  };
  return { page, perfil, fechar };
}

test('o app abre, a interface carrega e a saúde responde', async () => {
  const { page, perfil, fechar } = await abrirApp();
  try {
    // Primeira abertura do app empacotado (sem cache): a interface pode levar alguns segundos.
    await expect(page.locator('.brand')).toContainText('cleanchain', { timeout: 30_000 });
    expect(await page.title()).toBe('CleanChain');

    // Saúde e API de dentro do app (o cookie de sessão foi criado pelo /bootstrap).
    const health = await page.evaluate(() => fetch('/health').then((r) => r.json()));
    expect(health).toEqual({ ok: true });
    const drives = await page.evaluate(() => fetch('/api/drives').then((r) => r.status));
    expect(drives).toBe(200);

    // Perfil novo, sem chave: o app pede para conectar o agente.
    await expect(page.getByText('Conectar o agente')).toBeVisible();

    // Moldura integrada: menu do próprio app no lugar da barra de menu do Windows.
    await page.getByRole('button', { name: 'Menu do CleanChain' }).click();
    const menu = page.getByRole('menu', { name: 'CleanChain' });
    await expect(menu).toBeVisible();
    await expect(menu.getByRole('menuitem', { name: /Chave do modelo/ })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(menu).toBeHidden();
  } finally {
    await fechar();
    fs.rmSync(perfil, { recursive: true, force: true });
  }
});

test('as travas de segurança estão de pé', async () => {
  const { page, perfil, fechar } = await abrirApp();
  try {
    const origem = new URL(page.url()).origin;

    // Fora do app (sem o cookie), a API recusa.
    expect((await fetch(`${origem}/api/drives`)).status).toBe(401);
    expect((await fetch(`${origem}/`)).status).toBe(401);
    // O token de bootstrap não funciona de novo.
    expect((await fetch(`${origem}/bootstrap?t=qualquer`, { redirect: 'manual' })).status).toBe(401);

    // Na interface: sem Node, só a ponte mínima.
    const ambiente = await page.evaluate(() => ({
      require: typeof (window as unknown as { require?: unknown }).require,
      process: typeof (window as unknown as { process?: unknown }).process,
      ponte: Object.keys((window as unknown as { cleanchain: object }).cleanchain).sort(),
    }));
    expect(ambiente).toEqual({ require: 'undefined', process: 'undefined', ponte: ['aoAtualizacao', 'aoPropostaMcp', 'app', 'chave', 'mcp', 'sistema'] });

    // CSP vem no cabeçalho da página.
    const csp = await page.evaluate(() => fetch('/').then((r) => r.headers.get('content-security-policy')));
    expect(csp).toContain("default-src 'self'");

    // A ponte valida argumentos: chave inválida é recusada e nada é salvo.
    const erro = await page.evaluate(() =>
      (window as unknown as { cleanchain: { chave: { salvar: (p: string, c: string) => Promise<unknown> } } }).cleanchain.chave
        .salvar('groq', 'curta')
        .then(() => 'aceitou', (e: Error) => e.message)
    );
    expect(erro).toContain('não parece válida');
    expect(fs.existsSync(path.join(perfil, 'segredos.json'))).toBe(false);

    // Navegar para fora do app é bloqueado (a URL continua a do app). Usa http (não https):
    // o app também se recusa a abrir esse link no navegador, então o teste não abre nada de
    // verdade (no Linux sem navegador, o shell.openExternal de um link https ficava pendurado).
    await page.evaluate(() => {
      window.location.href = 'http://example.invalid/';
    });
    await page.waitForTimeout(1500);
    expect(new URL(page.url()).origin).toBe(origem);
  } finally {
    await fechar();
    fs.rmSync(perfil, { recursive: true, force: true });
  }
});

test('se o backend cair, o app mostra o aviso e Reiniciar traz tudo de volta', async () => {
  const { page, perfil, fechar } = await abrirApp();
  try {
    const porta = new URL(page.url()).port;
    // Derruba o backend como um travamento faria (o processo que escuta na porta).
    matarQuemEscuta(porta);

    // A tela de erro local (no visual do app) aparece, sem fechar a janela.
    await page.waitForURL(/estado\.html\?estado=erro/, { timeout: 30_000 });
    await expect(page.getByRole('heading', { name: 'O CleanChain precisa reiniciar o serviço.' })).toBeVisible();

    // Reiniciar: backend novo (outra porta/token) e a interface de volta, já com sessão.
    await page.getByRole('button', { name: 'Reiniciar' }).click();
    await page.waitForURL(URL_DO_APP, { timeout: 60_000 });
    expect(await page.evaluate(() => fetch('/api/drives').then((r) => r.status))).toBe(200);
  } finally {
    await fechar();
    fs.rmSync(perfil, { recursive: true, force: true });
  }
});

/** Liga/desliga a integração MCP pela ponte da interface (como a tela "Integração MCP" faz). */
function definirMcp(page: Page, ativo: boolean): Promise<{ ativo: boolean }> {
  type Ponte = { cleanchain: { mcp: { definir: (a: boolean) => Promise<{ ativo: boolean }> } } };
  return page.evaluate((a) => (window as unknown as Ponte).cleanchain.mcp.definir(a), ativo);
}

test('integração MCP: proposta chega ao app e só o usuário decide', async () => {
  // Uma "área escaneada" dentro da pasta do usuário (permitida nos três sistemas).
  const area = fs.mkdtempSync(path.join(os.homedir(), '.cleanchain-fumaca-'));
  const alvo = path.join(area, 'instalador-antigo.iso');
  fs.writeFileSync(alvo, Buffer.alloc(4096));
  const { page, perfil, fechar } = await abrirApp();
  try {
    // Desligada por padrão: sem runtime.json.
    const runtime = path.join(perfil, 'runtime.json');
    expect(fs.existsSync(runtime)).toBe(false);

    // Liga pela tela (ponte) → o app grava o runtime.json com porta, token e PID.
    expect((await definirMcp(page, true)).ativo).toBe(true);
    const rt = JSON.parse(fs.readFileSync(runtime, 'utf8'));
    expect(rt.porta).toBe(Number(new URL(page.url()).port));
    if (!WINDOWS) expect(fs.statSync(runtime).mode & 0o077).toBe(0); // só o usuário lê

    // O scan desta área (o que o botão Start scan gravaria).
    fs.mkdirSync(path.join(perfil, 'scans'), { recursive: true });
    fs.writeFileSync(path.join(perfil, 'scans', 'latest.json'), JSON.stringify({
      root: area, total: '4.0 KB', total_bytes: 4096, files_scanned: 1,
      tree: { name: 'area', path: area, bytes: 4096, size: '4.0 KB', files: 1, children: [] },
    }));

    // Como o cleanchain-mcp faria: token MCP do runtime.json, nome do cliente no cabeçalho.
    const base = `http://127.0.0.1:${rt.porta}`;
    const mcpHeaders = { Authorization: `Bearer ${rt.token}`, 'X-MCP-Client': 'Cliente de Fumaça', 'Content-Type': 'application/json' };
    const criada = await (await fetch(`${base}/api/mcp/propostas`, { method: 'POST', headers: mcpHeaders, body: JSON.stringify({ paths: [alvo], reason: 'instalador antigo' }) })).json();
    expect(criada.ok).toBe(true);

    // O app mostra o cartão com o selo do cliente.
    await expect(page.getByText('Proposta via MCP: Cliente de Fumaça')).toBeVisible({ timeout: 20_000 });

    // O token MCP não aprova (rota da interface exige o cookie).
    const tentativa = await fetch(`${base}/api/propostas/${criada.id}/decisao`, { method: 'POST', headers: mcpHeaders, body: JSON.stringify({ aprovar: true }) });
    expect(tentativa.status).toBe(401);

    // O usuário recusa no app: nada é apagado.
    await page.getByRole('button', { name: 'Cancelar' }).click();
    await expect(page.getByText('Cancelado — nada foi apagado.')).toBeVisible();
    const estado = await (await fetch(`${base}/api/mcp/propostas/${criada.id}`, { headers: mcpHeaders })).json();
    expect(estado.estado).toBe('recusada');
    expect(fs.existsSync(alvo)).toBe(true);

    // Desligar recusa as rotas MCP e apaga o runtime.json.
    await definirMcp(page, false);
    expect(fs.existsSync(runtime)).toBe(false);
    expect((await fetch(`${base}/api/mcp/resumo`, { headers: mcpHeaders })).status).toBe(403);

    // Ligado de novo e fechando o app: o runtime.json some junto.
    await definirMcp(page, true);
    expect(fs.existsSync(runtime)).toBe(true);
    await fechar();
    // App fechado = o cleanchain-mcp passa a responder "abra o app". Na saída normal o arquivo
    // some; se o processo foi encerrado à força (no macOS fechar a janela não encerra o app, então
    // o teste do app empacotado mata o processo), sobra o arquivo com um PID que já não existe —
    // e o cleanchain-mcp confere o PID (test_app_fechado_com_pid_morto).
    const sobrou = fs.existsSync(runtime) ? Number(JSON.parse(fs.readFileSync(runtime, 'utf8')).pid) : null;
    expect(sobrou === null || !processoVivo(sobrou)).toBe(true);
  } finally {
    await fechar().catch(() => {});
    fs.rmSync(perfil, { recursive: true, force: true });
    fs.rmSync(area, { recursive: true, force: true });
  }
});

test('ao fechar, o backend para de responder', async () => {
  const { page, perfil, fechar } = await abrirApp();
  const origem = new URL(page.url()).origin;
  expect((await fetch(`${origem}/health`)).ok).toBe(true);
  await fechar();
  try {
    let vivo = true;
    for (let i = 0; i < 20 && vivo; i++) {
      vivo = await fetch(`${origem}/health`, { signal: AbortSignal.timeout(500) }).then(
        () => true,
        () => false
      );
      if (vivo) await new Promise((r) => setTimeout(r, 250));
    }
    expect(vivo).toBe(false);
  } finally {
    fs.rmSync(perfil, { recursive: true, force: true });
  }
});
