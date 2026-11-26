// IA local (Ollama / LM Studio): regras puras, sem Electron, para serem testadas à parte
// (desktop/tests/ia-local.spec.ts). Quem fala com os servidores e grava a escolha é ia.ts.

export type ProvedorLocal = 'ollama' | 'lmstudio';

export const LOCAIS: Record<ProvedorLocal, { nome: string; porta: number }> = {
  ollama: { nome: 'Ollama', porta: 11434 },
  lmstudio: { nome: 'LM Studio', porta: 1234 },
};

export interface ModeloLocal {
  nome: string;
  /** true/false se o servidor informa; null se não dá para saber (o agente precisa de ferramentas). */
  ferramentas: boolean | null;
}

export function ehLocal(provedor: unknown): provedor is ProvedorLocal {
  return typeof provedor === 'string' && provedor in LOCAIS;
}

/** Valida o que vem da interface; lança Error com mensagem para o usuário. */
export function validarLocal(
  provedor: unknown,
  modelo: unknown,
  porta: unknown
): { provedor: ProvedorLocal; modelo: string; porta: number } {
  if (!ehLocal(provedor)) throw new Error('Provedor local inválido.');
  const p = validarPorta(porta ?? LOCAIS[provedor].porta);
  if (typeof modelo !== 'string' || !modelo.trim() || modelo.length > 200 || /[\r\n\0]/.test(modelo)) {
    throw new Error('Escolha um modelo da lista.');
  }
  return { provedor, modelo: modelo.trim(), porta: p };
}

export function validarPorta(porta: unknown): number {
  const n = typeof porta === 'string' && /^\d+$/.test(porta.trim()) ? Number(porta) : porta;
  if (typeof n !== 'number' || !Number.isInteger(n) || n < 1 || n > 65535) throw new Error('Porta inválida.');
  return n;
}

/** Endereço do servidor: sempre neste computador. */
export function urlLocal(porta: number): string {
  return `http://127.0.0.1:${porta}`;
}

/** Ollama: GET /api/tags → nomes dos modelos. */
export function modelosDoOllama(tags: unknown): string[] {
  const lista = (tags as { models?: Array<{ name?: unknown }> })?.models;
  return Array.isArray(lista) ? lista.map((m) => m?.name).filter((n): n is string => typeof n === 'string') : [];
}

/** Ollama: POST /api/show → o modelo sabe usar ferramentas? (null se a versão não informa) */
export function ollamaUsaFerramentas(show: unknown): boolean | null {
  const caps = (show as { capabilities?: unknown })?.capabilities;
  return Array.isArray(caps) ? caps.includes('tools') : null;
}

/** Ollama: o modelo conversa? (os só de embeddings, como nomic-embed-text, não servem para o agente) */
export function ollamaConversa(show: unknown): boolean {
  const caps = (show as { capabilities?: unknown })?.capabilities;
  return !Array.isArray(caps) || caps.includes('completion');
}

/** LM Studio: GET /api/v0/models (com capacidades) ou /v1/models (só os nomes). */
export function modelosDoLmStudio(resposta: unknown): ModeloLocal[] {
  const dados = (resposta as { data?: Array<Record<string, unknown>> })?.data;
  if (!Array.isArray(dados)) return [];
  return dados
    .filter((m) => typeof m?.id === 'string' && m.type !== 'embeddings' && !String(m.id).includes('embed'))
    .map((m) => ({
      nome: m.id as string,
      ferramentas: Array.isArray(m.capabilities) ? (m.capabilities as unknown[]).includes('tool_use') : null,
    }));
}
