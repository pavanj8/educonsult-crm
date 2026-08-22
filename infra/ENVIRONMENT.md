# Environment Variable Reference

> **Issue:** [#77](https://github.com/pavanj8/educonsult-crm/issues/77) — `[E4] Environment variable reference documentation`
> **Epic:** [E4 — Deployment & On-Prem Packaging](../docs/epics.md#e4-deployment--on-prem-packaging) (Phase 2)
> **Traces to:** Requirements §1 (Product & Deployment), §2 (Tech Stack)

This document is the single source of truth for every environment variable the
EduConsult CRM application reads at runtime, in every deployment mode (local
development, SaaS production, on-prem Docker Compose). It complements — but does
not replace — the inline `# Environment variables` docstring in
[`backend/app/storage/config.py`](../backend/app/storage/config.py) and the
comments on each `os.environ.get(...)` call in the backend config modules.

If a variable below does not exist in your shell, the application falls back
to the development defaults shipped in the source. **Production deployments
must override at least the secrets and any deployment-specific URLs** (see
"Required for production" on each variable).

## How variables are read

| Layer | Mechanism | Resolved at |
|---|---|---|
| Backend (Python) | `os.environ.get(...)` with a hard-coded default in each `app/*/config.py` module | Process startup (no caching across boots) |
| Frontend (Vite build) | `import.meta.env.VITE_*` — **baked into the bundle at build time** | Vite `build` step (not at runtime) |
| Frontend (nginx runtime) | `${BACKEND_UPSTREAM}` envsubst in `nginx.conf.template` | Container startup, via `nginx:alpine`'s `20-envsubst-on-templates.sh` |
| Backend Dockerfile | `HOST`, `PORT` consumed by [`backend/docker-entrypoint.sh`](../backend/docker-entrypoint.sh) | Container startup |
| Docker Compose (infra) | `${VAR:-default}` interpolation in [`infra/docker-compose.yml`](./docker-compose.yml) and `infra/docker-compose.prod.yml` | `docker compose up` |

## Backend — application configuration

These variables are read by the FastAPI process. All have safe defaults for
local development; the production deployments below list which ones **must**
be overridden.

### Database (`backend/app/db/database.py`)

| Variable | Default | Required for production | Purpose |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/educonsult` | **Yes (SaaS + on-prem)** | Full SQLAlchemy connection URL. Use this in real deployments; it is the canonical knob. |
| `DATABASE_OVERRIDE` | _unset_ | **No** | Escape hatch used by the test agent's harness to point the app at a scratch SQLite DB (e.g. `DATABASE_OVERRIDE=sqlite:///./test.db`). If set, it takes precedence over `DATABASE_URL`. **Never set this in production.** |

> The Postgres credentials baked into the default `DATABASE_URL` are
> `postgres:postgres` — match the default credentials in
> [`infra/.env.example`](./.env.example) for local dev. Override `DATABASE_URL`
> in any environment that talks to a real database.

### JWT auth (`backend/app/auth/config.py`)

| Variable | Default | Required for production | Purpose |
|---|---|---|---|
| `JWT_SECRET_KEY` | `dev-only-change-me` | **Yes — MUST override** | HMAC signing key for access + refresh tokens ([ADR-0004](../docs/adr/0004-rbac-role-model.md), Requirements §8). Use a long, random value. Rotating it invalidates every outstanding token. |
| `JWT_ALGORITHM` | `HS256` | Optional | Token signing algorithm. `HS256` is fine for a single-process deployment; switch to `RS256` only if you front the backend with multiple issuers. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Optional | Access-token lifetime in minutes ([ADR-0005]). |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Optional | Refresh-token lifetime in days. |

### Email / SMTP (`backend/app/email/config.py`)

| Variable | Default | Required for production | Purpose |
|---|---|---|---|
| `SMTP_HOST` | `localhost` | **Yes (SaaS + on-prem)** | Hostname of the SMTP server that delivers transactional email (Requirements §2). For local dev, point at the MailHog service in [`infra/docker-compose.yml`](./docker-compose.yml). |
| `SMTP_PORT` | `1025` | **Yes** | SMTP port (MailHog = `1025`, most real relays = `25` / `465` / `587`). |
| `SMTP_FROM` | `noreply@educonsult.test` | **Yes** | `From:` address on outbound email. Use a real address your relay accepts. |
| `APP_BASE_URL` | `http://localhost:5173` | **Yes** | Public origin of the frontend. Used to build absolute URLs inside email bodies (e.g. password-reset links, owner-invite links — see Requirements §6). Trailing slashes are stripped automatically. |

### Document storage — S3-compatible (`backend/app/storage/config.py`, `backend/app/storage/service.py`)

| Variable | Default | Required for production | Purpose |
|---|---|---|---|
| `DOCUMENT_STORAGE_BUCKET` | `educonsult-documents` | **Yes** | Bucket name uploads go into. |
| `DOCUMENT_STORAGE_ENDPOINT_URL` | _unset_ (→ real AWS S3) | **Yes for on-prem MinIO** | S3-compatible endpoint URL. Set to `http://minio:9000` (no trailing slash) for MinIO. Leave unset for AWS S3. |
| `DOCUMENT_STORAGE_REGION` | `us-east-1` | Optional | AWS region. Safe to leave at the default for MinIO. |
| `DOCUMENT_STORAGE_KEY_PREFIX` | `tenants` | Optional | Prefix prepended to every object key (used to namespace uploads per deployment). |
| `DOCUMENT_STORAGE` | _unset_ | **No** | If set to `memory` / `in-memory` / `inmemory`, the storage service becomes the in-memory test backend (no network). Used by the test agent's harness. **Never set this in production.** |

Credentials (access key id, secret access key) are **not** read from
`DOCUMENT_STORAGE_*`. They are sourced from the standard boto3 chain —
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and on AWS also the instance
role / IRSA. On the on-prem Docker Compose side, set these explicitly to the
`MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from `.env.example` (or your own
values) when the backend container starts.

### Storage selection (`backend/app/storage/service.py`)

The `DOCUMENT_STORAGE=memory` switch is listed above for completeness because
it is consumed in the same module that wires up storage. There is no other
storage-related variable.

### Schema lifecycle hook (`backend/app/main.py`)

The `DATABASE_OVERRIDE` variable (already listed under "Database") is also
consulted at startup to decide whether the running process should own its own
schema lifecycle (`Base.metadata.create_all` + stage-transition seeding) or
hand that off to Alembic. This is an internal implementation detail; **do not
configure `DATABASE_OVERRIDE` in production** or Alembic will be bypassed.

## Backend — container runtime

These variables are consumed by the **backend container image** (built from
[`backend/Dockerfile`](../backend/Dockerfile), issue #74) via its entrypoint
script [`backend/docker-entrypoint.sh`](../backend/docker-entrypoint.sh).

| Variable | Default | Required for production | Purpose |
|---|---|---|---|
| `HOST` | `0.0.0.0` | Optional | Interface uvicorn binds. `0.0.0.0` is required for the Docker bridge network; you would only override this on bare-metal / k8s deployments. |
| `PORT` | `8000` | Optional | Port uvicorn binds. Must match `EXPOSE 8000` in the Dockerfile unless you also rebuild the image. |

## Frontend — build-time

The frontend SPA reads these variables at **`npm run build`** time via
Vite's `import.meta.env`. They are baked into the static bundle; changing
them after the bundle is built requires a rebuild.

| Variable | Default | Required for production | Purpose |
|---|---|---|---|
| `VITE_API_BASE_URL` | _empty string_ | Recommended | Base URL for backend API calls in [`frontend/src/api/client.ts`](../frontend/src/api/client.ts). Empty string = same-origin (the SPA calls `/auth/login`, `/applications`, etc. on the host it was served from, which the nginx container proxies to the backend — see `BACKEND_UPSTREAM` below). Set to e.g. `https://api.educonsult.example` only if the SPA is hosted on a different origin than the API. |

## Frontend — nginx runtime

The frontend container (built from [`frontend/Dockerfile`](../frontend/Dockerfile),
issue #75) serves the built SPA through `nginx:alpine`. At container startup,
`nginx:alpine`'s built-in `20-envsubst-on-templates.sh` replaces
`${BACKEND_UPSTREAM}` in [`frontend/nginx.conf.template`](../frontend/nginx.conf.template)
with the matching container environment variable.

| Variable | Default | Required for production | Purpose |
|---|---|---|---|
| `BACKEND_UPSTREAM` | `backend:8000` | **Yes (docker-compose / k8s)** | `host:port` (no scheme) of the backend service that nginx reverse-proxies API requests to. The default matches the `backend` service name in `infra/docker-compose.prod.yml`; override to `127.0.0.1:8000` for a standalone container run, or to your k8s service name in a cluster deployment. |

## Docker Compose — local development (`infra/docker-compose.yml`)

These variables drive [`infra/docker-compose.yml`](./docker-compose.yml) (the
local development stack — Postgres, MinIO, MinIO-init, MailHog). They are
also documented in [`infra/.env.example`](./.env.example); you only need to
override them if the defaults conflict with something else running on your
machine.

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_USER` | `postgres` | Postgres username. Also baked into the backend's default `DATABASE_URL`. |
| `POSTGRES_PASSWORD` | `postgres` | Postgres password. Same caveat as above. |
| `POSTGRES_DB` | `educonsult` | Postgres database name. |
| `POSTGRES_PORT` | `5432` | Host port the Postgres service publishes on. |
| `MINIO_ROOT_USER` | `minioadmin` | MinIO admin user. Set as `AWS_ACCESS_KEY_ID` in the backend container so the document storage client can authenticate. |
| `MINIO_ROOT_PASSWORD` | `minioadmin` | MinIO admin password. Set as `AWS_SECRET_ACCESS_KEY` in the backend container. |
| `MINIO_BUCKET` | `educonsult-documents` | Bucket the `minio-init` one-shot creates on first boot. Must match `DOCUMENT_STORAGE_BUCKET` in the backend. |
| `MINIO_PORT` | `9000` | Host port the MinIO S3 API publishes on. |
| `MINIO_CONSOLE_PORT` | `9001` | Host port the MinIO web console publishes on. |
| `MAILHOG_SMTP_PORT` | `1025` | Host port the MailHog SMTP capture publishes on. Must match `SMTP_PORT` in the backend. |
| `MAILHOG_WEB_PORT` | `8025` | Host port the MailHog web UI publishes on. |

## Docker Compose — production (`infra/docker-compose.prod.yml`)

The production compose file (issue #76) reuses most of the same variables.
In addition, it surfaces a few **environment-only** values that the local
compose file does not need:

| Variable | Default (compose) | Required for production | Purpose |
|---|---|---|---|
| `DATABASE_URL` | _unset_ (backend falls back to its dev default) | **Yes** | Set this to the production Postgres connection string in the backend service's `environment:` block. |
| `JWT_SECRET_KEY` | _unset_ (backend uses the unsafe dev default) | **Yes** | Must be set to a strong random value, otherwise every installation shares the same signing key. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_FROM` | MailHog defaults | **Yes** | Point these at your real SMTP relay, not the MailHog service (which is dev-only). |
| `APP_BASE_URL` | `http://localhost:5173` | **Yes** | Public origin used inside outbound email. Set to the real frontend URL (e.g. `https://app.educonsult.example`). |
| `DOCUMENT_STORAGE_ENDPOINT_URL` | _unset_ | **Yes for MinIO, no for AWS S3** | Set to `http://minio:9000` if using the bundled MinIO service; leave unset if fronting AWS S3 instead. |
| `DOCUMENT_STORAGE_BUCKET` | `educonsult-documents` | Recommended | Match this to whatever bucket you provisioned (and to `MINIO_BUCKET` if you also use the local MinIO service). |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | _unset_ | **Yes** | Credentials the backend's boto3 client uses to talk to S3 / MinIO. On AWS, prefer instance roles / IRSA and leave these unset. |

> **Secrets handling.** Treat every variable marked **Yes — MUST override**
> as a secret. Do not commit a populated `.env` file to source control;
> prefer your platform's secret store (GitHub Actions secrets, AWS SSM /
> Secrets Manager, HashiCorp Vault, k8s Secrets, etc.) and inject the values
> at deploy time.

## Quick reference: minimum env file for on-prem

The smallest sane `.env` for an on-prem Docker Compose deployment looks like:

```dotenv
# infra/.env  (NOT committed)

# --- Database ---
POSTGRES_USER=educonsult
POSTGRES_PASSWORD=<strong-random>
POSTGRES_DB=educonsult
DATABASE_URL=postgresql+psycopg://educonsult:<strong-random>@db:5432/educonsult

# --- JWT ---
JWT_SECRET_KEY=<strong-random>

# --- SMTP ---
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_FROM=noreply@educonsult.example
APP_BASE_URL=https://crm.example.com

# --- Storage (MinIO in compose) ---
MINIO_ROOT_USER=<minio-user>
MINIO_ROOT_PASSWORD=<minio-password>
MINIO_BUCKET=educonsult-documents
DOCUMENT_STORAGE_BUCKET=educonsult-documents
DOCUMENT_STORAGE_ENDPOINT_URL=http://minio:9000
AWS_ACCESS_KEY_ID=<minio-user>
AWS_SECRET_ACCESS_KEY=<minio-password>

# --- Frontend ---
BACKEND_UPSTREAM=backend:8000
VITE_API_BASE_URL=
```

`<strong-random>` should be generated per environment, e.g. `openssl rand -hex 32`.

## Where to update this document

This file is owned by **E4** (Deployment & On-Prem Packaging). Any change
that adds a new `os.environ.get(...)` call to the backend, a new
`VITE_*` variable to the frontend, a new `nginx.conf.template` envsubst
variable, or a new `${VAR:-default}` interpolation to either
[`infra/docker-compose.yml`](./docker-compose.yml) or
`infra/docker-compose.prod.yml` **must** be reflected here in the same
change. The same applies to removing or renaming a variable.

This is the same traceability expectation as the test gate: an undocumented
runtime configuration is a bug.
