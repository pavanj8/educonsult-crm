# EduConsult CRM — Deployment Guide

This guide explains the two supported ways to run the EduConsult CRM:
**SaaS** (the hosted, multi-tenant service operated by EduConsult) and
**On-Premises** (a single-tenant install operated by the customer on
their own infrastructure). Both modes run the **same codebase and the
same container images** — the difference is purely in configuration and
who runs them. This is by design: see
[ADR-0003 — Deployment model: SaaS-first, on-prem via Docker Compose](../docs/adr/0003-deployment-model.md).

The artefacts in this directory (`infra/`) are the deployment surface
shared by both modes:

| File | Purpose |
|---|---|
| [`docker-compose.yml`](docker-compose.yml) | Local development stack (Postgres, MinIO, MailHog). Not for production. |
| [`docker-compose.prod.yml`](docker-compose.prod.yml) | Production-shaped stack used for **on-prem single-tenant** installs; also the shape SaaS runs per-environment. |
| [`.env.example`](.env.example) | Example variables for local development. |
| [`ENVIRONMENT.md`](ENVIRONMENT.md) | Full reference for every runtime-configurable variable across all three deployment contexts (local dev, SaaS, on-prem). |

If you only need a list of environment variables, read `ENVIRONMENT.md`
directly. This README is the **decision + procedure** document that
points at it.

---

## 1. Choosing a deployment mode

