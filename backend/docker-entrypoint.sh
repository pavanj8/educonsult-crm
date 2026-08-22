#!/bin/sh
# Container entrypoint for the EduConsult CRM backend.
#
# Why this exists (vs `CMD ["sh", "-c", "uvicorn ..."]`):
#   Using `exec` here makes uvicorn PID 1, so the kernel delivers SIGTERM /
#   SIGINT directly to the Python process and FastAPI gets a chance to run
#   its graceful-shutdown path. With a `sh -c` wrapper, PID 1 is /bin/sh and
#   signal forwarding is less reliable (Senior Developer review note, #74).
#
# Defaults match EXPOSE 8000 in the Dockerfile and the uvicorn bind
# documented in `docs/...`. Override at runtime via the HOST / PORT env
# vars (e.g. `docker run -e PORT=9000 ...` or the compose env file in
# #76); the explicit `--host 0.0.0.0` here is the safe default for the
# Docker bridge network.

set -eu

: "${HOST:=0.0.0.0}"
: "${PORT:=8000}"

exec uvicorn app.main:app --host "${HOST}" --port "${PORT}"
