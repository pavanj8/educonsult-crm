# ADR-0026: Harden PR authorship + lower the Dev turn cap

**Status**: Accepted — implemented
**Date**: 2026-08-21

## Context

1. **Bot-authored PRs still slipped through.** ADR-0023 authors PRs via GH_PAT so
   CI isn't held by the public-repo first-time-contributor approval policy. It
   works for most PRs, but intermittently one is created as `github-actions[bot]`
   (e.g. GH_PAT not applied on the original create), whose CI then sits as
   `action_required` waiting for manual approval (seen on #173).
2. **A churning Dev run ran ~49 min.** Dev inherited the engine's `MAX_TURNS=140`
   (raised for tool-heavy Test/Review). At M3's per-turn latency that is ~47 min
   of churn before the safety rail trips — and it holds the single Dev
   concurrency slot the whole time, pacing the drain.

## Decision

1. **PR authorship hardening.** The "Open or update pull request" step now:
   retries `gh pr create` on transient failures; if the resulting PR is
   bot-authored, **closes and recreates it with GH_PAT**; and if it is *still*
   bot-authored, **fails the step loudly** with an actionable error (refresh
   GH_PAT). PRs are thus never silently left bot-authored / approval-gated.
2. **Dev turn cap.** Dev runs with `DEV_MAX_TURNS=50` (env-overridable) instead
   of the shared 140. With the context pack + `str_replace` + "run check.sh once"
   guidance, a healthy Dev run finishes well under 50; a churning one now
   fails-closed to `needs-rework` in far less time instead of wedging the slot.

## Consequences

- Bot-authored/approval-gated agent PRs stop occurring; a genuine GH_PAT problem
  now surfaces as a loud run failure instead of a silently stuck PR.
- Recreating a bot PR changes its number, but feedback lives on the issue (not
  the PR), so nothing is lost.
- The Dev cap trades a few premature fail-closed retries for bounded run time; if
  legitimately-complex tickets hit the cap often, raise `DEV_MAX_TURNS`.
