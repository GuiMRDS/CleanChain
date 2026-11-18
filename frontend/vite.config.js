import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    // FastAPI agent backend (backend/: uv run uvicorn app.server:app --port 8000)
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
});
