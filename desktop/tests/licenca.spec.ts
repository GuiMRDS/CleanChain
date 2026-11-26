// Licença opcional (modelo WinRAR): regras puras de desktop/main/licenca-regras.ts (não abre o app).
import { expect, test } from '@playwright/test';
import crypto from 'node:crypto';
import { CHAVE_PUBLICA } from '../main/licenca-chave-publica';
import { deveConvidar, emitir, verificar } from '../main/licenca-regras';

const { privateKey, publicKey } = crypto.generateKeyPairSync('ed25519');
const DIA = 24 * 60 * 60 * 1000;
const ana = { nome: 'Ana Souza', emitida: '2026-11-26', id: 'x1' };

test('uma chave emitida com a chave privada é aceita, mesmo quebrada em linhas', () => {
  const chave = emitir(ana, privateKey);
  expect(chave.startsWith('CC1-')).toBe(true);
  expect(verificar(chave, publicKey)).toEqual(ana);
  const quebrada = `  ${chave.slice(0, 30)}\n${chave.slice(30, 60)}\r\n${chave.slice(60)}  `;
  expect(verificar(quebrada, publicKey)).toEqual(ana);
});

test('chave adulterada, de outra chave privada ou mal formada é recusada', () => {
  const chave = emitir(ana, privateKey);
  const [dados, assinatura] = chave.slice(4).split('.');
  const outroNome = Buffer.from(JSON.stringify({ v: 1, nome: 'Outra Pessoa', emitida: ana.emitida, id: ana.id })).toString(
    'base64url'
  );
  expect(() => verificar(`CC1-${outroNome}.${assinatura}`, publicKey)).toThrow('Chave inválida');

  const outra = crypto.generateKeyPairSync('ed25519').privateKey;
  expect(() => verificar(emitir(ana, outra), publicKey)).toThrow('Chave inválida');

  expect(() => verificar('XYZ-123', publicKey)).toThrow('começa com CC1-');
  expect(() => verificar(`CC1-${dados}`, publicKey)).toThrow('incompleta');
  expect(() => verificar(`CC1-${dados}.${assinatura}.extra`, publicKey)).toThrow('incompleta');
  expect(() => verificar(12345, publicKey)).toThrow('Chave inválida');
});

test('a chave pública do app é Ed25519 e não aceita chaves de teste', () => {
  expect(crypto.createPublicKey(CHAVE_PUBLICA).asymmetricKeyType).toBe('ed25519');
  expect(() => verificar(emitir(ana, privateKey), CHAVE_PUBLICA)).toThrow('Chave inválida');
});

test('convite: só sem licença, depois de 30 dias de uso e no máximo 1 vez por semana', () => {
  const inicio = Date.UTC(2026, 0, 1);
  const base = { licenciado: false, primeiroUso: inicio, ultimoConvite: null };
  expect(deveConvidar({ ...base, agora: inicio + 29 * DIA })).toBe(false); // ainda no primeiro mês
  expect(deveConvidar({ ...base, agora: inicio + 30 * DIA })).toBe(true);
  expect(deveConvidar({ ...base, licenciado: true, agora: inicio + 300 * DIA })).toBe(false);
  const fechado = inicio + 31 * DIA;
  expect(deveConvidar({ ...base, ultimoConvite: fechado, agora: fechado + 6 * DIA })).toBe(false); // fechou há 6 dias
  expect(deveConvidar({ ...base, ultimoConvite: fechado, agora: fechado + 7 * DIA })).toBe(true);
});
