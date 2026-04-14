import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ws': {  // Proxy WebSocket to API Service
        target: 'ws://localhost:5001',
        ws: true
      },
      '/api': {  // Proxy REST to API Service
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})