# ADR-0033: The Dev gate type-checks the frontend

**Status**: Accepted — implemented
**Date**: 2026-08-23

## Context

Frontend tickets were the harness's dominant failure class: several churned to
`MAX_ITERATIONS` and were abandoned (#112, #133), while backend tickets flowed
clean. Investigating the maxed-out tickets, the failures were almost never the
*feature* — they were strict-TypeScript build errors:

- `TS6133` unused-variable errors from dead code left by an abandoned refactor
  (`noUnusedLocals` is on), and
- a test file that referenced `render` / `screen` / a component it never
  imported (a copy-paste into the wrong file).

The Dev self-check gate (`dev_agent._dev_gate`) ran only `check.sh backend-lint`
plus the changed *backend* tests, and the Dev prompt explicitly deferred
`npm run build` to the merge gate. The authoritative post-agent workflow gate
(`agent-harness.yml`) likewise ran only `check.sh backend`. `npm run lint`
(oxlint) does **not** type-check. So a frontend `tsc` error was invisible to the
whole Dev loop and only surfaced at the Review agent (or CI), after which the
harness burned a fresh iteration rediscovering it — up to the cap.

## Decision

Type-check the frontend inside the Dev loop, but only when the ticket touched
frontend source (`frontend/**` `.ts/.tsx/.js/.jsx`):

1. **In-run gate** (`_dev_gate` → `_frontend_gate`): after the backend checks,
   if the ticket changed frontend source, install `node_modules` if missing
   (`npm ci`/`npm install`) and run `check.sh frontend` (oxlint + `tsc -b` +
   vite build). Failures feed back into the same run via the existing
   `DEV_BUILD_ATTEMPTS` loop, so the agent fixes them before finishing.
2. **Authoritative workflow gate** (`agent-harness.yml` "Build gate"): after the
   backend check, when the branch diff touches frontend source, run
   `check.sh frontend` too — a failure becomes `needs-rework` instead of being
   passed to Test/Review and a red CI-frontend job.
3. **Prompt**: the Dev prompt now tells the agent to make `npm run build`
   (`tsc -b` + vite build) green, not just `npm run lint`.

Both gates **skip silently** when there is no frontend, no frontend change, or
`node_modules` can't be installed on the runner — CI still gates those cases, so
this never false-fails a ticket on infrastructure.

## Consequences

- Frontend tickets get the same in-run "fix what the gate reports" loop backend
  tickets already had; a `tsc` error no longer costs an entire iteration.
- Frontend Dev runs pay a one-time `npm ci` (~tens of seconds) and a `tsc` +
  vite build; a worthwhile trade against burning up to five iterations.
- oxlint remaining separate is fine — the build (`tsc`) is the piece that was
  missing. See also the sibling-collision failure mode (docs/adr/0025), the
  other reason frontend tickets stalled.
