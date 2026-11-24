// Chave do LLM cifrada com safeStorage (DPAPI no Windows), em userData/segredos.json.
// A chave nunca é gravada em texto puro, nem em log, nem devolvida à interface.
import { safeStorage } from 'electron';
import fs from 'node:fs';
import path from 'node:path';
import { pastaDados } from './caminhos';
import { cofreSeguro } from './plataforma';

export type Provedor = 'groq' | 'openai';
export const PROVEDORES: Record<Provedor, { prefixo: string; variavel: string }> = {
  groq: { prefixo: 'gsk_', variavel: 'GROQ_API_KEY' },
  openai: { prefixo: 'sk-', variavel: 'OPENAI_API_KEY' },
};

interface Arquivo {
  provedor: Provedor;
  cifrada: string; // base64 do safeStorage.encryptString
}

const arquivo = () => path.join(pastaDados(), 'segredos.json');

function ler(): Arquivo | undefined {
  try {
    const dados = JSON.parse(fs.readFileSync(arquivo(), 'utf8'));
    if (dados && dados.provedor in PROVEDORES && typeof dados.cifrada === 'string') return dados;
  } catch {
    /* sem chave ainda */
  }
  return undefined;
}

/** Valida provedor e chave vindos da interface; lança Error com mensagem para o usuário. */
export function validar(provedor: unknown, chave: unknown): { provedor: Provedor; chave: string } {
  if (typeof provedor !== 'string' || !(provedor in PROVEDORES)) throw new Error('Provedor inválido.');
  if (typeof chave !== 'string') throw new Error('Chave inválida.');
  const limpa = chave.trim();
  const { prefixo } = PROVEDORES[provedor as Provedor];
  if (limpa.length < 20 || limpa.length > 300 || !/^[A-Za-z0-9_\-.]+$/.test(limpa)) {
    throw new Error('Essa chave não parece válida: confira se copiou ela inteira.');
  }
  if (!limpa.startsWith(prefixo)) throw new Error(`Chaves desse provedor começam com ${prefixo}`);
  return { provedor: provedor as Provedor, chave: limpa };
}

export function status(): { configurada: boolean; provedor: Provedor | null; cofre: boolean; motivoCofre?: string } {
  const dados = ler();
  const cofre = cofreSeguro();
  // Configurada = existe E dá para decifrar (um perfil copiado de outra máquina não dá).
  return {
    configurada: Object.keys(envDoBackend()).length > 0,
    provedor: dados?.provedor ?? null,
    cofre: cofre.ok,
    ...(cofre.motivo ? { motivoCofre: cofre.motivo } : {}),
  };
}

export function salvar(provedor: Provedor, chave: string): void {
  // Sem um cofre de verdade (Linux sem GNOME Keyring/KWallet), não salva: seria texto puro.
  const cofre = cofreSeguro();
  if (!cofre.ok) throw new Error(cofre.motivo ?? 'Não dá para guardar a chave com segurança neste sistema.');
  const dados: Arquivo = { provedor, cifrada: safeStorage.encryptString(chave).toString('base64') };
  fs.mkdirSync(pastaDados(), { recursive: true });
  const tmp = `${arquivo()}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(dados), { encoding: 'utf8', mode: 0o600 });
  fs.renameSync(tmp, arquivo());
}

export function remover(): void {
  fs.rmSync(arquivo(), { force: true });
}

/** Variáveis de ambiente para o backend (vazio se não houver chave). */
export function envDoBackend(): Record<string, string> {
  const dados = ler();
  if (!dados || !cofreSeguro().ok) return {};
  try {
    const chave = safeStorage.decryptString(Buffer.from(dados.cifrada, 'base64'));
    return { LLM_PROVIDER: dados.provedor, [PROVEDORES[dados.provedor].variavel]: chave };
  } catch {
    return {}; // cifrada por outro usuário/máquina: pede de novo na tela de configuração
  }
}
