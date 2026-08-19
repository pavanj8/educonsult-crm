# ADR-0012: Paced queue picker for processing a large issue backlog unattended

**Status**: Accepted — implemented
**Date**: 2026-08-19

## Context

After ADR-0011 (auto-merge on green), the user asked to kick off the rest
of the MVP backlog (96 open task issues) and explicitly required that
this keep running "even if I close my laptop" — i.e. with no dependency
on their machine or an active chat session.

The first attempt added the `agent:ready-for-dev` trigger label to all 96
issues in a tight loop (~2 seconds apart). This exposed a wrong
assumption about `agent-harness.yml`'s `concurrency:` group (added in the
same work session to prevent parallel Dev Agents from conflicting on
overlapping files): a `concurrency:` group with `cancel-in-progress:
false` holds at most **one running run and one queued run** per group —
it is not an unbounded FIFO. Firing 96 triggers within seconds caused
GitHub to cancel 94 of them, leaving only the very last one running. Two
issues (#55, #237) had, by chance, broken through to full completion
before the cancellations caught up; the rest were left with a dangling
`agent:ready-for-dev` label and no actual run.

## Decision

Add a second, small scheduled workflow,
`.github/workflows/agent-harness-queue-picker.yml`, that:

1. Runs every 5 minutes via `schedule: cron`, entirely on GitHub's
   infrastructure.
2. Checks whether an `agent-harness.yml` run is currently `in_progress`
   or `queued`; if so, does nothing this tick.
3. If idle, finds the lowest-numbered open issue labeled `task` +
   `phase:mvp` that has **no** `agent:*` label yet (i.e. never triggered),
   and adds `agent:ready-for-dev` to it — and only that one issue.

This turns "queue the whole backlog" into "one new trigger at a time,
paced by a cron tick and gated on the harness being idle," which is safe
under the concurrency group's real "1 running + 1 queued" semantics
(never more than one new arrival at a time) and requires nothing to stay
running locally.

Cleanup performed once, by hand, before enabling this: removed the
dangling `agent:ready-for-dev` label from the 94 issues whose runs were
cancelled, so the picker would see them as untouched and eligible again.
Issue #55's PR had actually merged despite the issue not auto-closing
(tracked as a known gap in `agents/README.md`); closed manually.

## Alternatives considered

- **Raise/remove the concurrency group and rely on Actions' own job
  queueing** — rejected; Actions queues jobs across *different* workflows
  fine, but jobs in the same `concurrency:` group specifically follow the
  "1 running + 1 queued, others cancelled" rule by design, not a FIFO.
  There is no built-in way to get an unbounded FIFO queue purely from
  `concurrency:`.
- **A single workflow run that loops over the whole backlog in one job**
  — rejected; would need to fit the entire backlog inside one job's
  execution time limit (6h on GitHub-hosted runners) and would make each
  ticket's Dev/Test/Review agents share one long-lived process rather
  than the clean one-run-per-iteration model already in place, harder to
  inspect per-ticket in the Actions UI.
- **Trigger from the local machine with a sleep/poll loop** — explicitly
  rejected per the user's requirement; anything driven by a process on
  the user's laptop defeats the purpose of moving execution to GitHub
  Actions (ADR-0009).

## Consequences

- The MVP backlog (94 remaining untouched task issues as of this
  decision) now drains automatically, roughly one ticket every few
  minutes depending on how long each Dev/Test/Review iteration takes,
  with zero ongoing action from the user or from any chat session.
- Failed iterations (`agent:needs-rework`) are *not* retried by the
  picker — it only ever picks issues with no `agent:*` label at all,
  matching ADR-0009's "no auto-loop retries" stance. A human still needs
  to decide whether/how to re-run a failed ticket.
- Once the backlog is exhausted the picker just no-ops every 5 minutes;
  cheap, but worth disabling (or leaving — it's harmless) once phase:mvp
  is fully done.
- If a burst-trigger is ever needed again (e.g. a future phase), do not
  label many issues in a tight loop; either let the picker's scope
  include that label set, or add a proper self-hosted queue if throughput
  needs to be faster than one-at-a-time.

## Amendment (2026-08-19, same day): label-only trigger silently did nothing

The first implementation only did `gh issue edit --add-label
agent:ready-for-dev` from the picker job. This looked correct (the picker
itself reported "success" on every run) but never actually started
`agent-harness.yml`: GitHub does not let events triggered by the
repository's default `GITHUB_TOKEN` start other workflow runs, precisely
to prevent infinite trigger loops. `workflow_dispatch`/`repository_dispatch`
are the only exceptions. Since the picker's `gh issue edit` runs as
`github-actions[bot]` using `GITHUB_TOKEN`, the `issues: types: [labeled]`
trigger on `agent-harness.yml` never fired. Discovered when three
consecutive picker ticks (13:51, 14:27, 15:03) each labeled a different
issue (#56, #57, #58) and none of them ever ran — an hour passed with the
user's laptop closed and nothing happened.

Fix: the picker now also runs `gh workflow run agent-harness.yml -f
issue_number=$NEXT` — an explicit `workflow_dispatch` call, which *is*
exempt from this restriction — in addition to the label add (kept for
bookkeeping/visibility and for the picker's own "already touched" check).
Required bumping the picker's `permissions.actions` from `read` to
`write`. The three stuck issues (#56-#58) were re-triggered by hand.

## Amendment (2026-08-19, same day): `gh workflow run` needs `contents: read`

The `workflow_dispatch` fix above is correct in principle, but the
picker's `permissions:` block only granted `issues: write` and
`actions: write`. `gh workflow run` still has to resolve
`repository.defaultBranchRef` over GraphQL, which needs `contents: read`.
Without it, a picker tick at 16:13 UTC labeled #58 then died with:

```
unable to determine default branch for pavanj8/educonsult-crm:
GraphQL: Resource not accessible by integration (repository.defaultBranchRef)
```

Same stuck shape as the previous amendment: issue has
`agent:ready-for-dev`, no harness run. Fix: add `contents: read`, and
pass `--ref main` so `gh` does not have to guess the default branch.
Issue #58 was re-dispatched by hand after this landed.
