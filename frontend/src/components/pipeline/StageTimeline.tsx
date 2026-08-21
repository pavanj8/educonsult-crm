import { useMemo } from 'react'

import type { PipelineStage } from '../../types/application'
import { PIPELINE_STAGE_LABELS } from '../../types/application'
import type { StageHistoryEntry } from '../../types/stageHistory'

/** Canonical non-terminal forward-progression order (Requirements §5; E25/J18). */
const FORWARD_STAGE_ORDER: readonly PipelineStage[] = [
  'registered',
  'counseling',
  'university_shortlisting',
  'application_submitted',
  'document_verification',
  'offer_letter',
  'visa_processing',
  'loan_processing',
  'enrolled',
]

type StageTimelineItemState = 'completed' | 'current' | 'future'

interface StageTimelineItem {
  stage: PipelineStage
  label: string
  state: StageTimelineItemState
  entry: StageHistoryEntry | null
}

export interface StageTimelineProps {
  currentStage: PipelineStage
  history?: StageHistoryEntry[]
  emptyMessage?: string
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return iso
  }
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** True for terminal stages (Requirements §5: enrolled / rejected / withdrawn). */
function isTerminal(stage: PipelineStage): boolean {
  return stage === 'enrolled' || stage === 'rejected' || stage === 'withdrawn'
}

/**
 * Find the last stage in ``forwardOrder`` that the application has reached,
 * given the history of transitions. The "reached" set is the union of every
 * ``to_stage`` recorded in history plus the application's current stage.
 *
 * Returns ``null`` when no forward-path stage has been reached (e.g. an
 * empty history where the current stage isn't on the forward path).
 */
function lastReachedForwardStage(
  forwardOrder: readonly PipelineStage[],
  currentStage: PipelineStage,
  history: StageHistoryEntry[],
): PipelineStage | null {
  const reached = new Set<PipelineStage>([currentStage])
  for (const entry of history) {
    reached.add(entry.to_stage)
  }
  for (let i = forwardOrder.length - 1; i >= 0; i -= 1) {
    const candidate = forwardOrder[i]
    if (reached.has(candidate)) {
      return candidate
    }
  }
  return null
}

/**
 * Build the timeline items from the current stage and recorded history.
 *
 * Semantics:
 *   - Stages in the history with ``to_stage == X`` are rendered as
 *     ``completed``, with the latest entry's timestamp / reason winning.
 *   - The application's current stage is rendered as ``current``.
 *   - For a non-terminal current stage, every unvisited forward stage is
 *     rendered as ``future`` so the user sees the full pipeline.
 *   - For a terminal current stage (``enrolled``), the entire forward path
 *     up to and including enrolled is rendered. No rows beyond.
 *   - For a terminal current stage not on the forward path (``rejected``
 *     / ``withdrawn``), only the forward-path stages the application
 *     actually reached are rendered; the terminal is appended last as
 *     ``current`` so the user sees the outcome.
 */
