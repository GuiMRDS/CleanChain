// Licença opcional (modelo WinRAR): o app é igual para todos; a licença só tira o convite.
// Arquivos na pasta de dados: licenca.json (a chave colada) e uso.json (primeiro uso e último
// convite). Nada é enviado a lugar nenhum: a chave é conferida aqui, com a chave pública.
import { app } from 'electron';
import log from 'electron-log/main';
import fs from 'node:fs';
import path from 'node:path';
import { pastaDados } from './caminhos';
import { CHAVE_PUBLICA } from './licenca-chave-publica';
import { deveConvidar, type Licenca, verificar } from './licenca-regras';

const logLicenca = log.scope('licenca');

/** Onde comprar (página do projeto até existir uma loja). */
export const PAGINA_DE_COMPRA = 'https://github.com/GuiMRDS/CleanChain#apoie-o-cleanchain';

const arquivoLicenca = () => path.join(pastaDados(), 'licenca.json');
const arquivoUso = () => path.join(pastaDados(), 'uso.json');

/** Em desenvolvimento e nos testes dá para usar outra chave pública; no app instalado, nunca. */
function chavePublica(): string {
  const outra = process.env.CLEANCHAIN_LICENCA_CHAVE_PUBLICA;
  return !app.isPackaged && outra ? outra : CHAVE_PUBLICA;
}

function lerJson<T>(arquivo: string): Partial<T> {
  try {
    const dados = JSON.parse(fs.readFileSync(arquivo, 'utf8'));
    return dados && typeof dados === 'object' ? dados : {};
  } catch {
    return {};
  }
}

function gravarJson(arquivo: string, dados: unknown): void {
  fs.mkdirSync(path.dirname(arquivo), { recursive: true });
  const tmp = `${arquivo}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(dados, null, 2), { encoding: 'utf8', mode: 0o600 });
  fs.renameSync(tmp, arquivo);
}

function licencaAtual(): Licenca | null {
  const { chave } = lerJson<{ chave: string }>(arquivoLicenca());
  if (!chave) return null;
  try {
    return verificar(chave, chavePublica());
  } catch {
    return null; // chave adulterada ou de outra chave pública: vale como sem licença
  }
}

function uso(agora: number): { primeiroUso: number; ultimoConvite: number | null } {
  const dados = lerJson<{ primeiroUso: number; ultimoConvite: number | null }>(arquivoUso());
  const primeiroUso = typeof dados.primeiroUso === 'number' ? dados.primeiroUso : agora;
  const ultimoConvite = typeof dados.ultimoConvite === 'number' ? dados.ultimoConvite : null;
  if (dados.primeiroUso !== primeiroUso) gravarJson(arquivoUso(), { primeiroUso, ultimoConvite });
  return { primeiroUso, ultimoConvite };
}

export function status(agora = Date.now()) {
  const licenca = licencaAtual();
  const { primeiroUso, ultimoConvite } = uso(agora);
  return {
    licenciado: Boolean(licenca),
    nome: licenca?.nome ?? null,
    emitida: licenca?.emitida ?? null,
    convite: deveConvidar({ licenciado: Boolean(licenca), primeiroUso, ultimoConvite, agora }),
    paginaDeCompra: PAGINA_DE_COMPRA,
  };
}

/** Registra uma chave colada pelo usuário; lança Error com mensagem para a tela. */
export function registrar(chave: unknown) {
  const licenca = verificar(chave, chavePublica());
  gravarJson(arquivoLicenca(), { chave: String(chave).replace(/\s+/g, '') });
  logLicenca.info(`licença registrada (emitida em ${licenca.emitida})`); // nunca a chave nem o nome
  return status();
}

export function remover() {
  fs.rmSync(arquivoLicenca(), { force: true });
  logLicenca.info('licença removida deste computador');
  return status();
}

/** O usuário fechou o convite: só volta daqui a uma semana. */
export function adiarConvite(agora = Date.now()) {
  const { primeiroUso } = uso(agora);
  gravarJson(arquivoUso(), { primeiroUso, ultimoConvite: agora });
  return status(agora);
}
