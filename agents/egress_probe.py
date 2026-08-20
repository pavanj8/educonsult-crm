#!/usr/bin/env python3
"""One-off egress diagnostic (docs/adr/0019 follow-up).

Determines whether this runner can actually reach MiniMax, or whether all LLM
egress is pinned to the Cursor gateway. Two runs (before/after a key change)
both returned Cursor's model catalog and "Use Cursor.models.list()" even with
`base_url=https://api.minimax.io/v1`, which means either (a) the network path
redirects/blocks api.minimax.io, or (b) the `openai` client ignores base_url.
This script separates the two:

  * a RAW urllib HTTPS POST straight to MiniMax (bypasses the openai client) --
    if this reaches MiniMax, egress is fine and the client is the problem;
  * the openai client call -- to compare.

Prints proxy env, DNS, the effective final URL after any redirect, and the raw
response body. No secrets are printed (the key is masked). Safe to delete once
the routing question is answered.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request

BASE = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1").rstrip("/")
KEY = os.environ.get("MINIMAX_API_KEY", "")


def hr(title: str) -> None:
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


hr("proxy / env")
for k in (
    "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
    "NO_PROXY", "no_proxy", "OPENAI_BASE_URL", "OPENAI_API_KEY",
):
    v = os.environ.get(k, "")
    if k.endswith("API_KEY") and v:
        v = f"{v[:6]}…({len(v)} chars)"
    print(f"{k}={v}")
print(f"MINIMAX_BASE_URL={BASE}")
print(f"MINIMAX_API_KEY set={'yes' if KEY else 'NO'} ({len(KEY)} chars)")

hr("DNS: api.minimax.io")
try:
    print(socket.gethostbyname_ex("api.minimax.io"))
except Exception as e:  # noqa: BLE001
    print("DNS error:", type(e).__name__, e)

hr(f"RAW urllib POST -> {BASE}/chat/completions (model=MiniMax-M3)")
req = urllib.request.Request(
    f"{BASE}/chat/completions",
    data=json.dumps({
        "model": "MiniMax-M3",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 8,
    }).encode(),
    headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
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

hr("openai client (compare) -> chat.completions.create(model=MiniMax-M3)")
try:
    from openai import OpenAI

    client = OpenAI(api_key=KEY, base_url=BASE)
    print("client base_url:", getattr(client, "base_url", "?"))
    resp = client.chat.completions.create(
        model="MiniMax-M3",
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=8,
    )
    print("OK:", resp.choices[0].message.content)
except Exception as e:  # noqa: BLE001
    print("error:", type(e).__name__, str(e)[:800])