function buildItems(
  currentStage: PipelineStage,
  history: StageHistoryEntry[],
): StageTimelineItem[] {
  const historyByStage = new Map<PipelineStage, StageHistoryEntry>()
  // The latest history entry for a given resulting stage wins — earlier
  // entries (e.g. a stage an application was bounced back into) would be
  // overwritten in a real backend rewind, which v1 does not support.
  for (const entry of history) {
    historyByStage.set(entry.to_stage, entry)
  }

  const reached = new Set<PipelineStage>([currentStage])
  for (const entry of history) {
    reached.add(entry.to_stage)
  }

  const currentIsTerminal = isTerminal(currentStage)
  const isOnForwardPath = (FORWARD_STAGE_ORDER as readonly PipelineStage[]).includes(currentStage)

  // Decide how far to walk the forward order.
  let walkToIndex: number
  if (!currentIsTerminal) {
    // Non-terminal current: walk the whole pipeline so future rows render.
    walkToIndex = FORWARD_STAGE_ORDER.length - 1
  } else if (currentStage === 'enrolled') {
    walkToIndex = FORWARD_STAGE_ORDER.length - 1
  } else {
    // rejected / withdrawn — only walk as far as the application actually got.
    const lastReached = lastReachedForwardStage(
      FORWARD_STAGE_ORDER,
      currentStage,
      history,
    )
    if (lastReached == null) {
      walkToIndex = -1
    } else {
      walkToIndex = FORWARD_STAGE_ORDER.indexOf(lastReached)
    }
  }

  const items: StageTimelineItem[] = []
  for (let i = 0; i <= walkToIndex; i += 1) {
    const stage = FORWARD_STAGE_ORDER[i]
    const entry = historyByStage.get(stage) ?? null
    let state: StageTimelineItemState
    if (stage === currentStage) {
      state = 'current'
    } else if (reached.has(stage)) {
      state = 'completed'
    } else {
      state = 'future'
    }
    items.push({ stage, label: PIPELINE_STAGE_LABELS[stage], state, entry })
  }

  // Append a rejected/withdrawn terminal as the final current item when it
  // is not already on the forward path.
  if (currentIsTerminal && !isOnForwardPath) {
    const entry = historyByStage.get(currentStage) ?? null
    items.push({
      stage: currentStage,
      label: PIPELINE_STAGE_LABELS[currentStage],
      state: 'current',
      entry,
    })
  }

  return items
}

export default function StageTimeline({
  currentStage,
  history = [],
  emptyMessage = 'No stage transitions recorded yet.',
}: StageTimelineProps) {
  const items = useMemo(() => buildItems(currentStage, history), [currentStage, history])

  if (history.length === 0 && currentStage === 'registered') {
    return (
      <section
        className="stage-timeline stage-timeline--empty"
        data-testid="stage-timeline"
        aria-label="Application stage timeline"
      >
        <p className="stage-timeline__empty" data-testid="stage-timeline-empty">
          {emptyMessage}
        </p>
      </section>
    )
  }

  return (
    <section
      className="stage-timeline"
      data-testid="stage-timeline"
      aria-label="Application stage timeline"
    >
      <ol className="stage-timeline__list" data-testid="stage-timeline-list">
        {items.map((item) => {
          const isCurrent = item.state === 'current'
          const isCompleted = item.state === 'completed'
          return (
            <li
              key={item.stage}
              className={
                'stage-timeline__item' +
                (isCurrent ? ' stage-timeline__item--current' : '') +
                (isCompleted ? ' stage-timeline__item--completed' : '') +
                (item.state === 'future' ? ' stage-timeline__item--future' : '')
              }
              data-testid={`stage-timeline-item-${item.stage}`}
              data-state={item.state}
              aria-current={isCurrent ? 'step' : undefined}
            >
              <span
                className="stage-timeline__marker"
                data-testid={`stage-timeline-marker-${item.stage}`}
                aria-hidden="true"
              />
              <div className="stage-timeline__content">
                <p className="stage-timeline__stage">{item.label}</p>
                <p
                  className="stage-timeline__status"
                  data-testid={`stage-timeline-status-${item.stage}`}
                >
                  {isCurrent
                    ? 'Current stage'
                    : isCompleted
                      ? 'Completed'
                      : 'Pending'}
                </p>
                {item.entry?.changed_at ? (
                  <time
                    className="stage-timeline__time"
                    dateTime={item.entry.changed_at}
                    data-testid={`stage-timeline-time-${item.stage}`}
                  >
                    {formatTimestamp(item.entry.changed_at)}
                  </time>
                ) : null}
                {item.entry?.reason ? (
                  <p
                    className="stage-timeline__reason"
                    data-testid={`stage-timeline-reason-${item.stage}`}
                  >
                    {item.entry.reason}
                  </p>
                ) : null}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
