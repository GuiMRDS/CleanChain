// Onde ficam as coisas no app empacotado e em desenvolvimento.
import { app } from 'electron';
import path from 'node:path';

/** Raiz do repositório (só em desenvolvimento): desktop/dist/main → ../../.. */
export const REPO = path.resolve(__dirname, '..', '..', '..');

/** Interface do Vite em desenvolvimento (ex.: http://localhost:5173); ausente no app empacotado. */
export function urlDev(): string | undefined {
  return app.isPackaged ? undefined : process.env.CLEANCHAIN_DEV_URL || undefined;
}

/** Pasta de dados do usuário: %APPDATA%\CleanChain (scans, chave cifrada, logs). */
export function pastaDados(): string {
  return app.getPath('userData');
}

/** Pasta do app instalado (protegida contra exclusão pelo backend). */
export function pastaInstalacao(): string | undefined {
  return app.isPackaged ? path.dirname(process.execPath) : undefined;
}

export interface ComandoBackend {
  cmd: string;
  args: string[];
  cwd: string;
}

/**
 * Como iniciar o backend: o executável do PyInstaller no app empacotado; em desenvolvimento,
 * `uv run python -m app.desktop` (ou CLEANCHAIN_PYTHON, se o uv não funcionar na máquina).
 */
export function comandoBackend(): ComandoBackend {
  if (app.isPackaged) {
    const dir = path.join(process.resourcesPath, 'backend');
    return { cmd: path.join(dir, 'cleanchain-backend.exe'), args: [], cwd: dir };
  }
  const cwd = path.join(REPO, 'backend');
  const python = process.env.CLEANCHAIN_PYTHON;
  if (python) return { cmd: python, args: ['-m', 'app.desktop'], cwd };
  return { cmd: 'uv', args: ['run', 'python', '-m', 'app.desktop'], cwd };
}
