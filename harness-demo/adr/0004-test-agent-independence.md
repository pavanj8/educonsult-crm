# ADR-0004: Test Agent independence — black-box, no access to implementation before testing

**Status**: Accepted
**Date**: 2026-08-19

## Context

If the Test Agent reads the Dev Agent's implementation (or its unit tests)
before designing its own tests, it will unconsciously test "what the code
does" instead of "what the ticket/requirements demand" — defeating the
point of independent verification.

## Decision

The Test Agent's prompt enforces strict rules:

1. Never open/read `backend/tests/` (the Dev Agent's own tests), at any
   point.
2. Never read `backend/app/` (implementation) **before** designing and
   running its own black-box tests. It may read source **after** observing
   a failure, purely to determine root cause for its report.
3. Test only over real HTTP against a live, freshly booted server instance
   — never call application code directly in-process.
4. Derive test cases only from `requirements.md`, `epics.md`, and the
   ticket's acceptance criteria — including boundary/negative cases the
   ticket implies even if not spelled out.

## Alternatives considered

- **Test Agent reads implementation for context "to write better tests"**
  — rejected: this is exactly the coupling that makes self-verification
  untrustworthy; a requirement the code silently fails to meet would never
  surface if the test author is influenced by the code.

## Consequences

- The Test Agent may occasionally "rediscover" edge cases the Dev Agent
  already handles — acceptable, this is a cost of genuine independence,
  not a bug.
- Root-cause diagnosis (allowed post-failure) requires the Test Agent to
  clearly separate "here is the observed black-box failure" from "here is
  my diagnosis after reading the code" in its report, so evidence and
  interpretation aren't conflated.
