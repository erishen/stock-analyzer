import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'

// 读取项目根 .env 的 WEB_PORT / VITE_PORT, 与后端 make web / make dev 保持一致
function readEnv(name: string, fallback: string): string {
  try {
    const env = readFileSync(fileURLToPath(new URL('../.env', import.meta.url)), 'utf-8')
    const m = env.match(new RegExp(`^${name}=(\\d+)`, 'm'))
    if (m) return m[1]
  } catch {
    // .env 不存在时用默认值
  }
  return fallback
}

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: Number(readEnv('VITE_PORT', '3000')),
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${readEnv('WEB_PORT', '8001')}`,
        changeOrigin: true,
        // AI 选股等接口需多次调用 LLM, 单次可达 1 分钟以上; 放宽 proxy 超时避免 Failed to fetch
        timeout: 180000,
        proxyTimeout: 180000,
      },
    },
  },
  build: {
    outDir: '../src/web/static',
    emptyOutDir: true,
  },
})
