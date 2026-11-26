// Qual IA o agente usa: a da nuvem (Groq/OpenAI, chave em segredos.ts) ou uma IA local
// (Ollama/LM Studio neste computador). A escolha fica em userData/ia.json (sem segredo nenhum);
// trocar para a local não apaga a chave da nuvem, para dar para voltar sem digitar de novo.
import log from 'electron-log/main';
import fs from 'node:fs';
import path from 'node:path';
import { pastaDados } from './caminhos';
import {
  LOCAIS,
  type ModeloLocal,
  modelosDoLmStudio,
  modelosDoOllama,
  ollamaConversa,
  ollamaUsaFerramentas,
  type ProvedorLocal,
  urlLocal,
  validarLocal,
  validarPorta,
  ehLocal,
} from './ia-local';
import * as segredos from './segredos';

const logIa = log.scope('ia');
const TEMPO_LIMITE_MS = 4000;

interface Escolha {
  ativo: 'nuvem' | ProvedorLocal;
  local?: { provedor: ProvedorLocal; modelo: string; porta: number };
}

const arquivo = () => path.join(pastaDados(), 'ia.json');

function ler(): Escolha {
  try {
    const dados = JSON.parse(fs.readFileSync(arquivo(), 'utf8'));
    if (dados?.ativo === 'nuvem') return { ativo: 'nuvem', local: lerLocal(dados.local) };
    const local = lerLocal(dados?.local);
    if (ehLocal(dados?.ativo) && local?.provedor === dados.ativo) return { ativo: dados.ativo, local };
  } catch {
    /* sem escolha gravada: nuvem (comportamento de antes) */
  }
  return { ativo: 'nuvem' };
}

function lerLocal(local: unknown): Escolha['local'] {
  try {
    const l = local as { provedor?: unknown; modelo?: unknown; porta?: unknown };
    return validarLocal(l?.provedor, l?.modelo, l?.porta);
  } catch {
    return undefined;
  }
}

function gravar(escolha: Escolha): void {
  fs.mkdirSync(pastaDados(), { recursive: true });
  const tmp = `${arquivo()}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(escolha, null, 2), { encoding: 'utf8', mode: 0o600 });
  fs.renameSync(tmp, arquivo());
}

/** O que a interface precisa saber (nunca a chave). Mantém os campos de antes de segredos.status(). */
export function status() {
  const nuvem = segredos.status();
  const escolha = ler();
  const local = escolha.local ? { ...escolha.local, nome: LOCAIS[escolha.local.provedor].nome } : null;
  if (escolha.ativo !== 'nuvem') {
    return {
      ...nuvem,
      configurada: true,
      provedor: escolha.ativo,
      ativo: escolha.ativo,
      local,
      nuvemConfigurada: nuvem.configurada,
      provedorNuvem: nuvem.provedor,
    };
  }
  return { ...nuvem, ativo: 'nuvem' as const, local, nuvemConfigurada: nuvem.configurada, provedorNuvem: nuvem.provedor };
}

/** Variáveis do backend: só as da IA escolhida (no modo local, a chave da nuvem não vai junto). */
export function envDoBackend(): Record<string, string> {
  const escolha = ler();
  if (escolha.ativo !== 'nuvem' && escolha.local) {
    return {
      LLM_PROVIDER: escolha.local.provedor,
      LOCAL_LLM_URL: urlLocal(escolha.local.porta),
      LOCAL_LLM_MODEL: escolha.local.modelo,
    };
  }
  return segredos.envDoBackend();
}

/** Passa a usar a IA local escolhida (quem chama reinicia o backend). */
export function usarLocal(provedor: unknown, modelo: unknown, porta: unknown): ProvedorLocal {
  const local = validarLocal(provedor, modelo, porta);
  gravar({ ativo: local.provedor, local });
  logIa.info(`IA local: ${LOCAIS[local.provedor].nome} · ${local.modelo} (porta ${local.porta})`);
  return local.provedor;
}

/** Volta para a nuvem (chave já salva). Quem chama reinicia o backend. */
export function usarNuvem(): void {
  if (!segredos.status().configurada) throw new Error('Não há chave da nuvem salva: cole uma chave da Groq ou da OpenAI.');
  gravar({ ...ler(), ativo: 'nuvem' });
  logIa.info('IA da nuvem');
}

async function pedir(url: string, init?: RequestInit): Promise<unknown> {
  const r = await fetch(url, { ...init, signal: AbortSignal.timeout(TEMPO_LIMITE_MS) });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

/** Modelos instalados no servidor local (só 127.0.0.1). Lança Error com mensagem para a tela. */
export async function modelosLocais(provedor: unknown, porta: unknown): Promise<ModeloLocal[]> {
  if (!ehLocal(provedor)) throw new Error('Provedor local inválido.');
  const p = validarPorta(porta ?? LOCAIS[provedor].porta);
  const base = urlLocal(p);
  const { nome } = LOCAIS[provedor];
  try {
    if (provedor === 'ollama') {
      const nomes = modelosDoOllama(await pedir(`${base}/api/tags`));
      const detalhes = await Promise.all(
        nomes.map(async (modelo) => ({
          modelo,
          show: await pedir(`${base}/api/show`, { method: 'POST', body: JSON.stringify({ model: modelo }) }).catch(() => null),
        }))
      );
      return detalhes
        .filter((d) => ollamaConversa(d.show))
        .map((d) => ({ nome: d.modelo, ferramentas: ollamaUsaFerramentas(d.show) }));
    }
    // LM Studio: /api/v0/models informa se o modelo usa ferramentas; versões antigas só têm /v1/models.
    return modelosDoLmStudio(await pedir(`${base}/api/v0/models`).catch(() => pedir(`${base}/v1/models`)));
  } catch {
    throw new Error(
      provedor === 'ollama'
        ? `Não encontrei o ${nome} em ${base}. Abra o ${nome} e tente de novo.`
        : `Não encontrei o servidor do ${nome} em ${base}. No ${nome}, ligue o servidor local (Developer › Start Server) e tente de novo.`
    );
  }
}
