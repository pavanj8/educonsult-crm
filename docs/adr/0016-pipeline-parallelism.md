# ADR-0016: Pipeline parallelism — Dev, Test, and Review on different tickets

**Status**: Accepted — implemented
**Date**: 2026-08-19

## Context

ADR-0009 put Dev, the hard test gate, Test Agent, and Review Agent in
**one sequential GitHub Actions job**, and a repo-wide `concurrency:`
group made that job the only harness work allowed at a time. The result:
while Dev Agent coded ticket A, Test Agent and Review Agent sat idle,
even if tickets B and C already had a pushed branch waiting for
verification.

The user asked why those agents were idle, and required that Dev can
keep working one ticket while Test and Review work **other** tickets,
with context (issue, branch, iteration) kept straight.

Same-ticket order is unchanged and mandatory: Test/Review of ticket A
must not start until Dev has pushed ticket A's branch for that
iteration. They do not scan open issues looking for work. Cross-ticket
overlap is only `Dev(B)` while `Test(A)`/`Review(A)` verify the branch
Dev already finished.

## Decision

1. **Test/Review never pick from the backlog.** They run only on the
   issue Dev Agent just finished, same iteration, same `agent/issue-N`
   branch. The queue picker starts Dev jobs only. After Dev commits and
   pushes that branch, `agent-harness.yml` dispatches `agent-test.yml`
   and `agent-review.yml` with that issue number and iteration. Those
   workflows refuse to run if Dev has not recorded a result for that
   exact issue+iteration. Parallelism is therefore:

   `Dev(B) || Test(A) || Review(A)` — never Test(C) when Dev never
   touched C.
2. **Serialize Dev only.** The historic `agent-harness-queue` concurrency
   group stays on the Dev workflow. Test/Review use per-issue groups
   (`agent-test-N`, `agent-review-N`) so different tickets can verify in
   parallel, including Test(A) overlapping Review(A) after the same Dev
   push.
3. **Join before merge or retry.** Either Test or Review may finish
   first. Both dispatch `agent-finalize.yml`, which reads
   `agent:{gate,test,review}-{pass,fail}` labels. If any result is
   missing it no-ops (`waiting`); when all three exist it runs the
   existing finalize/auto-merge/auto-retry path (ADR-0011, ADR-0015).
   `start_new_iteration` clears those result labels so "label present"
   always means *this* iteration.
4. **Picker starts Dev when Dev is idle**, not when Test/Review are idle.
   A ticket in the verify phase (has `agent:*` labels but not
   `needs-rework`) is not eligible for a new Dev pick, so we never start
   iteration N+1 until N's Test+Review have joined.

## Alternatives considered

- **Keep one sequential job (ADR-0009)** — rejected; it is exactly why
  Test/Review sat idle.
- **Parallelize Dev across tickets too** — rejected. Two Dev Agents
  committing overlapping files (Compose, shared models) was the original
  reason for a repo-wide lock.
- **One workflow, three jobs with `needs:`** — rejected; `needs: dev`
  would still hold Test/Review until *that* ticket's Dev finished, and
  would not let Test(B) run during Dev(A).
- **Let Test/Review pick any open ticket** — rejected; verifying a
  ticket Dev has not implemented is wasted work. They are a fan-out from
  that ticket's Dev stage, not a second queue.

## Consequences

- Throughput is bounded by Dev (one at a time) plus however many Test
  and Review jobs GitHub will run in parallel. Cursor API cost per wall
  clock hour goes up; wall-clock backlog drain goes down.
- Context is the issue number + `agent/issue-N` branch + iteration input.
  Mixing those is a bug; the join step also refuses to finalize if the
  issue's current iteration label does not match the dispatched
  iteration (`stale`).
- In-flight pre-split jobs (Dev+Test+Review in one workflow) keep using
  the old YAML until they finish; new dispatches after this lands use
  the pipeline.
