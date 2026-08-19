# ADR-0014: Local SDK runtime only executes a subset of listed models

**Status**: Accepted — implemented
**Date**: 2026-08-19

## Context

[ADR-0013](0013-asymmetric-model-tiering.md) tiered Test Agent and Review
Agent onto `claude-opus-5` after `Cursor.models.list()` showed that ID
(and other high-end IDs) as available to this account. The first
iteration to actually run those agents on GitHub Actions — issue #237
reopened after a manual merge was reverted — both finished in ~9 seconds
with `result.status == "error"`, empty assistant text, and empty
`result.result`. The workflow treated that as Test/Review fail, labeled
the issue `agent:needs-rework`, and did not auto-merge. That is the
correct conservative outcome, but it is not a product defect: the
verifiers never ran.

Reproduced on this machine against a tiny throwaway workspace (not the
CRM app): passing `model="claude-opus-5"` (and, separately, the model's
own default variant params) produced the same silent error in ~5s.
Control: `composer-2.5` returned `status=finished` and the expected
text. Further probes of listed IDs:

| ID | Local `Agent.create` + `run.wait()` |
|---|---|
| `composer-2.5` | finished |
| `grok-4.6` | finished |
| `claude-opus-5` | error, empty output |
| `claude-sonnet-5` | error, empty output |
| `claude-opus-4-6` | error, empty output |
| `claude-haiku-4-5` | error, empty output |
| `gpt-5.5` | error, empty output |
| `gpt-5.6-sol` | error, empty output |
| `gpt-5.4-mini` | error, empty output |
| `gemini-3.1-pro` | error, empty output |

So `Cursor.models.list()` answers "can this account see the ID?", not
"will the local SDK runtime execute it?". The harness runs on GitHub
Actions with `local=LocalAgentOptions(cwd=...)` (ADR-0009): Test Agent
must hit a live uvicorn on localhost, which a cloud agent on a different
VM cannot see.

## Decision

1. Treat local executability as a hard constraint on Test/Review model
   IDs until/unless those agents move off the GitHub-hosted runner's
   localhost.
2. Dev Agent stays on `composer-2.5` (already proven locally, ADR-0013).
3. Test Agent and Review Agent use `grok-4.6` — the strongest ID that
   actually finished a local run in the probe above, and a different
   model family from the writer, preserving ADR-0013's "don't verify
   with the same model that wrote the code" intent.
4. Agent scripts must log `result.status`, `duration_ms`, and
   `result.result` after `run.wait()`, and surface a diagnostic on
   silent local rejections instead of posting "UNKNOWN / 0 failures".

## Alternatives considered

- **Keep `claude-opus-5` and hope GitHub runners differ from this Mac** —
  rejected; the #237 Actions logs already showed the same ~9s empty
  error on `ubuntu-latest`.
- **Move Test/Review to cloud agents so opus-5 can run** — rejected for
  now. Test Agent's black-box contract is "hit the live server the
  workflow just booted on 127.0.0.1". A cloud VM does not share that
  loopback. Review Agent *could* go cloud (it only needs a diff), but
  splitting runtimes per role adds auth/repo-clone surface we do not
  need while `grok-4.6` works locally. Revisit if local-executable
  high-end IDs disappear or prove too weak on business-logic tickets.
- **Fall back to `composer-2.5` for Test/Review** — rejected; that is
  the exact same-model-for-write-and-verify setup ADR-0013 was written
  to leave. `grok-4.6` is available and locally executable.

## Consequences

- Verification is still on a different, stronger-reasoning model than
  generation, but not on the account's strongest *listed* model. If
  local runtime later executes `claude-opus-5`, switch the workflow env
  vars back — the intent in ADR-0013 is unchanged.
- A listed-but-unexecutable ID will still fail closed (`needs-rework`,
  no auto-merge) rather than fail open. The GitHub comment will now
  include the diagnostic instead of "UNKNOWN / 0 failures".
