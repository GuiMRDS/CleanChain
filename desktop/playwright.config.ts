import { defineConfig } from '@playwright/test';

// Teste de fumaça do app Electron (tests/fumaca.spec.ts). Um app por vez: cada teste abre e
// fecha o CleanChain inteiro, com o backend de verdade.
export default defineConfig({
  testDir: 'tests',
  timeout: 120_000,
  workers: 1,
  retries: 0,
  reporter: [['list']],
});
