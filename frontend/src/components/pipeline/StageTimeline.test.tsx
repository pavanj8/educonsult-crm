import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import StageTimeline from './StageTimeline'
import type { PipelineStage } from '../../types/application'
import type { StageHistoryEntry } from '../../types/stageHistory'

function entry(overrides: Partial<StageHistoryEntry> & { to_stage: PipelineStage }): StageHistoryEntry {
  return {
    id: 1,
    application_id: 100,
    from_stage: null,
    changed_at: '2026-01-15T10:00:00Z',
    reason: null,
    changed_by_user_id: null,
    ...overrides,
  }
}

describe('StageTimeline', () => {
  it('renders an empty state when no history exists and the app is still registered', () => {
    render(<StageTimeline currentStage="registered" />)

    expect(screen.getByTestId('stage-timeline')).toBeInTheDocument()
    expect(screen.getByTestId('stage-timeline-empty')).toHaveTextContent(
      'No stage transitions recorded yet.',
    )
    expect(screen.queryByTestId('stage-timeline-list')).not.toBeInTheDocument()
  })

  it('renders the canonical forward progression with completed, current, and future items', () => {
    const history: StageHistoryEntry[] = [
      entry({ id: 1, to_stage: 'registered', changed_at: '2026-01-15T09:00:00Z' }),
      entry({
        id: 2,
        from_stage: 'registered',
        to_stage: 'counseling',
        changed_at: '2026-01-16T10:00:00Z',
      }),
      entry({
        id: 3,
        from_stage: 'counseling',
        to_stage: 'university_shortlisting',
        changed_at: '2026-01-20T11:30:00Z',
      }),
    ]

    render(<StageTimeline currentStage="university_shortlisting" history={history} />)

    expect(screen.getByTestId('stage-timeline-list')).toBeInTheDocument()

    const registeredItem = screen.getByTestId('stage-timeline-item-registered')
    expect(registeredItem.dataset.state).toBe('completed')
    expect(registeredItem.getAttribute('aria-current')).toBeNull()
    expect(within(registeredItem).getByTestId('stage-timeline-status-registered')).toHaveTextContent(
      'Completed',
    )

    const counselingItem = screen.getByTestId('stage-timeline-item-counseling')
    expect(counselingItem.dataset.state).toBe('completed')

    const currentItem = screen.getByTestId('stage-timeline-item-university_shortlisting')
    expect(currentItem.dataset.state).toBe('current')
    expect(currentItem.getAttribute('aria-current')).toBe('step')
    expect(within(currentItem).getByTestId('stage-timeline-status-university_shortlisting')).toHaveTextContent(
      'Current stage',
    )

    const futureItem = screen.getByTestId('stage-timeline-item-application_submitted')
    expect(futureItem.dataset.state).toBe('future')
    expect(within(futureItem).getByTestId('stage-timeline-status-application_submitted')).toHaveTextContent(
      'Pending',
    )
  })

  it('shows the transition timestamp for completed stages', () => {
    const history: StageHistoryEntry[] = [
      entry({ id: 1, to_stage: 'registered' }),
      entry({
        id: 2,
        to_stage: 'counseling',
        changed_at: '2026-02-01T08:15:00Z',
      }),
    ]

    render(<StageTimeline currentStage="counseling" history={history} />)

    const time = screen.getByTestId('stage-timeline-time-counseling')
    expect(time.tagName.toLowerCase()).toBe('time')
    expect(time.getAttribute('datetime')).toBe('2026-02-01T08:15:00Z')
    // Format is locale-dependent; just verify some recognizable parts render.
    expect(time.textContent).toMatch(/2026/)
    expect(time.textContent).toMatch(/Feb/)
  })

  it('renders the optional reason text for a transition', () => {
    const history: StageHistoryEntry[] = [
      entry({ id: 1, to_stage: 'registered' }),
      entry({
        id: 2,
        to_stage: 'document_verification',
        changed_at: '2026-03-05T09:00:00Z',
        reason: 'All passport pages received',
      }),
    ]

    render(<StageTimeline currentStage="document_verification" history={history} />)

    expect(
      screen.getByTestId('stage-timeline-reason-document_verification'),
    ).toHaveTextContent('All passport pages received')
  })

  it('marks a terminal enrolled stage as current and every prior stage as completed', () => {
    const history: StageHistoryEntry[] = [
      entry({ id: 1, to_stage: 'registered' }),
      entry({ id: 2, from_stage: 'registered', to_stage: 'counseling' }),
      entry({ id: 3, from_stage: 'counseling', to_stage: 'university_shortlisting' }),
      entry({ id: 4, from_stage: 'university_shortlisting', to_stage: 'application_submitted' }),
      entry({ id: 5, from_stage: 'application_submitted', to_stage: 'document_verification' }),
      entry({ id: 6, from_stage: 'document_verification', to_stage: 'offer_letter' }),
      entry({ id: 7, from_stage: 'offer_letter', to_stage: 'visa_processing' }),
      entry({
        id: 8,
        from_stage: 'visa_processing',
        to_stage: 'enrolled',
        reason: 'Student accepted offer and paid deposit',
      }),
    ]

    render(<StageTimeline currentStage="enrolled" history={history} />)

    expect(screen.getByTestId('stage-timeline-item-registered').dataset.state).toBe('completed')
    expect(screen.getByTestId('stage-timeline-item-visa_processing').dataset.state).toBe('completed')
    expect(screen.getByTestId('stage-timeline-item-enrolled').dataset.state).toBe('current')

    expect(
      screen.getByTestId('stage-timeline-reason-enrolled'),
    ).toHaveTextContent('Student accepted offer and paid deposit')
  })

  it('renders rejected and withdrawn as terminal current items even though they are not on the forward path', () => {
    const history: StageHistoryEntry[] = [
      entry({ id: 1, to_stage: 'registered' }),
      entry({ id: 2, from_stage: 'registered', to_stage: 'counseling' }),
      entry({
        id: 3,
        from_stage: 'counseling',
        to_stage: 'rejected',
        changed_at: '2026-04-01T12:00:00Z',
        reason: 'Student declined to continue',
      }),
    ]

    render(<StageTimeline currentStage="rejected" history={history} />)

    expect(screen.getByTestId('stage-timeline-item-registered').dataset.state).toBe('completed')
    expect(screen.getByTestId('stage-timeline-item-counseling').dataset.state).toBe('completed')
    const rejectedItem = screen.getByTestId('stage-timeline-item-rejected')
    expect(rejectedItem.dataset.state).toBe('current')
    expect(rejectedItem.getAttribute('aria-current')).toBe('step')
    expect(screen.getByTestId('stage-timeline-reason-rejected')).toHaveTextContent(
      'Student declined to continue',
    )

    // No "future" rows beyond the terminal stage.
    expect(screen.queryByTestId('stage-timeline-item-enrolled')).not.toBeInTheDocument()
  })

  it('renders a withdrawn terminal stage with the recorded reason', () => {
    const history: StageHistoryEntry[] = [
      entry({ id: 1, to_stage: 'registered' }),
      entry({
        id: 2,
        from_stage: 'registered',
        to_stage: 'withdrawn',
        reason: 'Student relocated abroad',
      }),
    ]

    render(<StageTimeline currentStage="withdrawn" history={history} />)

    expect(screen.getByTestId('stage-timeline-item-withdrawn').dataset.state).toBe('current')
    expect(screen.getByTestId('stage-timeline-reason-withdrawn')).toHaveTextContent(
      'Student relocated abroad',
    )
  })

  it('uses a custom empty message when supplied', () => {
    render(
      <StageTimeline
        currentStage="registered"
        emptyMessage="Nothing to show yet."
      />,
    )

    expect(screen.getByTestId('stage-timeline-empty')).toHaveTextContent('Nothing to show yet.')
  })

  it('falls back to the raw timestamp string when the value is not a valid date', () => {
    const history: StageHistoryEntry[] = [
      entry({ id: 1, to_stage: 'registered' }),
      entry({ id: 2, to_stage: 'counseling', changed_at: 'not-a-date' }),
    ]

    render(<StageTimeline currentStage="counseling" history={history} />)

    const time = screen.getByTestId('stage-timeline-time-counseling')
    expect(time.getAttribute('datetime')).toBe('not-a-date')
    expect(time.textContent).toBe('not-a-date')
  })

  it('uses the latest history entry per stage when the same stage appears multiple times', () => {
    const history: StageHistoryEntry[] = [
      entry({ id: 1, to_stage: 'registered', changed_at: '2026-01-01T00:00:00Z' }),
      entry({
        id: 2,
        from_stage: 'registered',
        to_stage: 'counseling',
        changed_at: '2026-01-05T00:00:00Z',
      }),
      // Same stage again — the latest entry's timestamp/reason should win.
      entry({
        id: 3,
        from_stage: 'counseling',
        to_stage: 'counseling',
        changed_at: '2026-01-10T00:00:00Z',
        reason: 'Re-routed after a counselor swap',
      }),
    ]

    render(<StageTimeline currentStage="counseling" history={history} />)

    const counselingTime = screen.getByTestId('stage-timeline-time-counseling')
    expect(counselingTime.getAttribute('datetime')).toBe('2026-01-10T00:00:00Z')
    expect(
      screen.getByTestId('stage-timeline-reason-counseling'),
    ).toHaveTextContent('Re-routed after a counselor swap')
  })

  it('renders nothing about the timeline when the component is unmounted', () => {
    const { unmount } = render(<StageTimeline currentStage="registered" />)

    expect(screen.getByTestId('stage-timeline')).toBeInTheDocument()

    unmount()

    expect(screen.queryByTestId('stage-timeline')).not.toBeInTheDocument()
  })
})
