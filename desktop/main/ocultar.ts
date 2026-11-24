// Tira segredos de textos que vão para o log (a saída do backend é gravada inteira, e um erro do
// provedor pode repetir a chave). Módulo puro, sem Electron, para ser testado à parte.

/** Formatos das chaves dos provedores (Groq: gsk_…, OpenAI: sk-… / sk-proj-…). Igual ao backend. */
const FORMATO_CHAVE = /\b(?:gsk_|sk-)[A-Za-z0-9_-]{8,}/g;

/** Devolve uma função que troca por *** os valores dados (chave, tokens) e qualquer coisa com formato de chave. */
export function criarOcultador(segredos: Iterable<string | undefined>): (texto: string) => string {
  const valores = [...segredos].filter((s): s is string => typeof s === 'string' && s.length >= 8);
  return (texto: string) => {
    let saida = texto;
    for (const valor of valores) saida = saida.split(valor).join('***');
    return saida.replace(FORMATO_CHAVE, '***');
  };
}
