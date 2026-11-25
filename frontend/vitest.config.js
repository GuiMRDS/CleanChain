import { defineConfig } from 'vitest/config';

// Testes da interface: o contrato do chat e os fluxos de aprovação (não testes de visual).
export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{js,jsx}'],
  },
});
