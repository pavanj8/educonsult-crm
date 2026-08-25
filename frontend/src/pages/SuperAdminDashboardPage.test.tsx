/**
 * Tests for SuperAdminDashboardPage (E43; Journey J36).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import SuperAdminDashboardPage from '../pages/SuperAdminDashboardPage'
import { fetchPlatformWideStats } from '../api/analytics'

// Mock the API
vi.mock('../api/analytics', () => ({
  fetchPlatformWideStats: vi.fn(),
  getAnalyticsExportUrl: vi.fn((type: string, format: string) => {
    if (type === 'platform-stats') {
      return format === 'xlsx' ? '/analytics/export/platform-stats?format=xlsx' : '/analytics/export/platform-stats?format=csv'
    }
    return '/analytics/export/unknown?format=csv'
  }),
}))

// Mock ExportButton to simplify testing
vi.mock('../components/analytics/ExportButton', () => ({
  ExportButton: ({ label, className, 'data-testid': testId }: { label: string; className?: string; 'data-testid'?: string }) => (
    <button type="button" className={className} data-testid={testId}>
      {label}
    </button>
  ),
}))

// Mock the auth store to simulate super admin role
vi.mock('../store/authStore', () => ({
  useAuthStore: () => ({
    user: {
      id: 1,
      email: 'superadmin@educonsult.com',
      role: 'SUPER_ADMIN',
      tenant_id: null,
      branch_id: null,
    },
  }),
}))

function renderWithRouter() {
  render(
    <MemoryRouter>
      <SuperAdminDashboardPage />
    </MemoryRouter>
  )
}

describe('SuperAdminDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  it('should render loading state initially', () => {
    vi.mocked(fetchPlatformWideStats).mockImplementation(
      () => new Promise(() => {}),
    )

    renderWithRouter()

    expect(screen.getByTestId('analytics-loading')).toHaveTextContent(
      'Loading platform stats…',
    )
  })

  it('should render platform stats when data loads', async () => {
    const mockStats = {
      tenants: [
        {
          tenant_id: 1,
          tenant_name: 'Test Consultancy A',
          tenant_slug: 'test-consultancy-a',
          plan_code: 'growth',
          branches_count: 3,
          staff_count: 10,
          students_count: 50,
          applications_count: 75,
          enrolled_count: 20,
          rejected_count: 5,
          withdrawn_count: 3,
          active_count: 47,
        },
        {
          tenant_id: 2,
          tenant_name: 'Test Consultancy B',
          tenant_slug: 'test-consultancy-b',
          plan_code: 'starter',
          branches_count: 1,
          staff_count: 3,
          students_count: 20,
          applications_count: 30,
          enrolled_count: 8,
          rejected_count: 2,
          withdrawn_count: 1,
          active_count: 19,
        },
      ],
      total_tenants: 2,
      total_branches: 4,
      total_staff: 13,
      total_students: 70,
      total_applications: 105,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.queryByTestId('analytics-loading')).not.toBeInTheDocument()
    })

    // Check summary cards
    expect(screen.getByTestId('total-tenants-value')).toHaveTextContent('2')
    expect(screen.getByTestId('total-branches-value')).toHaveTextContent('4')
    expect(screen.getByTestId('total-staff-value')).toHaveTextContent('13')
    expect(screen.getByTestId('total-students-value')).toHaveTextContent('70')
    expect(screen.getByTestId('total-applications-value')).toHaveTextContent('105')

    // Check tenant table
    expect(screen.getByTestId('tenant-table')).toBeInTheDocument()
    expect(screen.getByTestId('tenant-row-1')).toBeInTheDocument()
    expect(screen.getByTestId('tenant-row-2')).toBeInTheDocument()

    // Check tenant A details
    expect(screen.getByTestId('branches-1')).toHaveTextContent('3')
    expect(screen.getByTestId('staff-1')).toHaveTextContent('10')
    expect(screen.getByTestId('students-1')).toHaveTextContent('50')
    expect(screen.getByTestId('applications-1')).toHaveTextContent('75')
    expect(screen.getByTestId('enrolled-1')).toHaveTextContent('20')
    expect(screen.getByTestId('active-1')).toHaveTextContent('47')

    // Check tenant B details
    expect(screen.getByTestId('branches-2')).toHaveTextContent('1')
    expect(screen.getByTestId('applications-2')).toHaveTextContent('30')
  })

  it('should render error state on API failure', async () => {
    const mockError = new Error('API error')
    vi.mocked(fetchPlatformWideStats).mockRejectedValue(mockError)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.queryByTestId('analytics-loading')).not.toBeInTheDocument()
    })

    expect(screen.getByTestId('analytics-error')).toHaveTextContent('API error')
  })

  it('should handle empty tenant list', async () => {
    const mockStats = {
      tenants: [],
      total_tenants: 0,
      total_branches: 0,
      total_staff: 0,
      total_students: 0,
      total_applications: 0,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.queryByTestId('analytics-loading')).not.toBeInTheDocument()
    })

    expect(screen.getByTestId('no-tenants')).toHaveTextContent('No tenants found')
  })

  it('should show plan code badge when tenant has a plan', async () => {
    const mockStats = {
      tenants: [
        {
          tenant_id: 1,
          tenant_name: 'Enterprise Consultancy',
          tenant_slug: 'enterprise-consultancy',
          plan_code: 'enterprise',
          branches_count: 5,
          staff_count: 25,
          students_count: 200,
          applications_count: 350,
          enrolled_count: 100,
          rejected_count: 20,
          withdrawn_count: 10,
          active_count: 220,
        },
      ],
      total_tenants: 1,
      total_branches: 5,
      total_staff: 25,
      total_students: 200,
      total_applications: 350,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.queryByTestId('analytics-loading')).not.toBeInTheDocument()
    })

    expect(screen.getByTestId('plan-1')).toHaveTextContent('enterprise')
  })

  it('should show dash when tenant has no plan', async () => {
    const mockStats = {
      tenants: [
        {
          tenant_id: 1,
          tenant_name: 'New Consultancy',
          tenant_slug: 'new-consultancy',
          plan_code: null,
          branches_count: 1,
          staff_count: 2,
          students_count: 5,
          applications_count: 8,
          enrolled_count: 2,
          rejected_count: 1,
          withdrawn_count: 0,
          active_count: 5,
        },
      ],
      total_tenants: 1,
      total_branches: 1,
      total_staff: 2,
      total_students: 5,
      total_applications: 8,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.queryByTestId('analytics-loading')).not.toBeInTheDocument()
    })

    const planCell = screen.getByTestId('tenant-row-1').querySelector('.plan-cell')
    expect(planCell?.textContent).toBe('—')
  })

  it('should allow date range preset selection', async () => {
    const user = userEvent.setup()
    const mockStats = {
      tenants: [],
      total_tenants: 1,
      total_branches: 1,
      total_staff: 3,
      total_students: 15,
      total_applications: 20,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.queryByTestId('analytics-loading')).not.toBeInTheDocument()
    })

    const presetSelect = screen.getByTestId('preset-select')
    expect(presetSelect).toHaveValue('15d')

    await user.selectOptions(presetSelect, '7d')
    expect(presetSelect).toHaveValue('7d')
  })

  it('should show custom date range inputs when custom preset is selected', async () => {
    const user = userEvent.setup()
    const mockStats = {
      tenants: [],
      total_tenants: 1,
      total_branches: 1,
      total_staff: 3,
      total_students: 15,
      total_applications: 20,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.queryByTestId('analytics-loading')).not.toBeInTheDocument()
    })

    const presetSelect = screen.getByTestId('preset-select')

    await user.selectOptions(presetSelect, 'custom')

    expect(screen.getByTestId('custom-date-range')).toBeInTheDocument()
    expect(screen.getByTestId('start-date-input')).toBeInTheDocument()
    expect(screen.getByTestId('end-date-input')).toBeInTheDocument()
  })

  it('should reload data when refresh button is clicked', async () => {
    const user = userEvent.setup()
    const mockStats = {
      tenants: [],
      total_tenants: 1,
      total_branches: 1,
      total_staff: 3,
      total_students: 15,
      total_applications: 20,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.queryByTestId('analytics-loading')).not.toBeInTheDocument()
    })

    // Store initial call count (may be 1 or 2 due to React 18 StrictMode)
    const initialCallCount = vi.mocked(fetchPlatformWideStats).mock.calls.length
    expect(initialCallCount).toBeGreaterThanOrEqual(1)

    const refreshButton = screen.getByTestId('reload-button')
    await user.click(refreshButton)

    // Should have at least one more call after reload
    expect(vi.mocked(fetchPlatformWideStats).mock.calls.length).toBeGreaterThanOrEqual(
      initialCallCount + 1,
    )
  })

  it('should display correct date range text for preset', async () => {
    const mockStats = {
      tenants: [],
      total_tenants: 1,
      total_branches: 1,
      total_staff: 3,
      total_students: 15,
      total_applications: 20,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.queryByTestId('analytics-loading')).not.toBeInTheDocument()
    })

    const display = screen.getByTestId('date-range-display')
    // The display shows actual dates when a preset is selected
    expect(display.textContent).toMatch(/Showing data from/)
    expect(display.textContent).toMatch(/to/)
  })

  it('renders export buttons for platform stats (CSV and Excel)', async () => {
    const mockStats = {
      tenants: [],
      total_tenants: 1,
      total_branches: 1,
      total_staff: 3,
      total_students: 15,
      total_applications: 20,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.queryByTestId('analytics-loading')).not.toBeInTheDocument()
    })

    expect(screen.getByTestId('export-platform-stats-csv')).toBeInTheDocument()
    expect(screen.getByTestId('export-platform-stats-csv')).toHaveTextContent('Export Stats (CSV)')
    expect(screen.getByTestId('export-platform-stats-xlsx')).toBeInTheDocument()
    expect(screen.getByTestId('export-platform-stats-xlsx')).toHaveTextContent('Export Stats (Excel)')
  })
})
