// Tela local de abertura/erro servida por um protocolo próprio (cleanchain://tela/…).
//
// Por que não file://: o Fuse GrantFileProtocolExtraPrivileges fica desligado (segurança), e
// páginas file:// perdem privilégios no app empacotado. O caminho recomendado é um protocolo
// próprio que só entrega os arquivos da pasta desktop/tela (nada fora dela).
import { net, protocol } from 'electron';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { telaEstado } from './caminhos';

export const ESQUEMA = 'cleanchain';
export const URL_TELA = `${ESQUEMA}://tela/estado.html`;

/** Precisa rodar antes do app ficar pronto (app.whenReady). */
export function registrarEsquema(): void {
  protocol.registerSchemesAsPrivileged([
    // standard + secure: origem própria ("cleanchain://tela") para a CSP 'self' valer.
    { scheme: ESQUEMA, privileges: { standard: true, secure: true } },
  ]);
}

/** Depois do app pronto: entrega só os arquivos da pasta da tela. */
export function servirTela(): void {
  const pasta = path.dirname(telaEstado());
  protocol.handle(ESQUEMA, (request) => {
    const url = new URL(request.url);
    const arquivo = path.normalize(path.join(pasta, decodeURIComponent(url.pathname)));
    const dentro = url.host === 'tela' && arquivo.startsWith(pasta + path.sep);
    if (!dentro) return new Response('não encontrado', { status: 404 });
    return net.fetch(pathToFileURL(arquivo).toString());
  });
}

/** URL da tela num estado (iniciando, reiniciando, erro) com uma mensagem opcional. */
export function urlDaTela(estado: string, mensagem = ''): string {
  const q = new URLSearchParams({ estado, mensagem });
  return `${URL_TELA}?${q.toString()}`;
}

/** True se a URL é a tela local (para o IPC saber quem está chamando). */
export function ehTela(url: string | undefined): boolean {
  return (url ?? '').split(/[?#]/)[0] === URL_TELA;
}
