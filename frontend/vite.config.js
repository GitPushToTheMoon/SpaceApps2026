import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// In dev, /api/* and /library go to the FastAPI backend (uvicorn on port 8000).
// When deployed, set VITE_API_URL to the backend URL instead (see src/services/config.js).
const backend = process.env.BACKEND_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': backend,
      '/library': backend,
    },
  },
})
