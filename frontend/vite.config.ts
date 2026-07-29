import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // 新闻搜索含联网 + 本地 LLM，常超过默认代理超时
        timeout: 300_000,
        proxyTimeout: 300_000,
      },
    },
  },
});
