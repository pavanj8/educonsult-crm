# ADR-0025: Cut rework — sibling-ticket awareness + frontend Test N/A

**Status**: Accepted — implemented
**Date**: 2026-08-21

## Context

Sampling real failures showed two *systemic* (non-model) causes of frequent
Test/Review failure, not just "poor code":

1. **Re-implementing existing code.** #169's Review FAIL: the Dev Agent "believed
   it was the first ticket to add the StageHistory schema, but origin/main already
   contained it via #168." The repo map lists files but the agent didn't connect
   "it exists" with "don't recreate it," causing duplicate models/migrations and
   conflicts.
2. **Frontend tickets false-failing Test.** The Test Agent only serves the FastAPI
   backend, so a frontend-only ticket (#147) has no HTTP surface — it FAILed and
   churned to the iteration cap for no real reason.

## Decision

1. **Sibling awareness.** `github_ticket_utils.epic_sibling_status()` lists the
   epic's other tickets and whether each is merged; the Dev prompt injects it under
   "what already exists (do NOT recreate)," plus a hard rule to import/extend
   existing models/migrations/schemas/endpoints rather than re-adding them.
2. **Frontend/tests-only Test N/A.** The Test Agent now returns PASS-by-N/A when the
   ticket changed no `backend/app/` code (`backend_app_changed()` vs origin/main),
   the same way it already does for infra-only tickets — instead of failing on a
   backend it can't exercise the frontend against.

## Consequences

- Kills two whole failure classes (duplicate-implementation, frontend false-fails)
  that were inflating the failure/iteration count, independent of model quality.
- Frontend and pure-test tickets now pass Test-by-N/A and rely on Review + the hard
  gate + CI, which is the correct division of labor.
- Sibling status adds one `gh issue list` per Dev run (~1-2s); acceptable.
- Deeper code-quality lift (conventions primer, exemplar files, self-review
  checklist) is deferred to a follow-up so each lever can be measured.
