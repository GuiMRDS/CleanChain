// Grava os quadros da demonstração (docs/roteiro-demo.md) com o app de verdade, sem dados reais:
//   node tests/gravar-demo.mjs <pasta-de-quadros>
// e depois: uv run --with pillow python tests/montar-gif.py <pasta-de-quadros> ../docs/images/demo.gif
//
// - A "pasta do usuário" é uma pasta fictícia (CLEANCHAIN_DEMO_HOME, padrão D:\Demo\ana no
//   Windows) com arquivos gerados; o perfil do app é temporário. Nada do seu disco aparece.
// - O agente usa a chave do .env (GROQ_API_KEY/OPENAI_API_KEY), salva no cofre só deste perfil
//   temporário e nunca impressa.
// - A limpeza aprovada no vídeo manda arquivos GERADOS para a Lixeira do sistema.
// - A cena do MCP faz o mesmo pedido HTTP que a ponte MCP faz, identificado como "Claude Code".
import { _electron as electron } from '@playwright/test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const raiz = path.resolve(desktop, '..');
const [saida = path.join(os.tmpdir(), 'cleanchain-demo-quadros')] = process.argv.slice(2);
const HOME = process.env.CLEANCHAIN_DEMO_HOME || (process.platform === 'win32' ? 'D:\\Demo\\ana' : path.join(os.tmpdir(), 'demo', 'ana'));
const MB = 1024 * 1024;
const ANTIGO = new Date('2023-03-14T10:00:00');

// ------------------------------------------------------------------ pasta do usuário fictícia

function arquivo(rel, mb, { antigo = false, conteudo } = {}) {
  const p = path.join(HOME, rel);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  const fd = fs.openSync(p, 'w');
  // Cabeçalho único por arquivo (ou igual, para duplicados de verdade) e o resto do tamanho.
  fs.writeSync(fd, Buffer.from((conteudo ?? rel).padEnd(4096, '.')));
  fs.ftruncateSync(fd, Math.round(mb * MB));
  fs.closeSync(fd);
  if (antigo) fs.utimesSync(p, ANTIGO, ANTIGO);
}

function montarHome() {
  fs.rmSync(HOME, { recursive: true, force: true });
  arquivo('Videos/viagem-patagonia-2023.mp4', 412, { antigo: true });
  arquivo('Videos/aula-gravada-react.mp4', 263);
  arquivo('Videos/apresentacao-final.mov', 148);
  arquivo('Downloads/ubuntu-24.04-desktop-amd64.iso', 296, { antigo: true });
  arquivo('Downloads/instaladores/editor-setup-2022.exe', 88, { antigo: true });
  arquivo('Downloads/instaladores/driver-impressora-v3.exe', 46, { antigo: true });
  arquivo('Downloads/instaladores/jogo-instalador.msi', 63, { antigo: true });
  arquivo('Downloads/planilha-orcamento.xlsx', 2.4);
  arquivo('Pictures/ferias/IMG_2041.jpg', 14, { conteudo: 'foto-praia' });
  arquivo('Pictures/ferias (copia)/IMG_2041.jpg', 14, { conteudo: 'foto-praia' });
  arquivo('Pictures/ferias/IMG_2042.jpg', 11.5);
  arquivo('Pictures/ferias/IMG_2043.jpg', 12.7);
  arquivo('Documents/tcc-versao-final.pdf', 9.3);
  arquivo('Documents/contratos/aluguel-2024.pdf', 1.6);
  arquivo('Documents/backup-celular-2022.zip', 238, { antigo: true });
  for (let i = 0; i < 14; i++) arquivo(`projetos/loja-web/node_modules/pacote-${i}/index.js`, 3 + i * 0.7);
  arquivo('projetos/loja-web/src/app.jsx', 0.1);
  for (let i = 0; i < 6; i++) arquivo(`AppData/Local/Temp/tmp-instalacao-${i}.tmp`, 9 + i * 3);
  for (let i = 0; i < 5; i++) arquivo(`AppData/Local/pip/cache/http/wheel-${i}.bin`, 7 + i * 2);
}

// ------------------------------------------------------------------ chave do .env (sem imprimir)

