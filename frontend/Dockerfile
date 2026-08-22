# syntax=docker/dockerfile:1.7
#
# Frontend production image for the EduConsult CRM SPA (React + Vite + TS).
#
# Produces a small runtime image: a single nginx process serves the built
# static bundle AND reverse-proxies the same API prefixes the dev Vite
# server proxies (see frontend/vite.config.ts), so the SPA can keep using
# same-origin relative paths (``VITE_API_BASE_URL`` unset / empty).
#
# Build:
#   docker build -t educonsult-frontend:latest frontend/
#
# Run (standalone):
#   docker run --rm -p 8080:80 \
#     -e BACKEND_UPSTREAM=127.0.0.1:8000 \
#     educonsult-frontend:latest
#
# In docker-compose.prod.yml the backend service is referenced as
# ``backend``; the default BACKEND_UPSTREAM points at that hostname.
# Note: BACKEND_UPSTREAM is a bare ``host:port`` (no scheme).

# ---------- Stage 1: build ----------
# Pinned to the active LTS line so local builds and CI builds are
# reproducible (Vite 8 requires Node >= 20.19 / 22.5).
FROM node:22-alpine AS build
WORKDIR /app

# Install dependencies first so this layer caches independently of
# application source changes.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Now copy the rest of the source and build the production bundle.
COPY . .
RUN npm run build

# ---------- Stage 2: runtime ----------
# nginx:alpine is ~40 MB, has the rewrite module we need for SPA
# history-mode fallback, and is the de-facto choice for serving a
# static SPA in production.
FROM nginx:1.27-alpine AS runtime

# Drop the default welcome page; we'll ship our own config + bundle.
RUN rm -f /etc/nginx/conf.d/default.conf

# SPA-aware nginx config:
#   * serves the built bundle from /usr/share/nginx/html
#   * reverse-proxies the API prefixes the dev server proxies (kept in
#     sync with vite.config.ts) to the backend service
#   * falls back to /index.html for any non-asset route so React Router
#     (history mode) keeps working on deep links / page reload
#   * adds sensible caching for hashed asset bundles and ``no-cache``
#     for index.html so deploys are picked up immediately
#
# Shipped as a *.template so the nginx:alpine entrypoint's
# 20-envsubst-on-templates.sh replaces ``${BACKEND_UPSTREAM}`` with the
# value of the matching container env var at startup, without baking
# the hostname into the image.
COPY nginx.conf.template /etc/nginx/templates/app.conf.template

# Static bundle from the build stage.
COPY --from=build /app/dist /usr/share/nginx/html

# Where the backend lives. Override at run/deploy time, e.g.
# ``-e BACKEND_UPSTREAM=backend:8000`` in docker-compose.prod.yml. The
# default keeps the image runnable standalone for local smoke tests.
# Must be a bare ``host:port`` (no scheme) — see nginx.conf.template.
ENV BACKEND_UPSTREAM=backend:8000

# nginx:alpine already EXPOSES 80; make it explicit for compose / k8s.
EXPOSE 80

# Healthcheck hits the SPA shell — the React app's index.html always
# returns 200 from nginx, even if the backend is down. That is enough
# for the container to be considered "serving" in the production stack;
# real API liveness is verified by the backend's own health check.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1

# nginx:alpine's default CMD already runs nginx in the foreground.