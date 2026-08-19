# ADR-0013: Asymmetric model tiering — cheap model to write, high-end model to verify

**Status**: Accepted — implemented
**Date**: 2026-08-19

## Context

Dev Agent, Test Agent, and Review Agent all defaulted to the same model,
`composer-2.5` — fast and cost-efficient, purpose-built for agentic
coding loops (edit → run → fix), but not the account's strongest
available reasoning model.

Across the first several tickets run through the harness (#54, #59, #55),
the Test Agent and Review Agent reported no defects. The user asked
whether it was possible to use a cheaper model for code generation and a
stronger one for review/testing, and separately flagged surprise that
verification kept coming back clean — a fair question, since running the
generator and the two verifiers on the same, cheaper model narrows the
gap between "the code looks right to this model" and "this model finds
problems in it." (Separately, and not a model-quality issue:
issue #237 *did* get a Test Agent failure, but the resulting PR was
merged manually, bypassing the gate — see the queue picker bug of the
same day for the circumstances.)

Queried the account's actual available models (`Cursor.models.list()`)
rather than assuming IDs, per the SDK skill's guidance. Fast/cheap tier
available: `composer-2.5`, `gpt-5.4-mini`, `gpt-5.4-nano`,
`claude-haiku-4-5`, `gemini-3.x-flash`. High-end tier available:
`claude-opus-5`, `claude-sonnet-5`, `gpt-5.6-sol`, `gpt-5.5`,
`gemini-3.1-pro`, plus other `claude-opus-4-*` variants.

## Decision

Tier models by role, asymmetrically:

- **Dev Agent** → `composer-2.5` (unchanged). Writing code across a large
  ticket backlog is the highest-volume, most repeated call in the
  harness; composer-2.5 is fast, cheap, and already proven adequate for
  the scaffolding-level tickets run so far.
- **Test Agent** → `claude-opus-5`. Independent black-box verification is
  exactly where a stronger reasoning model earns its cost: designing
  non-obvious edge cases and boundary tests from requirements/journeys
  alone (never reading the implementation first, per ADR-0008) benefits
  directly from more capable reasoning.
- **Review Agent** → `claude-opus-5`. Same rationale, across all five
  review perspectives (security, architecture, code quality, API/UX
  design, test adequacy) — this is the harness's last line of defense
  before auto-merge (ADR-0011), so it should run on the account's
  strongest available model, not the same model that wrote the code.

Implemented as `--model` CLI flags on all three scripts (already
existed, just never passed by the workflow), driven by three new env
vars at the top of `.github/workflows/agent-harness.yml`
(`DEV_AGENT_MODEL`, `TEST_AGENT_MODEL`, `REVIEW_AGENT_MODEL`) so the
tiering can be retuned in one visible place without touching
`agents/*.py`. Each script's own `DEFAULT_MODEL` constant is updated to
match, as the fallback for local/manual runs.

## Alternatives considered

- **Use the single strongest model everywhere** — rejected for now on
  cost/throughput grounds: Dev Agent runs far more total agent-minutes
  across a ~190-ticket backlog than Test+Review combined per ticket, and
  composer-2.5 has already produced clean, mergeable implementations for
  the tickets run so far.
- **Use the fast tier everywhere (status quo)** — rejected per the user's
  explicit request and the reasoning above: verification benefits more
  from model strength than generation does, for this shape of work.
- **Keep model IDs hardcoded only in `agents/*.py`, no workflow env vars**
  — rejected; putting the tiering in the workflow file makes it visible
  and tunable without a code change, which matters given "model lists
  evolve" (the SDK skill's own caution) and cost/quality tradeoffs are
  likely to be revisited as the backlog moves into more complex,
  business-logic-heavy epics.

## Consequences

- Slightly higher cost per ticket (two of three agent calls now run on a
  more expensive model), in exchange for verification that should be
  strictly harder to satisfy than before — the intended trade.
- If Test/Review now start finding more issues (the expected outcome),
  more tickets will land in `agent:needs-rework` rather than
  auto-merging on the first iteration. That's a feature, not a
  regression: ADR-0009 deliberately made needs-rework a safe, cheap
  outcome (no auto-retry, no auto-merge) rather than a failure mode to
  avoid.
- If Dev Agent's fast-tier output quality proves insufficient once the
  backlog reaches more complex, multi-tenant/business-logic epics (E2
  RBAC, E5 Auth, etc.), revisit and consider tiering Dev Agent up too —
  not decided here, deferred until there's evidence either way.
- Model IDs are a point-in-time snapshot of what this account can access
  (queried 2026-08-19); if either of these IDs is retired, this file
  documents the intent (fast-for-write, strong-for-verify) so a
  replacement can be chosen consistent with that intent, not just
  picked arbitrarily.
