# syntax=docker/dockerfile:1.7
#
# Production image for the EduConsult CRM backend (FastAPI + uvicorn).
# Used by infra/docker-compose.prod.yml (ticket #76) for on-prem deployment.

# ---------------------------------------------------------------------------
# Stage 1 — builder: install Python deps into an isolated prefix we can copy
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Build deps for any wheels that need compiling (e.g. bcrypt). Stripped later.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install into a relocatable prefix so we can COPY it into the runtime stage
# without dragging the system site-packages / pip cache along.
COPY requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---------------------------------------------------------------------------
# Stage 2 — runtime: minimal image, non-root, single uvicorn worker process
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Runtime libs uvicorn[standard] / psycopg / bcrypt link against. Kept minimal;
# curl is added so the HEALTHCHECK can hit the in-process /health endpoint.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Dedicated non-root user for the app process.
RUN groupadd --system app \
    && useradd --system --gid app --create-home --home-dir /home/app app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy the prebuilt Python site-packages from the builder stage.
COPY --from=builder /install /usr/local

# Application code (and Alembic migration tree) is added last so source edits
# don't bust the dependency-install layer.
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./alembic.ini

USER app

EXPOSE 8000

# Liveness check against the FastAPI /health endpoint shipped in app/main.py.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail --silent http://localhost:8000/health || exit 1

# Single uvicorn worker per container; scale horizontally by adding replicas.
# HOST=0.0.0.0 is required so the container accepts traffic on the Docker
# network. PORT is overridable for compose/k8s; default matches EXPOSE above.
ENV HOST=0.0.0.0 \
    PORT=8000

CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST} --port ${PORT}"]
