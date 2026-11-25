// Gera o ícone do CleanChain a partir da marca do app (.brand__mark em frontend/src/App.css),
// renderizada no próprio Electron, com fundo transparente. Uma fonte só para tudo:
//   desktop/build/icon.png        512 px — instalador, .exe e janela (o builder converte em .ico)
//   frontend/public/favicon.png   128 px — aba do navegador e da interface
//   docs/images/logo.png          256 px — topo do README
//
//   cd desktop && npm run icone
import { app, BrowserWindow } from 'electron';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const LADO = 512;
const k = LADO / 20; // a marca tem 20px na interface
const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const SAIDAS = [
  { arquivo: path.join(repo, 'desktop', 'build', 'icon.png'), lado: 512 },
  { arquivo: path.join(repo, 'frontend', 'public', 'favicon.png'), lado: 128 },
  { arquivo: path.join(repo, 'docs', 'images', 'logo.png'), lado: 256 },
];

const html = `<!doctype html><html><body style="margin:0;background:transparent">
<div style="position:relative;width:${LADO}px;height:${LADO}px;border-radius:${6 * k}px;
  background:conic-gradient(from 200deg,#0091ff,#00aaff,#ff0099,#8000ff,#0091ff)">
  <div style="position:absolute;inset:${5 * k}px;border-radius:${3 * k}px;background:#f6fafe"></div>
</div></body></html>`;

/** Monta um .ico com imagens PNG dentro (formato aceito pelo Windows desde o Vista). */
function arquivoIco(imagens) {
  const cabecalho = Buffer.alloc(6);
  cabecalho.writeUInt16LE(0, 0); // reservado
  cabecalho.writeUInt16LE(1, 2); // tipo: ícone
  cabecalho.writeUInt16LE(imagens.length, 4);
  const entradas = [];
  let posicao = 6 + 16 * imagens.length;
  for (const { lado, png } of imagens) {
    const e = Buffer.alloc(16);
    e.writeUInt8(lado >= 256 ? 0 : lado, 0); // largura (0 = 256)
    e.writeUInt8(lado >= 256 ? 0 : lado, 1); // altura
    e.writeUInt16LE(1, 4); // planos
    e.writeUInt16LE(32, 6); // bits por pixel
    e.writeUInt32LE(png.length, 8);
    e.writeUInt32LE(posicao, 12);
    posicao += png.length;
    entradas.push(e);
  }
  return Buffer.concat([cabecalho, ...entradas, ...imagens.map((i) => i.png)]);
}

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    width: LADO,
    height: LADO,
    show: false,
    frame: false,
    transparent: true,
    useContentSize: true,
    webPreferences: { offscreen: true, sandbox: true },
  });
  await win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
  await new Promise((r) => setTimeout(r, 300));
  const img = await win.webContents.capturePage({ x: 0, y: 0, width: LADO, height: LADO });
  for (const { arquivo, lado } of SAIDAS) {
    fs.mkdirSync(path.dirname(arquivo), { recursive: true });
    fs.writeFileSync(arquivo, img.resize({ width: lado, height: lado, quality: 'best' }).toPNG());
    console.log(`ícone ${lado}px → ${path.relative(repo, arquivo)}`);
  }
  // .ico com vários tamanhos: o Windows usa na barra de tarefas quando o app roda pelo código
  // (setAppDetails em desktop/main/plataforma.ts); no app instalado o builder gera o dele.
  const ico = path.join(repo, 'desktop', 'build', 'icon.ico');
  fs.writeFileSync(ico, arquivoIco([16, 24, 32, 48, 64, 128, 256].map((lado) => ({ lado, png: img.resize({ width: lado, height: lado, quality: 'best' }).toPNG() }))));
  console.log(`ícone .ico → ${path.relative(repo, ico)}`);
  app.quit();
});
