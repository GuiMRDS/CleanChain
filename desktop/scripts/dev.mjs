// Modo de desenvolvimento do app desktop: Vite (com hot reload) + Electron.
//
//   cd desktop && npm run dev
//
// O Electron inicia o backend (uv run python -m app.desktop, ou CLEANCHAIN_PYTHON) na porta
// fixa CLEANCHAIN_PORTA_DEV (padrão 8000) e abre http://localhost:5173/bootstrap?t=…; o proxy
// do Vite repassa /api, /bootstrap e /health para o backend, então o cookie de sessão fica na
// origem do Vite e o fluxo é o mesmo do app instalado.
import { execFile, spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const frontend = path.resolve(desktop, '..', 'frontend');
const VITE_URL = 'http://localhost:5173';
const env = { ...process.env, CLEANCHAIN_PORTA_DEV: process.env.CLEANCHAIN_PORTA_DEV || '8000' };

function matar(proc) {
  if (!proc?.pid || proc.exitCode !== null) return;
  if (process.platform === 'win32') execFile('taskkill', ['/PID', String(proc.pid), '/T', '/F'], () => {});
  else {
    try {
      process.kill(-proc.pid, 'SIGTERM'); // o grupo inteiro (npm → vite)
    } catch {
      proc.kill('SIGTERM');
    }
  }
}

const vite = spawn('npm', ['run', 'dev', '--', '--port', '5173', '--strictPort'], {
  cwd: frontend,
  env,
  stdio: 'inherit',
  shell: true,
  detached: process.platform !== 'win32', // grupo próprio: dá para encerrar npm e vite juntos
});

async function esperarVite() {
  for (let i = 0; i < 120; i++) {
    try {
      if ((await fetch(VITE_URL)).ok) return;
    } catch {
      /* ainda subindo */
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error('o Vite não respondeu em 30 s');
}

try {
  await esperarVite();
} catch (err) {
  console.error(err.message);
  matar(vite);
  process.exit(1);
}

const electron = spawn(require('electron'), [desktop], { env: { ...env, CLEANCHAIN_DEV_URL: VITE_URL }, stdio: 'inherit' });
electron.on('exit', (code) => {
  matar(vite);
  process.exit(code ?? 0);
});
for (const sinal of ['SIGINT', 'SIGTERM']) {
  process.on(sinal, () => {
    matar(electron);
    matar(vite);
  });
}
