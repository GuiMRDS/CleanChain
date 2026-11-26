// IA local (Ollama / LM Studio): regras puras de desktop/main/ia-local.ts (não abre o app).
import { expect, test } from '@playwright/test';
import {
  modelosDoLmStudio,
  modelosDoOllama,
  ollamaConversa,
  ollamaUsaFerramentas,
  urlLocal,
  validarLocal,
  validarPorta,
} from '../main/ia-local';

test('valida provedor, modelo e porta da IA local', () => {
  expect(validarLocal('ollama', ' qwen3:8b ', 11434)).toEqual({ provedor: 'ollama', modelo: 'qwen3:8b', porta: 11434 });
  expect(validarLocal('lmstudio', 'gemma-3-12b', undefined).porta).toBe(1234); // porta padrão
  expect(() => validarLocal('groq', 'x', 1)).toThrow('Provedor local inválido');
  expect(() => validarLocal('ollama', '', 11434)).toThrow('Escolha um modelo');
  expect(() => validarLocal('ollama', 'a\nb', 11434)).toThrow('Escolha um modelo');
  for (const porta of [0, 70000, -1, 1.5, 'abc', '80; rm']) expect(() => validarPorta(porta)).toThrow('Porta inválida');
  expect(validarPorta('8080')).toBe(8080);
});

test('o servidor local é sempre este computador', () => {
  expect(urlLocal(11434)).toBe('http://127.0.0.1:11434');
});

test('lê os modelos e as capacidades do Ollama', () => {
  expect(modelosDoOllama({ models: [{ name: 'qwen3:8b' }, { name: 3 }, {}] })).toEqual(['qwen3:8b']);
  expect(modelosDoOllama({})).toEqual([]);
  expect(ollamaUsaFerramentas({ capabilities: ['completion', 'tools'] })).toBe(true);
  expect(ollamaUsaFerramentas({ capabilities: ['completion'] })).toBe(false);
  expect(ollamaUsaFerramentas({})).toBeNull(); // versão antiga: não dá para saber
  // Modelos só de embeddings (nomic-embed-text) não conversam: ficam fora da lista.
  expect(ollamaConversa({ capabilities: ['embedding'] })).toBe(false);
  expect(ollamaConversa({ capabilities: ['completion', 'tools', 'thinking'] })).toBe(true);
  expect(ollamaConversa({})).toBe(true);
});

test('lê os modelos do LM Studio e ignora os de embeddings', () => {
  const v0 = {
    data: [
      { id: 'qwen3-8b', type: 'llm', capabilities: ['tool_use'] },
      { id: 'gemma-3-1b', type: 'vlm', capabilities: [] },
      { id: 'text-embedding-nomic', type: 'embeddings' },
    ],
  };
  expect(modelosDoLmStudio(v0)).toEqual([
    { nome: 'qwen3-8b', ferramentas: true },
    { nome: 'gemma-3-1b', ferramentas: false },
  ]);
  // /v1/models (versões antigas): só nomes.
  expect(modelosDoLmStudio({ data: [{ id: 'mistral-7b' }, { id: 'nomic-embed-text' }] })).toEqual([
    { nome: 'mistral-7b', ferramentas: null },
  ]);
});
