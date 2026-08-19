# ADR-0003: Three-agent separation of concerns: Dev / Test / Review

**Status**: Accepted
**Date**: 2026-08-19

## Context

A single agent that both writes code and judges its own correctness has an
obvious conflict of interest — it can rationalize its own shortcuts. The
user explicitly asked for independent verification "not based on the dev
agent implemented code" plus a review from multiple senior-engineering
perspectives.

## Decision

Split responsibilities into three separate agents, each with a distinct
mandate and distinct context window:

1. **Dev Agent** — reads ticket + requirements + epic + existing code,
   implements, runs its own unit tests.
2. **Test Agent** — independently black-box tests the running application
   against requirements/ticket only (see
   [ADR-0004](0004-test-agent-independence.md)); never trusts the Dev
   Agent's own test suite as evidence of correctness.
3. **Review Agent** — reviews the Dev Agent's actual code diff as a senior
   Security Analyst, Software Architect, Senior Developer, UX Architect,
   and Test Engineer, in one pass.

All three read/write a shared ticket file as the coordination point (see
[ADR-0005](0005-ticket-closure-policy.md)).

## Alternatives considered

- **Single agent, multi-persona prompting** (one agent asked to "now review
  your own work") — rejected: same context/conversation history biases the
  self-review; doesn't give the independence the user asked for.

## Consequences

- Three separate CLI scripts / Cursor SDK agent sessions per ticket
  iteration — more moving parts, but each is independently testable and
  replaceable.
- Coordination happens only through durable artifacts (the ticket file,
  git diff, live HTTP server) — no shared in-memory state or conversation
  history between agents. This is what makes it possible to later move
  each stage into its own GitHub Actions job (ADR-0008).
