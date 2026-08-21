import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import ChecklistView from './ChecklistView'
import type { ChecklistItem } from '../../types/checklist'

const baseItems: ChecklistItem[] = [
  {
    templateId: 10,
    stage: 'registered',
    name: 'Passport',
    description: 'A clear scan of your passport biodata page.',
    required: true,
    orderIndex: 0,
    upload: null,
  },
  {
    templateId: 11,
    stage: 'registered',
    name: 'Transcript',
    description: null,
    required: false,
    orderIndex: 1,
    upload: {
      id: 99,
      status: 'approved',
      originalFilename: 'transcript.pdf',
      uploadedAt: '2026-02-01T10:00:00Z',
      verifiedAt: '2026-02-02T11:00:00Z',
      rejectionReason: null,
    },
  },
  {
    templateId: 12,
    stage: 'document_verification',
    name: 'Statement of Purpose',
    description: 'A 500-word statement explaining your motivation.',
    required: true,
    orderIndex: null,
    upload: {
      id: 100,
      status: 'rejected',
      originalFilename: 'sop.pdf',
      uploadedAt: '2026-02-03T09:00:00Z',
      verifiedAt: '2026-02-03T10:00:00Z',
      rejectionReason: 'Please re-upload with a scanned signature.',
    },
  },
  {
    templateId: 13,
    stage: 'registered',
    name: 'Recommendation letter',
    description: null,
    required: false,
    orderIndex: 2,
    upload: {
      id: 101,
      status: 'pending',
      originalFilename: 'rec.pdf',
      uploadedAt: '2026-02-04T12:00:00Z',
      verifiedAt: null,
      rejectionReason: null,
    },
  },
]

function renderView(props: Partial<React.ComponentProps<typeof ChecklistView>> = {}) {
  const defaultProps: React.ComponentProps<typeof ChecklistView> = {
    applicationId: 1,
    items: baseItems,
    loading: false,
    error: null,
  }
  return render(<ChecklistView {...defaultProps} {...props} />)
}

describe('ChecklistView', () => {
  it('renders a heading keyed off the application id', () => {
    renderView({ applicationId: 42 })

    expect(screen.getByTestId('checklist-view-42')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Document checklist' })).toBeInTheDocument()
  })

  it('shows a loading state when loading is true', () => {
    renderView({ items: [], loading: true })

    expect(screen.getByText('Loading checklist…')).toBeInTheDocument()
    expect(screen.queryByText('No documents required at this stage.')).not.toBeInTheDocument()
  })

  it('shows an error state when error is set', () => {
    renderView({ items: [], loading: false, error: 'Failed to load the document checklist' })

    expect(screen.getByRole('alert')).toHaveTextContent('Failed to load the document checklist')
  })

  it('shows an empty state when there are no items', () => {
    renderView({ items: [], loading: false, error: null })

    expect(screen.getByText('No documents required at this stage.')).toBeInTheDocument()
  })

  it('renders one row per checklist item with the right test ids', () => {
    renderView()

    expect(screen.getByTestId('checklist-item-10')).toBeInTheDocument()
    expect(screen.getByTestId('checklist-item-11')).toBeInTheDocument()
    expect(screen.getByTestId('checklist-item-12')).toBeInTheDocument()
    expect(screen.getByTestId('checklist-item-13')).toBeInTheDocument()
  })

  it('marks required items with a required tag', () => {
    renderView()

    expect(screen.getByTestId('checklist-item-required-10')).toBeInTheDocument()
    expect(screen.getByTestId('checklist-item-required-12')).toBeInTheDocument()
    expect(screen.queryByTestId('checklist-item-required-11')).not.toBeInTheDocument()
    expect(screen.queryByTestId('checklist-item-required-13')).not.toBeInTheDocument()
  })

  it('renders the description only when present', () => {
    renderView()

    expect(screen.getByText('A clear scan of your passport biodata page.')).toBeInTheDocument()
    expect(screen.getByText('A 500-word statement explaining your motivation.')).toBeInTheDocument()
    // Items without descriptions should not have an empty description paragraph.
    expect(screen.queryByTestId('checklist-item-11')).not.toHaveTextContent(/Description/i)
  })

  it('renders "Not uploaded" badge for items without uploads', () => {
    renderView()

    const status = screen.getByTestId('checklist-item-status-10')
    expect(status).toHaveTextContent('Not uploaded')
    expect(status).toHaveAttribute('data-status', 'not-uploaded')
  })

  it('renders the upload status badge for items with uploads', () => {
    renderView()

    expect(screen.getByTestId('checklist-item-status-11')).toHaveTextContent('Approved')
    expect(screen.getByTestId('checklist-item-status-11')).toHaveAttribute('data-status', 'approved')

    expect(screen.getByTestId('checklist-item-status-12')).toHaveTextContent('Rejected')
    expect(screen.getByTestId('checklist-item-status-12')).toHaveAttribute('data-status', 'rejected')

    expect(screen.getByTestId('checklist-item-status-13')).toHaveTextContent('Pending review')
    expect(screen.getByTestId('checklist-item-status-13')).toHaveAttribute('data-status', 'pending')
  })

  it('shows the uploaded filename and timestamp for items with uploads', () => {
    renderView()

    expect(screen.getByText('transcript.pdf')).toBeInTheDocument()
    expect(screen.getByText('sop.pdf')).toBeInTheDocument()
    expect(screen.getByText('rec.pdf')).toBeInTheDocument()
    // All three uploads have a valid ISO date that should render through <time>.
    const timeElements = screen.getAllByText(/2026/)
    expect(timeElements.length).toBeGreaterThanOrEqual(3)
  })

  it('renders the rejection reason when an upload is rejected', () => {
    renderView()

    expect(screen.getByTestId('checklist-item-rejection-12')).toHaveTextContent(
      'Please re-upload with a scanned signature.',
    )
  })

  it('does not render the rejection block for approved uploads', () => {
    renderView()

    expect(screen.queryByTestId('checklist-item-rejection-11')).not.toBeInTheDocument()
  })

  it('renders the reload button when onReload is provided', async () => {
    const user = userEvent.setup()
    const onReload = vi.fn().mockResolvedValue(undefined)

    renderView({ onReload })

    const reloadButton = screen.getByTestId('checklist-reload-1')
    expect(reloadButton).toHaveTextContent('Refresh')

    await user.click(reloadButton)

    expect(onReload).toHaveBeenCalledTimes(1)
  })

  it('disables the reload button while loading', () => {
    renderView({ loading: true, onReload: vi.fn() })

    expect(screen.getByTestId('checklist-reload-1')).toBeDisabled()
    expect(screen.getByTestId('checklist-reload-1')).toHaveTextContent('Refreshing…')
  })

  it('omits the reload button when onReload is not provided', () => {
    renderView({ onReload: undefined })

    expect(screen.queryByTestId('checklist-reload-1')).not.toBeInTheDocument()
  })

  it('renders nothing inside the list when items is empty after loading', () => {
    renderView({ items: [], loading: false, error: null })

    expect(screen.queryByRole('list')).not.toBeInTheDocument()
    expect(screen.queryByTestId('checklist-item-10')).not.toBeInTheDocument()
  })
})