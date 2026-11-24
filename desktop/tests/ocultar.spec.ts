// Invariante 11: a chave do LLM (e os tokens) nunca vão para o log. Teste unitário do filtro que
// o Electron aplica a toda linha que o backend escreve (não abre o app).
import { expect, test } from '@playwright/test';
import { criarOcultador } from '../main/ocultar';

const CHAVE = 'gsk_ChaveDeTesteMuitoSecreta123';
const TOKEN = 'token-de-sessao-aleatorio-XYZ987';

test('a chave e os tokens em uso somem da linha de log', () => {
  const ocultar = criarOcultador([CHAVE, TOKEN, undefined]);
  const linha = `AuthenticationError: chave ${CHAVE} inválida; token=${TOKEN}`;
  const saida = ocultar(linha);
  expect(saida).not.toContain(CHAVE);
  expect(saida).not.toContain(TOKEN);
  expect(saida).toBe('AuthenticationError: chave *** inválida; token=***');
});

test('qualquer coisa com formato de chave de API também some', () => {
  const ocultar = criarOcultador([]);
  expect(ocultar('Incorrect API key provided: sk-proj-abcDEF123456_xyz')).toBe('Incorrect API key provided: ***');
  expect(ocultar('chave gsk_1234567890abcdef no erro')).toBe('chave *** no erro');
});

test('o resto da linha fica como está', () => {
  const ocultar = criarOcultador(['curto']);
  const linha = 'INFO: backend iniciado na porta 51234 (task-1234567890, disk-cleanup)';
  expect(ocultar(linha)).toBe(linha);
});