function chaveDoEnv() {
  for (const f of [path.join(raiz, 'backend', '.env'), path.join(raiz, '.env')]) {
    if (!fs.existsSync(f)) continue;
    for (const linha of fs.readFileSync(f, 'utf8').split(/\r?\n/)) {
      const m = linha.match(/^\s*(GROQ_API_KEY|OPENAI_API_KEY)\s*=\s*"?([^"\s#]+)/);
      if (m) return { provedor: m[1] === 'GROQ_API_KEY' ? 'groq' : 'openai', chave: m[2] };
    }
  }
  throw new Error('Sem GROQ_API_KEY/OPENAI_API_KEY no .env');
}

// ------------------------------------------------------------------ gravação

montarHome();
fs.rmSync(saida, { recursive: true, force: true });
fs.mkdirSync(saida, { recursive: true });
const perfil = fs.mkdtempSync(path.join(os.tmpdir(), 'cleanchain-demo-'));
// Python da venv direto (o uv procuraria o Python e o cache dentro da pasta do usuário fictícia).
const python = path.join(raiz, 'backend', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const env = { ...process.env, CLEANCHAIN_PERFIL: perfil, CLEANCHAIN_PYTHON: python, USERPROFILE: HOME, HOME };
delete env.CLEANCHAIN_DEV_URL;

const app = await electron.launch({ args: [desktop], cwd: desktop, env });
const quadros = [];
let gravando = false;
let velocidade = 1;
let cena = '';
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
const marcar = (nome, v = 1) => { cena = nome; velocidade = v; console.log(`cena: ${nome}`); };

try {
  let page = await app.firstWindow();
  await app.evaluate(({ BrowserWindow }) => {
    const w = BrowserWindow.getAllWindows()[0];
    w.setContentSize(1600, 900);
    w.center();
  });
  await page.waitForURL(/^http:\/\/127\.0\.0\.1:\d+\/$/, { timeout: 90_000 });

  // Espera o app voltar depois de um reinício do backend (tela de estado → interface) e ficar
  // estável por alguns segundos na interface.
  const esperarApp = async () => {
    const fim = Date.now() + 120_000;
    while (Date.now() < fim) {
      try {
        await page.waitForURL(/^http:\/\/127\.0\.0\.1:\d+\/$/, { timeout: 5_000 });
        await page.locator('.orb').waitFor({ timeout: 5_000 });
        await esperar(2_500);
        if (/^http:\/\/127\.0\.0\.1:\d+\/$/.test(page.url()) && (await page.locator('.orb').count())) return;
      } catch {
        await esperar(500);
      }
    }
    throw new Error('o app não voltou depois do reinício');
  };
  // Chama a ponte sem depender da página continuar a mesma (a chamada pode reiniciar o backend).
  const ponte = (fn, arg) => page.evaluate(fn, arg).catch(() => {});

  // Prepara fora da gravação: chave (o backend reinicia) e integração MCP ligada.
  const { provedor, chave } = chaveDoEnv();
  await ponte(([p, c]) => window.cleanchain.chave.salvar(p, c), [provedor, chave]);
  await esperar(1_500);
  await esperarApp();
  await ponte(() => window.cleanchain.mcp.definir(true));
  await esperar(1_500);
  await esperarApp();
  if (!fs.existsSync(path.join(perfil, 'runtime.json'))) throw new Error('integração MCP não ligou');
  await esperar(3000); // robô e animações de entrada

  // Quadros em paralelo com as ações.
  gravando = true;
  const t0 = Date.now();
  const captura = (async () => {
    let i = 0;
    while (gravando) {
      const arq = `q${String(i++).padStart(5, '0')}.jpg`;
      try {
        await page.screenshot({ path: path.join(saida, arq), type: 'jpeg', quality: 82 });
        quadros.push({ arq, t: Date.now() - t0, v: velocidade, cena });
      } catch {
        await esperar(50);
      }
    }
  })();

  marcar('abertura');
  await esperar(3500);

  marcar('escolher');
  await page.locator('.target', { hasText: 'Minha pasta' }).click();
  await esperar(1800);

  marcar('scan', 2);
  await page.locator('.orb').click();
  await page.locator('.scan-card').waitFor({ timeout: 180_000 });
  marcar('resultado');
  await esperar(2500);
  const mapa = page.locator('.sunburst svg path').nth(2);
  if (await mapa.count()) await mapa.hover().catch(() => {});
  await esperar(2500);

  const caixa = page.getByLabel('Mensagem para o agente');
  const perguntar = async (texto) => {
    marcar('digitando');
    await caixa.click();
    await caixa.pressSequentially(texto, { delay: 35 });
    await esperar(400);
    await caixa.press('Enter');
    marcar('agente', 2);
    await page.waitForFunction(() => !document.querySelector('.agent-status.is-thinking'), null, { timeout: 120_000, polling: 300 });
  };

  await perguntar('Onde foi meu espaço? Abre a maior pasta no mapa.');
  marcar('resposta');
  await esperar(4500);

  await perguntar('Manda os instaladores antigos da pasta Downloads\\instaladores para a Lixeira.');
  const aprovar = page.locator('.approval__go');
  await aprovar.waitFor({ timeout: 60_000 });
  marcar('aprovacao');
  await esperar(3500);
  await aprovar.click();
  marcar('aprovado', 2);
  await page.waitForFunction(() => !document.querySelector('.agent-status.is-thinking') && !document.querySelector('.approval__go'), null, { timeout: 120_000, polling: 300 });
  marcar('liberado');
  await esperar(3500);

  // MCP: o mesmo pedido que a ponte MCP faz (token do runtime.json, nome do cliente).
  marcar('mcp');
  const rt = JSON.parse(fs.readFileSync(path.join(perfil, 'runtime.json'), 'utf8'));
  const resp = await fetch(`http://127.0.0.1:${rt.porta}/api/mcp/propostas`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${rt.token}`, 'X-MCP-Client': 'Claude Code', 'Content-Type': 'application/json' },
    body: JSON.stringify({ paths: [path.join(HOME, 'Downloads', 'ubuntu-24.04-desktop-amd64.iso')], reason: 'Imagem de instalação de 2023, já usada: ~296 MB.' }),
  });
  if (!resp.ok) throw new Error(`proposta MCP: ${resp.status} ${await resp.text()}`);
  await page.getByText('Proposta via MCP: Claude Code').waitFor({ timeout: 30_000 });
  await esperar(4000);
  await page.locator('.approval__no').click();
  marcar('fim');
  await esperar(3500);

  gravando = false;
  await captura;
  fs.writeFileSync(path.join(saida, 'quadros.json'), JSON.stringify(quadros));
  console.log(`${quadros.length} quadros em ${saida}`);
} finally {
  gravando = false;
  await app.close().catch(() => {});
  fs.rmSync(perfil, { recursive: true, force: true });
  fs.rmSync(HOME, { recursive: true, force: true });
}
