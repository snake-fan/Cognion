import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return
          }

          if (id.includes('react-pdf') || id.includes('pdfjs-dist')) {
            return 'pdf-vendor'
          }

          if (id.includes('highlight.js')) {
            return 'highlight-vendor'
          }

          if (
            id.includes('react-markdown') ||
            id.includes('remark-math') ||
            id.includes('rehype-katex') ||
            id.includes('rehype-highlight') ||
            id.includes('katex')
          ) {
            return 'markdown-vendor'
          }

          if (id.includes('react') || id.includes('scheduler')) {
            return 'react-vendor'
          }
        }
      }
    }
  }
})
