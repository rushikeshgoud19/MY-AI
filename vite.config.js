import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: '.',
  base: './',
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: false,
    rollupOptions: {
      input: 'index.html'
    }
  },
  server: {
    port: 1420,
    strictPort: true
  },
  optimizeDeps: {
    include: ['three', '@pixiv/three-vrm']
  }
});