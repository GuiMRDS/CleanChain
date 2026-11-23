// Captura a janela inteira do app, com a moldura (barra de título, botões e bordas), como o
// usuário vê. Perfil vazio e temporário.
//   node tests/captura-janela.mjs <arquivo.png> [espera-ms]
import { _electron as electron } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [saida = 'janela.png', espera = '4000'] = process.argv.slice(2);
const perfil = fs.mkdtempSync(path.join(os.tmpdir(), 'cleanchain-janela-'));
const env = { ...process.env, CLEANCHAIN_PERFIL: perfil };
delete env.CLEANCHAIN_DEV_URL;

const app = await electron.launch({ args: [desktop], cwd: desktop, env });
try {
  const page = await app.firstWindow();
  await page.waitForURL(/^http:\/\/127\.0\.0\.1:\d+\/$/, { timeout: 60_000 });
  await page.waitForTimeout(Number(espera));
  const b = await app.evaluate(({ BrowserWindow }) => {
    const w = BrowserWindow.getAllWindows()[0];
    w.setAlwaysOnTop(true);
    w.focus();
    return w.getBounds();
  });
  await page.waitForTimeout(400);
  const ps = `Add-Type -AssemblyName System.Drawing;
    $bmp = New-Object System.Drawing.Bitmap ${b.width}, ${b.height};
    $g = [System.Drawing.Graphics]::FromImage($bmp);
    $g.CopyFromScreen(${b.x}, ${b.y}, 0, 0, $bmp.Size);
    $bmp.Save('${path.resolve(saida).replace(/'/g, "''")}', [System.Drawing.Imaging.ImageFormat]::Png)`;
  execFileSync('powershell', ['-NoProfile', '-Command', ps]);
  console.log('janela', b, '→', path.resolve(saida));
} finally {
  await app.close();
  fs.rmSync(perfil, { recursive: true, force: true });
}
