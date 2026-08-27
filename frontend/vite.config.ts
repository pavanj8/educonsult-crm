/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-only: the app's apiFetch uses same-origin relative paths (API_BASE=''),
// so proxy the backend's top-level API prefixes to the FastAPI server. Keeps
// the browser same-origin (no CORS needed) for local full-stack runs.
const API_PREFIXES = [
  '/auth',
  '/applications',
  '/verifier',
  '/notifications',
  '/branches',
  '/staff',
  '/tenants',
  '/meetings',
  '/health',
]
const BACKEND = process.env.VITE_DEV_BACKEND ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(
      API_PREFIXES.map((p) => [p, { target: BACKEND, changeOrigin: true }]),
    ),
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    exclude: ['**/node_modules/**', '**/dist/**', 'e2e/**'],
    // Several suites convert a datetime-local value to a UTC timestamp and
    // assert on the exact result, which only holds if the run's local zone is
    // UTC. CI happens to be UTC, so without this they pass there and fail for
    // anyone developing in another zone. Pin it so the two agree.
    env: { TZ: 'UTC' },
  },
})
