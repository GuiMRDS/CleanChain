import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Backend FastAPI do agente. No navegador: uv run uvicorn app.server:app --port 8000.
// No app desktop em desenvolvimento (desktop/: npm run dev), o Electron inicia o backend na
// porta CLEANCHAIN_PORTA_DEV e abre /bootstrap por aqui, para o cookie de sessão ficar nesta origem.
const backend = `http://127.0.0.1:${process.env.CLEANCHAIN_PORTA_DEV || 8000}`;

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': backend,
      '/bootstrap': backend,
      '/health': backend,
    },
  },
});
