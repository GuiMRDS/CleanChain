// Mapa de pastas: comandos do agente abrem a pasta (com o selo por um momento) e um scan novo
// volta para a raiz. O backend da tabela de arquivos é simulado pelo fetch.
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Sunburst from './Sunburst.jsx';

const pasta = (name, path, bytes, children = []) => ({ name, path, bytes, size: `${bytes} B`, files: 1, children });

const scan = (raiz = 'C:\\Users\\ana') => ({
  root: raiz,
  total_bytes: 1000,
  tree: pasta('ana', raiz, 1000, [
    pasta('Videos', `${raiz}\\Videos`, 600, [pasta('Aulas', `${raiz}\\Videos\\Aulas`, 400)]),
    pasta('Downloads', `${raiz}\\Downloads`, 400),
  ]),
});

const aberta = () => screen.getByRole('navigation', { name: 'Pasta aberta' }).textContent;
const selo = () => screen.queryByText(/aberta pelo agente/);

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({ files: [], total_files: 0, total: '0 B' })))
  );
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('Sunburst', () => {
  it('um comando do agente abre a pasta e mostra o selo por um momento', () => {
    const dados = scan();
    const { rerender } = render(<Sunburst scan={dados} command={null} />);
    expect(selo()).toBeNull();

    rerender(<Sunburst scan={dados} command={{ seq: 1, path: 'C:\\Users\\ana\\Videos' }} />);
    expect(aberta()).toContain('Videos');
    expect(selo()).not.toBeNull();

    act(() => vi.advanceTimersByTime(3800));
    expect(selo()).toBeNull();
    expect(aberta()).toContain('Videos'); // a pasta continua aberta; só o selo some
  });

  it('o mesmo comando não é reaplicado; um comando novo para a mesma pasta é', () => {
    const dados = scan();
    const comando = { seq: 1, path: 'C:\\Users\\ana\\Downloads' };
    const { rerender } = render(<Sunburst scan={dados} command={comando} />);
    act(() => vi.advanceTimersByTime(3800));
    rerender(<Sunburst scan={dados} command={comando} />);
    expect(selo()).toBeNull();

    rerender(<Sunburst scan={dados} command={{ seq: 2, path: 'C:\\Users\\ana\\Downloads' }} />);
    expect(selo()).not.toBeNull();
  });

  it('caminho com outras maiúsculas abre a mesma pasta (Windows/macOS)', () => {
    const dados = scan();
    const { rerender } = render(<Sunburst scan={dados} command={null} />);
    rerender(<Sunburst scan={dados} command={{ seq: 1, path: 'c:\\users\\ANA\\videos' }} />);
    expect(aberta()).toContain('Videos');
  });

  it('pasta que não está no mapa não muda nada', () => {
    const dados = scan();
    const { rerender } = render(<Sunburst scan={dados} command={null} />);
    const antes = aberta();
    rerender(<Sunburst scan={dados} command={{ seq: 1, path: 'D:\\Outro' }} />);
    expect(aberta()).toBe(antes);
    expect(selo()).toBeNull();
  });

  it('um scan novo volta o mapa para a raiz', () => {
    const comando = { seq: 1, path: 'C:\\Users\\ana\\Videos' };
    const { rerender } = render(<Sunburst scan={scan()} command={comando} />);
    expect(aberta()).toContain('Videos');
    // Como no app: ao começar um scan, a fila do agente é limpa (useFilaDeTela.limpar → null).
    rerender(<Sunburst scan={scan()} command={null} />);
    expect(aberta()).not.toContain('Videos');
  });
});
