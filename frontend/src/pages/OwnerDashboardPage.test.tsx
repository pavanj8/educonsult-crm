/**
 * Tests for OwnerDashboardPage component (E42; Journey J35).
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'

import { describe, expect, it, vi } from 'vitest'

import OwnerDashboardPage from './OwnerDashboardPage'

// Mock the hook
vi.mock('./../hooks/useBranchComparison', () => ({
  useBranchComparison: vi.fn(),
}))

import { useBranchComparison } from './../hooks/useBranchComparison'

const mockUseBranchComparison = vi.mocked(useBranchComparison)

describe('OwnerDashboardPage', () => {
  const renderWithRouter = (component: React.ReactElement) => {
    const routes = [
      {
        path: '/owner/dashboard',
        element: component,
      },
    ]

    const router = createMemoryRouter(routes, {
      initialEntries: ['/owner/dashboard'],
    })

    return render(<RouterProvider router={router} />)
  }

  it('should render loading state', () => {
    vi.clearAllMocks()
    mockUseBranchComparison.mockReturnValue({
      branches: [],
      totalBranches: 0,
      totalApplications: 0,
      loading: true,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    renderWithRouter(<OwnerDashboardPage />)

    expect(screen.getByTestId('branch-comparison-loading')).toHaveTextContent(
      'Loading branch comparison data…',
    )
  })

  it('should render error state', () => {
    vi.clearAllMocks()
    mockUseBranchComparison.mockReturnValue({
      branches: [],
      totalBranches: 0,
      totalApplications: 0,
      loading: false,
      error: 'Failed to load branch comparison data',
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    renderWithRouter(<OwnerDashboardPage />)

    expect(screen.getByTestId('branch-comparison-error')).toHaveTextContent(
      'Failed to load branch comparison data',
    )
  })

  it('should render empty state', () => {
    vi.clearAllMocks()
    mockUseBranchComparison.mockReturnValue({
      branches: [],
      totalBranches: 0,
      totalApplications: 0,
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    renderWithRouter(<OwnerDashboardPage />)

    expect(screen.getByTestId('branch-comparison-empty')).toHaveTextContent(
      'No branches found for your consultancy.',
    )
  })

  it('should render branch comparison table with data', () => {
    vi.clearAllMocks()
    mockUseBranchComparison.mockReturnValue({
      branches: [
        {
          branch_id: 1,
          branch_name: 'Downtown',
          branch_city: 'New York',
          total_applications: 100,
          enrolled_count: 20,
          rejected_count: 10,
          withdrawn_count: 5,
          active_count: 65,
        },
        {
          branch_id: 2,
          branch_name: 'Uptown',
          branch_city: 'New York',
          total_applications: 80,
          enrolled_count: 15,
          rejected_count: 8,
          withdrawn_count: 3,
          active_count: 54,
        },
      ],
      totalBranches: 2,
      totalApplications: 180,
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    renderWithRouter(<OwnerDashboardPage />)

    expect(screen.getByTestId('branch-comparison-summary')).toHaveTextContent('2 branches')
    expect(screen.getByTestId('branch-comparison-summary')).toHaveTextContent('180 applications')
    expect(screen.getByTestId('branch-row-1')).toBeInTheDocument()
    expect(screen.getByTestId('branch-row-2')).toBeInTheDocument()
  })

  it('should render date filter inputs', () => {
    vi.clearAllMocks()
    mockUseBranchComparison.mockReturnValue({
      branches: [],
      totalBranches: 0,
      totalApplications: 0,
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    renderWithRouter(<OwnerDashboardPage />)

    expect(screen.getByTestId('start-date-input')).toBeInTheDocument()
    expect(screen.getByTestId('end-date-input')).toBeInTheDocument()
    expect(screen.getByTestId('apply-filter')).toBeInTheDocument()
    expect(screen.getByTestId('clear-filter')).toBeInTheDocument()
  })

  it('should call refetch with date filters on apply', async () => {
    const refetch = vi.fn()
    vi.clearAllMocks()
    mockUseBranchComparison.mockReturnValue({
      branches: [],
      totalBranches: 0,
      totalApplications: 0,
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch,
    })

    const user = userEvent.setup()
    renderWithRouter(<OwnerDashboardPage />)

    const startDateInput = screen.getByTestId('start-date-input')
    const endDateInput = screen.getByTestId('end-date-input')
    const applyButton = screen.getByTestId('apply-filter')

    await user.clear(startDateInput)
    await user.type(startDateInput, '2024-01-01')
    await user.clear(endDateInput)
    await user.type(endDateInput, '2024-12-31')
    await user.click(applyButton)

    await waitFor(() => {
      expect(refetch).toHaveBeenCalledWith(
        expect.objectContaining({
          start_date: expect.any(String),
          end_date: expect.any(String),
        }),
      )
    })
  })

  it('should clear date filters on clear button click', async () => {
    const refetch = vi.fn()
    vi.clearAllMocks()
    mockUseBranchComparison.mockReturnValue({
      branches: [],
      totalBranches: 0,
      totalApplications: 0,
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch,
    })

    const user = userEvent.setup()
    renderWithRouter(<OwnerDashboardPage />)

    const startDateInput = screen.getByTestId('start-date-input')
    const clearButton = screen.getByTestId('clear-filter')

    await user.type(startDateInput, '2024-01-01')
    await user.click(clearButton)

    expect(startDateInput).toHaveValue('')
    await waitFor(() => {
      expect(refetch).toHaveBeenCalledWith(undefined)
    })
  })

  it('should call reload on refresh button click', async () => {
    const reload = vi.fn()
    vi.clearAllMocks()
    mockUseBranchComparison.mockReturnValue({
      branches: [
        {
          branch_id: 1,
          branch_name: 'Downtown',
          branch_city: 'New York',
          total_applications: 100,
          enrolled_count: 20,
          rejected_count: 10,
          withdrawn_count: 5,
          active_count: 65,
        },
      ],
      totalBranches: 1,
      totalApplications: 100,
      loading: false,
      error: null,
      reload,
      refetch: vi.fn(),
    })

    const user = userEvent.setup()
    renderWithRouter(<OwnerDashboardPage />)

    const refreshButton = screen.getByRole('button', { name: 'Refresh' })
    await user.click(refreshButton)

    expect(reload).toHaveBeenCalledOnce()
  })

  it('should disable clear button when no filters are set', () => {
    vi.clearAllMocks()
    mockUseBranchComparison.mockReturnValue({
      branches: [],
      totalBranches: 0,
      totalApplications: 0,
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    renderWithRouter(<OwnerDashboardPage />)

    expect(screen.getByTestId('clear-filter')).toBeDisabled()
  })

  it('should enable clear button when filters are set', async () => {
    vi.clearAllMocks()
    mockUseBranchComparison.mockReturnValue({
      branches: [],
      totalBranches: 0,
      totalApplications: 0,
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    const user = userEvent.setup()
    renderWithRouter(<OwnerDashboardPage />)

    const startDateInput = screen.getByTestId('start-date-input')
    await user.type(startDateInput, '2024-01-01')

    expect(screen.getByTestId('clear-filter')).not.toBeDisabled()
  })
})
