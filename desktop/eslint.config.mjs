// ESLint do app Electron: a configuração recomendada do typescript-eslint (a mesma base do
// Electron Forge) + eslint-config-prettier por último (a formatação é do Prettier).
import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import { defineConfig, globalIgnores } from 'eslint/config';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default defineConfig([
  globalIgnores(['dist', 'release', 'test-results', 'playwright-report']),
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    // Processo principal, preload, testes e scripts: Node.
    files: ['**/*.{ts,mjs,js}'],
    languageOptions: { globals: globals.node },
  },
  {
    // Scripts de teste/captura: o código dentro de page.evaluate(...) roda na página do app.
    files: ['tests/**/*.mjs'],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },
  {
    // Telas locais de abertura/erro (cleanchain://tela): navegador.
    files: ['tela/**/*.js'],
    languageOptions: { globals: globals.browser },
  },
  prettier,
]);