| | SaaS (hosted) | On-Premises |
|---|---|---|
| **Who operates it** | EduConsult | The customer's IT / consultancy |
| **Tenancy** | Multi-tenant (many consultancies share one install, isolated by `tenant_id` everywhere — see [ADR-0001](../docs/adr/0001-multi-tenant-shared-database.md)) | Single-tenant (one consultancy, one install) |
| **Database** | Managed PostgreSQL (e.g. AWS RDS, Cloud SQL) — separate production + replica per environment | PostgreSQL container (`postgres:16-alpine`) from this compose stack, or a customer-managed Postgres pointed at by `DATABASE_URL` |
| **Object storage** | AWS S3 bucket per environment | MinIO container from this compose stack, or any S3-compatible endpoint pointed at by `DOCUMENT_STORAGE_ENDPOINT_URL` |
| **Email** | Real SMTP provider (SES, SendGrid, etc.) — configured via `SMTP_*` env | Local SMTP relay, or the customer's own SMTP relay, configured via `SMTP_*` env |
| **Public endpoint** | HTTPS in front of the frontend container, with the backend reachable only via the internal docker network | Typically a reverse proxy (nginx, Traefik, Cloudflare Tunnel, …) on the customer's network terminating TLS in front of the frontend container |
| **Backups** | Managed (DB snapshots + S3 versioning + off-site replication) | Customer's responsibility — see [§6 Operations](#6-operations) below |
| **Upgrades** | EduConsult applies new image tags to the running stack | Customer pulls new image tags and re-runs `docker compose up -d` |
| **Scaling** | Horizontal at the SaaS layer (not covered by this stack) | Vertical only with this compose stack — see [§7 Limitations](#7-limitations) |

**Rule of thumb:** choose **SaaS** if you want EduConsult to run the
platform and bill you per tenant. Choose **on-prem** if you have a
data-residency, regulatory, or IT-policy reason to keep every byte of
student data inside your own network. There is **no separate "on-prem
edition"** of the code — both modes consume the same images.

---

## 2. Prerequisites (both modes)

- **Docker Engine 24+** with the Compose plugin (`docker compose`
  subcommand). The production stack targets the Compose v2 schema used
  by `docker-compose.prod.yml`.
- **Git**, to fetch this repository and pull new image tags on upgrade.
- A Linux host (physical server, VM, or cloud instance) with at least:
  - 4 vCPU, 8 GB RAM, 40 GB free disk for an on-prem single-tenant
    install (Postgres + MinIO + backend + frontend + headroom for
    uploads).
  - Outbound HTTPS to whatever image registry you pull from, plus
    inbound HTTPS on the port(s) you choose to expose.
- For **on-prem** specifically: a strategy for off-host backups of the
  `postgres_data` and `minio_data` named volumes (see [§6](#6-operations)).

---

## 3. On-Prem deployment (step-by-step)

This is the procedure for a customer's IT team to install a
single-tenant EduConsult CRM on infrastructure they control.

### 3.1 Clone the repo

```bash
git clone https://github.com/pavanj8/educonsult-crm.git
cd educonsult-crm
```

You only need the `infra/` directory, `backend/Dockerfile`, and
`frontend/Dockerfile` at deploy time — pull new image tags from your
registry of choice rather than re-building on the host. The steps
below assume you have **already published** the backend and frontend
images to a registry the host can reach, and that you have the
Postgres / MinIO / mail images available locally or via the standard
Docker Hub mirrors used by `docker-compose.prod.yml`.

### 3.2 Create the on-prem environment file

Copy the example and edit it for your install. **Do not commit this
file** — it contains secrets:

```bash
cp infra/.env.example infra/.env.prod
$EDITOR infra/.env.prod
```

Set at minimum:

| Variable | Why it matters |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Database credentials. Use a long random password. |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | Object-storage admin credentials. The same values double as the `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` the backend uses against MinIO. |
| `MINIO_BUCKET` | Bucket the backend reads/writes student documents under (default `educonsult-documents`). |
| `BACKEND_IMAGE` / `FRONTEND_IMAGE` | Image:tag references the host will pull (e.g. `registry.example.com/educonsult-backend:1.4.2`). |
| `BACKEND_ENV_FILE` | Path (relative to `infra/`) to the file that holds the **backend's own** env vars (`JWT_SECRET`, `SMTP_*`, etc.). See [ENVIRONMENT.md](ENVIRONMENT.md) for the full list. |
| `FRONTEND_PORT` | Host port that maps to the frontend container's port 80 (default `8080`). |
| `MINIO_REGION` | Any non-empty value; only used for S3 SDK compatibility. |

For the complete reference — including the backend's `JWT_SECRET`,
`SMTP_*`, optional `DOCUMENT_STORAGE=memory` switch for throwaway
environments, and the frontend's `BACKEND_UPSTREAM` — read
[`ENVIRONMENT.md`](ENVIRONMENT.md).

### 3.3 Start the stack

From the repository root:

```bash
docker compose \
  --env-file infra/.env.prod \
  -f infra/docker-compose.prod.yml \
  up -d
```

This brings up, in order:

1. `postgres` (waits for `pg_isready` to pass)
2. `minio` (waits for its own health endpoint)
3. `minio-init` (one-shot: creates the document bucket)
4. `migrate` (one-shot: runs `alembic upgrade head`)
5. `backend` (waits for both `minio-init` and `migrate` to succeed, then
   starts uvicorn)
6. `frontend` (nginx serving the built SPA, reverse-proxying `/api/…`
   and `/auth/…` to the backend)

Verify with:

```bash
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml ps
curl -fsS http://localhost:8080/                 # frontend shell
curl -fsS http://localhost:8080/health           # proxied to backend's /health
```

### 3.4 Front the stack with TLS

`docker-compose.prod.yml` publishes the frontend on
`${FRONTEND_PORT:-8080}` only — it does not terminate TLS. In
production you must put a TLS-terminating reverse proxy in front.
Two equally supported shapes:

- **Same host, reverse proxy in front** — run nginx / Traefik /
  Caddy on the host, listen on 443, proxy to
  `http://127.0.0.1:8080`. Pin a real certificate (Let's Encrypt,
  internal CA, …).
- **Sidecar proxy container** — add an nginx-proxy or Caddy service
  to an extended compose file that depends on `frontend`, and publish
  only the proxy on 443.

The frontend nginx config already handles SPA history-mode fallback
and the API prefixes, so a proxy that just forwards `/` to it is
sufficient.

### 3.5 Create the first Super Admin

The product does not self-signup: tenancy is created by a Super
Admin (Requirements §1). For a single-tenant on-prem install, the
simplest path is to bootstrap the Super Admin row directly against
the on-prem Postgres using the backend's existing tooling — follow
the same flow your customer-success team uses for SaaS tenant
provisioning, just pointed at this stack's `DATABASE_URL`.

---

## 4. SaaS deployment (operator-facing summary)

This section is for the EduConsult SRE / platform team running the
hosted service. The procedure is identical to [§3](#3-on-prem-deployment-step-by-step)
with three structural differences:

1. **Database is managed, not containerised.** Run the backend image
   against a managed Postgres (RDS, Cloud SQL, …) by setting
   `DATABASE_URL` in the backend env file to the managed endpoint,
   and either delete the `postgres` service from
   `docker-compose.prod.yml` for that environment or leave it
   dormant. `migrate` must still run, because Alembic is the only
   supported schema-migration path.
2. **Object storage is AWS S3, not MinIO.** Drop the `minio` and
   `minio-init` services, set:
   - `DOCUMENT_STORAGE_ENDPOINT_URL=` *(empty — defaults to real AWS)*
   - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` to an IAM role or
     user scoped to the per-environment bucket
   - `DOCUMENT_STORAGE_BUCKET=<env>-educonsult-documents`
   - `DOCUMENT_STORAGE_REGION=<aws-region>`
3. **One logical install hosts many tenants.** Every row carries a
   `tenant_id` ([ADR-0001](../docs/adr/0001-multi-tenant-shared-database.md));
   tenancy is created through the Super Admin API, never by
   self-signup. Plan your Postgres connection pool sizing and S3
   request rate accordingly.

Everything else — the `migrate` job, the backend image, the
frontend image, the `BACKEND_UPSTREAM` wiring — is identical between
the two modes.

---

## 5. Local development (not a deployment mode)

For day-to-day engineering work, use `infra/docker-compose.yml` (not
the prod one): it stands up Postgres, MinIO, and MailHog with
dev-friendly defaults and port-forwarding for direct access from the
host. See the top-level [README](../README.md#running-it-locally) for
the full `uvicorn` + `npm run dev` workflow against this stack.

---

## 6. Operations

These commands assume the on-prem layout from [§3](#3-on-prem-deployment-step-by-step);
the same patterns apply SaaS-side against whatever orchestrator
wraps the prod compose file.

| Task | Command |
|---|---|
| Tail logs from everything | `docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml logs -f` |
| Tail logs from one service | `… logs -f backend` |
| Restart the backend after a config change | `… up -d backend` |
| Apply a new image tag | edit `BACKEND_IMAGE` / `FRONTEND_IMAGE` in `infra/.env.prod`, then `… pull && … up -d` |
| Run Alembic migrations manually | `… run --rm migrate alembic upgrade head` |
| Open a psql shell against the DB | `… exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"` |
| Open a `mc` shell against MinIO | `… run --rm --entrypoint /bin/sh minio/mc:latest` (then `mc alias set local http://minio:9000 …`) |
| Stop the stack | `… stop` *(keeps volumes)* |
| Wipe the stack **and its data** | `… down -v` *(destructive — see below)* |

### Backups (on-prem)

The named volumes `postgres_data` and `minio_data` defined in
`docker-compose.prod.yml` are the source of truth. A minimal backup
strategy that meets the product's soft-delete + export promise
(Requirements §8):

1. **Postgres**: nightly `pg_dump` of `$POSTGRES_DB`, written to a
   separate volume or off-host location (e.g.
   `docker exec postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"
   | gzip > /backups/db-$(date +%F).sql.gz`). Retain per your data
   retention policy.
2. **MinIO**: replicate the document bucket to a second bucket or
   external object store (e.g. `mc mirror` to a cold-storage
   bucket, or a `mc admin bucket replication` rule). Student
   documents are the user-visible data; losing them is not
   recoverable from the database.
3. **Configuration**: keep `infra/.env.prod` and the backend env
   file under your usual secrets manager. Without them, a fresh
   `docker compose up` will not be able to talk to the existing
   volumes.

### Upgrades

Upgrades are image-tag changes. For a routine patch release:

```bash
# 1. Stop the backend + frontend (leave postgres + minio running)
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml \
  stop backend frontend

# 2. Bump BACKEND_IMAGE / FRONTEND_IMAGE in infra/.env.prod, then…
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml \
  pull
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml \
  run --rm migrate        # safe to re-run; Alembic is idempotent
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml \
  up -d
```

Schema changes ship as new Alembic revisions in the backend image;
`migrate` is the only thing that ever touches the schema.

---

## 7. Limitations

- **Single host per on-prem install.** `docker-compose.prod.yml`
  is a single-node stack. It does not provide Postgres replication,
  MinIO distributed mode, or backend horizontal scaling out of the
  box. For multi-node on-prem, point `DATABASE_URL` at a
  customer-managed Postgres cluster and `DOCUMENT_STORAGE_ENDPOINT_URL`
  at a customer-managed S3-compatible cluster, and run the backend
  + frontend containers on however many hosts you need behind your
  own load balancer. The compose file remains the supported
  reference for the single-node shape.
- **No in-place SaaS → on-prem data migration tool.** Both modes
  share the schema, so a `pg_dump` + bucket copy + reconfigure is
  technically feasible, but there is no first-party migration
  utility yet. For a real cutover, engage EduConsult support.
- **No automatic TLS.** `docker-compose.prod.yml` does not include a
  TLS-terminating proxy. Bring your own (see [§3.4](#34-front-the-stack-with-tls)).
- **No automated backups in the on-prem stack.** Backups are the
  operator's responsibility (see [§6](#6-operations)).
- **Compose v2 only.** The prod compose file uses features
  (`include`-style `env_file.required`, healthcheck `condition:
  service_completed_successfully`) that require Docker Compose v2
  (`docker compose`, not the legacy `docker-compose` Python tool).

---

## 8. See also

- [`ENVIRONMENT.md`](ENVIRONMENT.md) — every env var, every mode.
- [`docker-compose.prod.yml`](docker-compose.prod.yml) — the prod stack.
- [`../docs/adr/0003-deployment-model.md`](../docs/adr/0003-deployment-model.md) — the
  decision to build one codebase for both modes.
- [`../docs/adr/0001-multi-tenant-shared-database.md`](../docs/adr/0001-multi-tenant-shared-database.md) —
  the multi-tenant schema that makes SaaS and on-prem share one DBMS.
- [`../docs/requirements.md`](../docs/requirements.md) §1 *Product & Deployment* —
  the product-level statement that both modes must ship from one codebase.
