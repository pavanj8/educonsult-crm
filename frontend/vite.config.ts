/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-only: the app's apiFetch uses same-origin relative paths (API_BASE=''),
// so proxy the backend's top-level API prefixes to the FastAPI server. Keeps
// the browser same-origin (no CORS needed) for local full-stack runs.
const API_PREFIXES = [
  '/analytics',
  '/applications',
  '/auth',
  '/billing',
  '/branches',
  '/checklist-templates',
  '/health',
  '/meetings',
  '/notifications',
  '/staff',
  '/students',
  '/tenants',
  '/verifier',
  '/visa',
]
const BACKEND = process.env.VITE_DEV_BACKEND ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(
      API_PREFIXES.map((p) => [
        p,
        {
          target: BACKEND,
          changeOrigin: true,
          // Several of these prefixes double as client-side routes
          // (/branches, /staff, /tenants, /visa, /analytics...). Without this,
          // deep-linking or reloading one of those pages in dev serves the
          // backend's JSON instead of the app. A browser navigation asks for
          // text/html while apiFetch asks for JSON, so hand navigations back to
          // Vite and proxy only the actual API calls.
          bypass: (req) =>
            req.headers.accept?.includes('text/html') ? '/index.html' : undefined,
        },
      ]),
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
