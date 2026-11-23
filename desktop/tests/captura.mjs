// Captura de tela do app (perfil vazio): node tests/captura.mjs <arquivo.png> [CleanChain.exe]
import { _electron as electron } from '@playwright/test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [saida = 'captura.png', exe] = process.argv.slice(2);
const perfil = fs.mkdtempSync(path.join(os.tmpdir(), 'cleanchain-captura-'));
const env = { ...process.env, CLEANCHAIN_PERFIL: perfil };
delete env.CLEANCHAIN_DEV_URL;

const app = exe
  ? await electron.launch({ executablePath: path.resolve(exe), env })
  : await electron.launch({ args: [desktop], cwd: desktop, env });
try {
  const page = await app.firstWindow();
  await page.waitForURL(/^http:\/\/127\.0\.0\.1:\d+\/$/, { timeout: 60_000 });
  await page.waitForTimeout(3500); // robô 3D e animações de entrada
  await page.screenshot({ path: saida });
  console.log('captura salva em', path.resolve(saida));
} finally {
  await app.close();
  fs.rmSync(perfil, { recursive: true, force: true });
}
