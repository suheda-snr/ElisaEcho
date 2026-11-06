import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  // Server-side only (never exposed to the browser): where the dev server
  // forwards /api requests. Inside Docker Compose this is the backend service.
  const proxyTarget = env.API_PROXY_TARGET ?? 'http://localhost:8000'

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(import.meta.dirname, './src'),
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
      watch: {
        // Bind-mounted files on Docker Desktop (Windows/macOS) do not always
        // emit native file events, so polling can be enabled via env.
        usePolling: env.VITE_USE_POLLING === 'true',
        interval: 300,
      },
    },
  }
})
