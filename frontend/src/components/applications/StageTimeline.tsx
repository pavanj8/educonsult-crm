import { PIPELINE_STAGE_LABELS } from '../../types/application'
import type { PipelineStage } from '../../types/application'
import type { StageHistoryEntry } from '../../api/applications'

function stageLabel(stage: string | null): string {
  if (!stage) {
    return 'Created'
  }
  return PIPELINE_STAGE_LABELS[stage as PipelineStage] ?? stage
}

function formatDateTime(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString()
}

interface StageTimelineProps {
  entries: StageHistoryEntry[]
}

/**
 * Read-only timeline of an application's pipeline-stage transitions (E25;
 * Journey J18). Presentational: the host supplies the stage-history entries.
 * Renders them oldest-first as an accessible ordered list, each showing the
 * from -> to transition (human labels), the timestamp, and any captured reason.
 */
export default function StageTimeline({ entries }: StageTimelineProps) {
  if (entries.length === 0) {
    return <p data-testid="stage-timeline-empty">No stage history yet.</p>
  }

  const ordered = [...entries].sort((a, b) => a.changed_at.localeCompare(b.changed_at))

  return (
    <ol className="stage-timeline" data-testid="stage-timeline" aria-label="Application stage history">
      {ordered.map((entry) => (
        <li key={entry.id} className="stage-timeline__item" data-testid={`stage-timeline-entry-${entry.id}`}>
          <span className="stage-timeline__transition">
            {stageLabel(entry.from_stage)} → {stageLabel(entry.to_stage)}
          </span>{' '}
          <time dateTime={entry.changed_at}>{formatDateTime(entry.changed_at)}</time>
          {entry.reason ? <p className="stage-timeline__reason">{entry.reason}</p> : null}
        </li>
      ))}
    </ol>
  )
}
