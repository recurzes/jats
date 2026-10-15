/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      // Mirrors `paths` in tsconfig.app.json.
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    // Tests never read web/.env; the mock API answers at this URL.
    env: {
      VITE_API_URL: 'http://api.test',
      VITE_NEON_AUTH_URL: 'https://auth.example.com/neondb/auth',
      VITE_USE_MOCKS: 'false',
    },
  },
})
