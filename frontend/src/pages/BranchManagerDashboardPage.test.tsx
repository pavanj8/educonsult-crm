/**
 * Tests for BranchManagerDashboardPage (E41; Journey J34).
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BranchManagerDashboardPage from './BranchManagerDashboardPage'

// Mock the analytics hook
const mockData = {
  funnel: [
    { stage: 'registered', count: 100 },
    { stage: 'counseling', count: 80 },
    { stage: 'university_shortlisting', count: 60 },
    { stage: 'application_submitted', count: 50 },
    { stage: 'document_verification', count: 40 },
    { stage: 'offer_letter', count: 30 },
    { stage: 'visa_processing', count: 20 },
    { stage: 'loan_processing', count: 10 },
    { stage: 'enrolled', count: 15 },
    { stage: 'rejected', count: 5 },
    { stage: 'withdrawn', count: 3 },
  ],
  total_applications: 413,
}

const mockReload = vi.fn()

const mockUseAnalytics = vi.fn(() => ({
  data: mockData,
  loading: false,
  error: null,
  reload: mockReload,
}))

vi.mock('../hooks/useAnalytics', () => ({
  useAnalytics: () => mockUseAnalytics(),
}))

describe('BranchManagerDashboardPage', () => {
  beforeEach(() => {
    mockReload.mockClear()
    mockUseAnalytics.mockReturnValue({
      data: mockData,
      loading: false,
      error: null,
      reload: mockReload,
    })
  })

  it('renders dashboard heading', () => {
    render(<BranchManagerDashboardPage />)

    expect(
      screen.getByRole('heading', { name: 'Branch Analytics Dashboard' }),
    ).toBeInTheDocument()
  })

  it('renders date range preset selector', () => {
    render(<BranchManagerDashboardPage />)

    const select = screen.getByTestId('preset-select')
    expect(select).toBeInTheDocument()

    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(4)
    expect(options[0]).toHaveTextContent('Last 7 days')
    expect(options[1]).toHaveTextContent('Last 15 days')
    expect(options[2]).toHaveTextContent('Last 30 days')
    expect(options[3]).toHaveTextContent('Custom range')
  })

  it('shows default 15-day date range', () => {
    render(<BranchManagerDashboardPage />)

    const display = screen.getByTestId('date-range-display')
    expect(display).toBeInTheDocument()
    // Should show a date range (will be relative to "now", so we just check it exists)
    expect(display.textContent).toContain('Showing data from')
  })

  it('shows custom date inputs when custom preset is selected', async () => {
    const user = userEvent.setup()
    render(<BranchManagerDashboardPage />)

    const select = screen.getByTestId('preset-select')
    await user.selectOptions(select, 'custom')

    expect(screen.getByTestId('custom-date-range')).toBeInTheDocument()
    expect(screen.getByTestId('start-date-input')).toBeInTheDocument()
    expect(screen.getByTestId('end-date-input')).toBeInTheDocument()
  })

  it('renders summary statistics cards', () => {
    render(<BranchManagerDashboardPage />)

    expect(screen.getByTestId('total-applications-card')).toBeInTheDocument()
    expect(screen.getByTestId('enrolled-applications-card')).toBeInTheDocument()
    expect(screen.getByTestId('conversion-rate-card')).toBeInTheDocument()

    expect(screen.getByTestId('total-applications-value')).toHaveTextContent('413')
    expect(screen.getByTestId('enrolled-value')).toHaveTextContent('15')
    expect(screen.getByTestId('conversion-rate-value')).toHaveTextContent('3.6%')
  })

  it('renders conversion funnel chart heading', () => {
    render(<BranchManagerDashboardPage />)

    expect(
      screen.getByRole('heading', { name: 'Conversion Funnel by Stage' }),
    ).toBeInTheDocument()
  })

  it('renders funnel chart table', () => {
    render(<BranchManagerDashboardPage />)

    const chart = screen.getByTestId('funnel-chart')
    expect(chart).toBeInTheDocument()

    // Check a few stage rows
    expect(screen.getByTestId('funnel-row-registered')).toBeInTheDocument()
    expect(screen.getByTestId('funnel-row-counseling')).toBeInTheDocument()
    expect(screen.getByTestId('funnel-row-enrolled')).toBeInTheDocument()
  })

  it('displays stage labels correctly', () => {
    render(<BranchManagerDashboardPage />)

    const chart = screen.getByTestId('funnel-chart')

    expect(chart).toHaveTextContent('Registered')
    expect(chart).toHaveTextContent('Counseling')
    expect(chart).toHaveTextContent('Enrolled')
    expect(chart).toHaveTextContent('Rejected')
  })

  it('displays correct counts for each stage', () => {
    render(<BranchManagerDashboardPage />)

    const registeredRow = screen.getByTestId('funnel-row-registered')
    expect(registeredRow).toHaveTextContent('100')

    const enrolledRow = screen.getByTestId('funnel-row-enrolled')
    expect(enrolledRow).toHaveTextContent('15')
  })

  it('calls reload when refresh button is clicked', async () => {
    const user = userEvent.setup()
    render(<BranchManagerDashboardPage />)

    const refreshButton = screen.getByRole('button', { name: 'Refresh' })
    await user.click(refreshButton)

    expect(mockReload).toHaveBeenCalledTimes(1)
  })

  it('shows loading state', () => {
    mockUseAnalytics.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      reload: mockReload,
    } as unknown as ReturnType<typeof mockUseAnalytics>)

    render(<BranchManagerDashboardPage />)

    expect(screen.getByTestId('analytics-loading')).toHaveTextContent(
      'Loading analytics data…',
    )
  })

  it('shows error state', () => {
    mockUseAnalytics.mockReturnValue({
      data: null,
      loading: false,
      error: 'Failed to load',
      reload: mockReload,
    } as unknown as ReturnType<typeof mockUseAnalytics>)

    render(<BranchManagerDashboardPage />)

    expect(screen.getByTestId('analytics-error')).toHaveTextContent(
      'Failed to load',
    )
  })

  it('converts to custom date range and back', async () => {
    const user = userEvent.setup()
    render(<BranchManagerDashboardPage />)

    // Start with 15d preset
    let select = screen.getByTestId('preset-select')
    expect(select).toHaveValue('15d')

    // Switch to custom
    await user.selectOptions(select, 'custom')
    expect(screen.getByTestId('custom-date-range')).toBeInTheDocument()

    // Switch back to preset
    select = screen.getByTestId('preset-select')
    await user.selectOptions(select, '7d')
    expect(screen.queryByTestId('custom-date-range')).not.toBeInTheDocument()
  })
})
