import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  base: './',
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