# ADR-0027: Dev self-verifies and fixes in-run before needs-rework

**Status**: Accepted — implemented
**Date**: 2026-08-21

## Context

When a Dev run produced code that failed the build gate (`check.sh`), the ticket
bounced out to `needs-rework` and the picker re-dispatched a **fresh Dev job** —
paying full overhead (runner provision, checkout, install, sync, re-read context,
queue hop) just to fix what was often a small, deterministic gate failure the
agent could have addressed in place. The agent already iterates inside its tool
loop, but it sometimes exits believing it is done while `check.sh` still fails.

## Decision

The Dev run now **self-verifies and fixes in-run**: after the agent finishes,
`dev_agent.py` runs `scripts/check.sh backend`; if it fails, it feeds the exact
failure back into a fresh agent attempt ("fix ONLY this, don't restart") and
re-checks — up to `DEV_BUILD_ATTEMPTS` (default 2) total attempts — before
returning. Only if it still fails does the ticket go to `needs-rework` (via the
workflow build gate) and get re-dispatched.

Scope: this applies to the **backend build gate only** (cheap, deterministic,
in-process). **Test and Review are unchanged** — they are independent agents in
separate jobs *by design* (the Test agent must stay isolated from Dev), so they
cannot and should not run inside the Dev run.

## Consequences

- Build-gate failures are fixed in the same run, avoiding a full re-dispatch — the
  common "one more small fix" case no longer costs a fresh runner + queue hop.
- Bounded: each attempt is still capped at `DEV_MAX_TURNS`; two attempts max, so a
  genuinely stuck ticket still fails-closed to `needs-rework` promptly (it does not
  reintroduce the 49-min churn ADR-0026 removed).
- The workflow build gate remains as an independent re-verification in the clean
  job env (defence in depth); it now almost always passes on the first try.
- Slightly more work per Dev run (an extra `check.sh` when the agent's first pass
  already passed), which is far cheaper than a re-dispatched iteration.
