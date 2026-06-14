// vite.config.js - version corrigée
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        ws: true,
        timeout: 60000,
        configure: (proxy) => {
          proxy.on('error', (err, req, res) => {
            console.log('proxy error', err.message);
            if (res && !res.headersSent) {
              res.writeHead(502, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ 
                detail: 'Backend server unreachable. Please start the FastAPI server on port 8000.' 
              }));
            }
          });
          proxy.on('proxyReq', (proxyReq, req) => {
            console.log(`[Proxy] ${req.method} ${req.url} → ${proxyReq.path}`);
          });
          proxy.on('proxyRes', (proxyRes, req) => {
            console.log(`[Proxy Response] ${proxyRes.statusCode} ← ${req.url}`);
          });
        }
      },
    },
  },
});