// Capturas das telas do app desktop (perfil vazio): janela inteira, menu do app aberto,
// tela de abertura e tela de erro.  node tests/captura-estados.mjs <pasta-de-saída>
// ATENÇÃO: copia uma região da TELA do sistema (para mostrar a moldura da janela). Se outra
// janela estiver na frente, ela aparece na captura: feche/minimize as outras antes. Para ver
// só o conteúdo do app, use tests/captura.mjs (page.screenshot).
import { _electron as electron } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pasta = path.resolve(process.argv[2] || '.');
const perfil = fs.mkdtempSync(path.join(os.tmpdir(), 'cleanchain-estados-'));
const env = { ...process.env, CLEANCHAIN_PERFIL: perfil };
delete env.CLEANCHAIN_DEV_URL;

const app = await electron.launch({ args: [desktop], cwd: desktop, env });

async function capturarJanela(nome) {
  const b = await app.evaluate(({ BrowserWindow }) => {
    const w = BrowserWindow.getAllWindows()[0];
    w.setAlwaysOnTop(true);
    w.focus();
    return w.getBounds();
  });
  await new Promise((r) => setTimeout(r, 500));
  const saida = path.join(pasta, nome).replace(/'/g, "''");
  execFileSync('powershell', ['-NoProfile', '-Command', `Add-Type -AssemblyName System.Drawing;
    $bmp = New-Object System.Drawing.Bitmap ${b.width}, ${b.height}; $g = [System.Drawing.Graphics]::FromImage($bmp);
    $g.CopyFromScreen(${b.x}, ${b.y}, 0, 0, $bmp.Size); $bmp.Save('${saida}', [System.Drawing.Imaging.ImageFormat]::Png)`]);
  console.log('→', nome);
}

try {
  const page = await app.firstWindow();
  await page.waitForURL(/^http:\/\/127\.0\.0\.1:\d+\/$/, { timeout: 60_000 });
  await page.waitForTimeout(3500);
  await capturarJanela('1-janela.png');

  await page.getByRole('button', { name: 'Menu do CleanChain' }).click();
  await page.waitForTimeout(400);
  await capturarJanela('2-menu.png');
  await page.keyboard.press('Escape');

  const tela = 'cleanchain://tela/estado.html';
  await page.goto(`${tela}?estado=iniciando`);
  await page.waitForTimeout(900);
  await capturarJanela('3-abertura.png');

  await page.goto(`${tela}?estado=erro&mensagem=${encodeURIComponent('O serviço terminou de forma inesperada (código 1).')}`);
  await page.waitForTimeout(900);
  await capturarJanela('4-erro.png');
} finally {
  await app.close();
  fs.rmSync(perfil, { recursive: true, force: true });
}
