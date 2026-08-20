#!/usr/bin/env python3
"""One-off egress/auth diagnostic (docs/adr/0019 follow-up).

Fast pre-check for MiniMax's **Anthropic-compatible** endpoint before a full
agent run: verifies the runner reaches api.minimax.io, that ANTHROPIC_AUTH_TOKEN
authenticates, and that the Token Plan has balance (a 429 rate_limit_error 2056
means out of credits). Does a raw urllib POST straight to the endpoint (bypasses
the client) and then the same call via the `anthropic` client. No secrets are
printed. Safe to delete once everything runs.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request

BASE = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic").rstrip("/")
TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN", "") or os.environ.get("MINIMAX_API_KEY", "")
MODEL = os.environ.get("PROBE_MODEL", "MiniMax-M3")


def hr(title: str) -> None:
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


hr("proxy / env")
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy"):
    print(f"{k}={os.environ.get(k, '')}")
print(f"ANTHROPIC_BASE_URL={BASE}")
print(f"ANTHROPIC_AUTH_TOKEN set={'yes' if TOKEN else 'NO'} ({len(TOKEN)} chars)")

hr("DNS: api.minimax.io")
try:
    print(socket.gethostbyname_ex("api.minimax.io"))
except Exception as e:  # noqa: BLE001
    print("DNS error:", type(e).__name__, e)

hr(f"RAW urllib POST -> {BASE}/v1/messages (model={MODEL})")
req = urllib.request.Request(
    f"{BASE}/v1/messages",
    data=json.dumps({
        "model": MODEL,
        "max_tokens": 16,
        "messages": [{"role": "user", "content": "ping"}],
    }).encode(),
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    },
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print("HTTP", r.status, "final-url:", r.geturl())
        print(r.read(1000).decode(errors="replace"))
except urllib.error.HTTPError as e:
    print("HTTPError", e.code, "final-url:", e.geturl())
    print(e.read(1000).decode(errors="replace"))
except Exception as e:  # noqa: BLE001
    print("error:", type(e).__name__, e)

hr(f"anthropic client (compare) -> messages.create(model={MODEL})")
try:
    from anthropic import Anthropic

    client = Anthropic(base_url=BASE, auth_token=TOKEN)
    print("client base_url:", getattr(client, "base_url", "?"))
    resp = client.messages.create(
        model=MODEL,
        max_tokens=16,
        messages=[{"role": "user", "content": "ping"}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    print("OK stop_reason:", resp.stop_reason, "text:", text)
except Exception as e:  # noqa: BLE001
    print("error:", type(e).__name__, str(e)[:800])
