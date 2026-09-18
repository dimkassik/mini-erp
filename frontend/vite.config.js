import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  // все запросы /api/... фронт пересылает на бэкенд (FastAPI на порту 8000)
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
