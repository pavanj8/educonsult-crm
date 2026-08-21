import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import StageTimeline from './StageTimeline'
import type { StageHistoryEntry } from '../../api/applications'

function entry(over: Partial<StageHistoryEntry>): StageHistoryEntry {
  return {
    id: 1, application_id: 9, from_stage: 'registered', to_stage: 'counseling',
    changed_by_user_id: 7, changed_at: '2026-02-01T10:00:00Z', reason: null, ...over,
  }
}

describe('StageTimeline', () => {
  it('shows an empty state when there are no entries', () => {
    render(<StageTimeline entries={[]} />)
    expect(screen.getByTestId('stage-timeline-empty')).toBeInTheDocument()
  })

  it('renders one entry per transition with human-readable stage labels', () => {
    render(<StageTimeline entries={[entry({ id: 1, from_stage: 'registered', to_stage: 'counseling' })]} />)
    const row = screen.getByTestId('stage-timeline-entry-1')
    expect(within(row).getByText(/Registered → Counseling/)).toBeInTheDocument()
  })

  it('labels a null from_stage as "Created" and shows the reason', () => {
    render(<StageTimeline entries={[entry({ id: 2, from_stage: null, to_stage: 'rejected', reason: 'Docs missing' })]} />)
    const row = screen.getByTestId('stage-timeline-entry-2')
    expect(within(row).getByText(/Created → Rejected/)).toBeInTheDocument()
    expect(within(row).getByText('Docs missing')).toBeInTheDocument()
  })

  it('orders entries oldest-first by changed_at', () => {
    render(
      <StageTimeline
        entries={[
          entry({ id: 10, changed_at: '2026-03-01T10:00:00Z', to_stage: 'offer_letter' }),
          entry({ id: 11, changed_at: '2026-01-01T10:00:00Z', to_stage: 'counseling' }),
        ]}
      />,
    )
    const items = screen.getAllByRole('listitem')
    expect(items[0]).toHaveAttribute('data-testid', 'stage-timeline-entry-11')
    expect(items[1]).toHaveAttribute('data-testid', 'stage-timeline-entry-10')
  })
})
