// Fila dos comandos de tela do agente: um de cada vez, com intervalo para cada pasta ser vista.
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UI_STEP_MS, useFilaDeTela } from './useFilaDeTela.js';

const abrir = (path) => ({ type: 'ui', command: 'focus_folder', args: { path } });

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('useFilaDeTela', () => {
  it('aplica o primeiro comando na hora e os seguintes a cada UI_STEP_MS', () => {
    const { result } = renderHook(() => useFilaDeTela());
    act(() => {
      result.current.receber(abrir('C:\\A'));
      result.current.receber(abrir('C:\\B'));
      result.current.receber(abrir('C:\\C'));
    });
    expect(result.current.comando.path).toBe('C:\\A');

    act(() => vi.advanceTimersByTime(UI_STEP_MS - 1));
    expect(result.current.comando.path).toBe('C:\\A');
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.comando.path).toBe('C:\\B');
    act(() => vi.advanceTimersByTime(UI_STEP_MS));
    expect(result.current.comando.path).toBe('C:\\C');
  });

  it('cada comando é novo, mesmo para a mesma pasta (o mapa reage de novo)', () => {
    const { result } = renderHook(() => useFilaDeTela());
    act(() => result.current.receber(abrir('C:\\A')));
    const primeiro = result.current.comando;
    act(() => vi.advanceTimersByTime(UI_STEP_MS));
    act(() => result.current.receber(abrir('C:\\A')));
    expect(result.current.comando).not.toBe(primeiro);
    expect(result.current.comando.seq).not.toBe(primeiro.seq);
  });

  it('ignora comandos que não são de abrir pasta', () => {
    const { result } = renderHook(() => useFilaDeTela());
    act(() => result.current.receber({ type: 'ui', command: 'outra_coisa', args: {} }));
    expect(result.current.comando).toBeNull();
  });

  it('limpar descarta o que estava na fila (scan novo começa do mapa limpo)', () => {
    const { result } = renderHook(() => useFilaDeTela());
    act(() => {
      result.current.receber(abrir('C:\\A'));
      result.current.receber(abrir('C:\\B'));
    });
    act(() => result.current.limpar());
    expect(result.current.comando).toBeNull();
    act(() => vi.advanceTimersByTime(UI_STEP_MS * 3));
    expect(result.current.comando).toBeNull(); // C:\B não aparece depois
  });
});
