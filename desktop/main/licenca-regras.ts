// Licença opcional (modelo WinRAR): regras puras, sem Electron, testadas à parte
// (desktop/tests/licenca.spec.ts). Quem lê/grava os arquivos e fala com a interface é licenca.ts.
//
// O app é 100% igual com ou sem licença. Sem licença, depois de 30 dias de uso, um convite
// discreto aparece ao abrir, no máximo 1 vez por semana. Com licença, o convite some e o menu
// mostra "Licenciado para <nome>".
//
// Formato da chave: CC1-<dados em base64url>.<assinatura Ed25519 em base64url>. Os dados são um
// JSON { v: 1, nome, emitida, id }. Só quem tem a chave PRIVADA (desktop/scripts/licenca.mjs)
// emite licenças; o app confere com a chave PÚBLICA, offline, sem servidor.
import crypto from 'node:crypto';

export const PREFIXO = 'CC1-';
export const CONVITE_APOS_DIAS = 30;
export const CONVITE_A_CADA_DIAS = 7;
const DIA_MS = 24 * 60 * 60 * 1000;

export interface Licenca {
  nome: string;
  emitida: string; // AAAA-MM-DD
  id: string;
}

const base64url = (b: Buffer) => b.toString('base64url');

/** Os bytes assinados: o JSON dos dados (a mesma string na emissão e na conferência). */
export function dadosDaLicenca(licenca: Licenca): string {
  return JSON.stringify({ v: 1, nome: licenca.nome, emitida: licenca.emitida, id: licenca.id });
}

/** Emite uma chave (usado pelo script de quem vende e pelos testes; o app nunca emite). */
export function emitir(licenca: Licenca, chavePrivada: crypto.KeyObject | string): string {
  const dados = Buffer.from(dadosDaLicenca(licenca), 'utf8');
  const assinatura = crypto.sign(null, dados, chavePrivada);
  return `${PREFIXO}${base64url(dados)}.${base64url(assinatura)}`;
}

/** Confere uma chave colada pelo usuário; lança Error com mensagem para a tela. */
export function verificar(chave: unknown, chavePublica: crypto.KeyObject | string): Licenca {
  if (typeof chave !== 'string') throw new Error('Chave inválida.');
  const limpa = chave.replace(/\s+/g, ''); // e-mails costumam quebrar a chave em linhas
  if (!limpa.startsWith(PREFIXO) || limpa.length > 2000)
    throw new Error('Isso não parece uma chave do CleanChain (começa com CC1-).');
  const [dadosB64, assinaturaB64, sobra] = limpa.slice(PREFIXO.length).split('.');
  if (!dadosB64 || !assinaturaB64 || sobra !== undefined) throw new Error('Chave incompleta: confira se copiou ela inteira.');

  const dados = Buffer.from(dadosB64, 'base64url');
  const assinatura = Buffer.from(assinaturaB64, 'base64url');
  let valida: boolean;
  try {
    valida = crypto.verify(null, dados, chavePublica, assinatura);
  } catch {
    valida = false;
  }
  if (!valida) throw new Error('Chave inválida: confira se copiou ela inteira, do jeito que veio.');

  let licenca: Partial<Licenca> & { v?: unknown };
  try {
    licenca = JSON.parse(dados.toString('utf8'));
  } catch {
    throw new Error('Chave inválida.');
  }
  const { nome, emitida, id } = licenca;
  if (
    licenca.v !== 1 ||
    typeof nome !== 'string' ||
    !nome.trim() ||
    nome.length > 120 ||
    typeof emitida !== 'string' ||
    typeof id !== 'string'
  ) {
    throw new Error('Chave de uma versão que este app não conhece.');
  }
  return { nome: nome.trim(), emitida, id };
}

/** Mostrar o convite agora? Sem licença, depois de 30 dias de uso e no máximo 1 vez por semana. */
export function deveConvidar(o: {
  licenciado: boolean;
  primeiroUso: number;
  ultimoConvite: number | null;
  agora: number;
}): boolean {
  if (o.licenciado) return false;
  if (o.agora - o.primeiroUso < CONVITE_APOS_DIAS * DIA_MS) return false;
  return o.ultimoConvite === null || o.agora - o.ultimoConvite >= CONVITE_A_CADA_DIAS * DIA_MS;
}
