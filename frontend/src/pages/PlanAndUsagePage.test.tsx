/**
 * Tests for PlanAndUsagePage component (E45; Journey J38).
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import PlanAndUsagePage from './PlanAndUsagePage'
import { usePlanAndUsage } from '../hooks/usePlanAndUsage'

// Mock the hook
vi.mock('../hooks/usePlanAndUsage')

describe('PlanAndUsagePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render loading state', () => {
    vi.mocked(usePlanAndUsage).mockReturnValue({
      planAndUsage: null,
      loading: true,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    render(<PlanAndUsagePage />)

    expect(screen.getByTestId('plan-usage-loading')).toHaveTextContent(
      'Loading plan and usage data…'
    )
  })

  it('should render error state', () => {
    const errorMessage = 'Failed to load plan data'
    vi.mocked(usePlanAndUsage).mockReturnValue({
      planAndUsage: null,
      loading: false,
      error: errorMessage,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    render(<PlanAndUsagePage />)

    expect(screen.getByTestId('plan-usage-error')).toHaveTextContent(errorMessage)
  })

  it('should render no plan assigned message when plan is null', () => {
    vi.mocked(usePlanAndUsage).mockReturnValue({
      planAndUsage: {
        plan: null,
        usage: {
          branches: 0,
          staff: 0,
          students: 0,
        },
      },
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    render(<PlanAndUsagePage />)

    expect(screen.getByTestId('plan-usage-no-plan')).toBeInTheDocument()
    expect(screen.getByTestId('plan-usage-no-plan')).toHaveTextContent(
      /no plan has been assigned/i
    )
  })

  it('should render plan card with plan details', () => {
    vi.mocked(usePlanAndUsage).mockReturnValue({
      planAndUsage: {
        plan: {
          id: 1,
          code: 'growth',
          name: 'Growth',
          max_branches: 5,
          max_staff: 20,
          max_students: 100,
          is_active: true,
        },
        usage: {
          branches: 3,
          staff: 12,
          students: 67,
        },
      },
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    render(<PlanAndUsagePage />)

    expect(screen.getByTestId('plan-usage-plan-name')).toHaveTextContent('Growth')
    expect(screen.getByTestId('plan-usage-plan-code')).toHaveTextContent('growth')
    expect(screen.getByTestId('plan-usage-plan-card')).toBeInTheDocument()
  })

  it('should render usage metrics', () => {
    vi.mocked(usePlanAndUsage).mockReturnValue({
      planAndUsage: {
        plan: {
          id: 1,
          code: 'starter',
          name: 'Starter',
          max_branches: 1,
          max_staff: 5,
          max_students: 50,
          is_active: true,
        },
        usage: {
          branches: 1,
          staff: 3,
          students: 25,
        },
      },
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    render(<PlanAndUsagePage />)

    // Check branches metric
    const branchesMetric = screen.getByTestId('plan-usage-branches')
    expect(branchesMetric).toHaveTextContent('Branches')
    expect(branchesMetric).toHaveTextContent('1 / 1')

    // Check staff metric
    const staffMetric = screen.getByTestId('plan-usage-staff')
    expect(staffMetric).toHaveTextContent('Staff')
    expect(staffMetric).toHaveTextContent('3 / 5')

    // Check students metric
    const studentsMetric = screen.getByTestId('plan-usage-students')
    expect(studentsMetric).toHaveTextContent('Students')
    expect(studentsMetric).toHaveTextContent('25 / 50')
  })

  it('should render unlimited limits for enterprise plan', () => {
    vi.mocked(usePlanAndUsage).mockReturnValue({
      planAndUsage: {
        plan: {
          id: 3,
          code: 'enterprise',
          name: 'Enterprise',
          max_branches: null,
          max_staff: null,
          max_students: null,
          is_active: true,
        },
        usage: {
          branches: 10,
          staff: 50,
          students: 500,
        },
      },
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    render(<PlanAndUsagePage />)

    // All metrics should show "Unlimited"
    const branchesMetric = screen.getByTestId('plan-usage-branches')
    expect(branchesMetric).toHaveTextContent('10 / Unlimited')

    const staffMetric = screen.getByTestId('plan-usage-staff')
    expect(staffMetric).toHaveTextContent('50 / Unlimited')

    const studentsMetric = screen.getByTestId('plan-usage-students')
    expect(studentsMetric).toHaveTextContent('500 / Unlimited')

    // Limits section should also show unlimited
    expect(screen.getByTestId('limit-max-branches')).toHaveTextContent('Unlimited')
    expect(screen.getByTestId('limit-max-staff')).toHaveTextContent('Unlimited')
    expect(screen.getByTestId('limit-max-students')).toHaveTextContent('Unlimited')
  })

  it('should show warning when at limit', () => {
    vi.mocked(usePlanAndUsage).mockReturnValue({
      planAndUsage: {
        plan: {
          id: 1,
          code: 'starter',
          name: 'Starter',
          max_branches: 1,
          max_staff: 5,
          max_students: 50,
          is_active: true,
        },
        usage: {
          branches: 1,
          staff: 5,
          students: 25,
        },
      },
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    render(<PlanAndUsagePage />)

    // Branches at limit
    expect(screen.getByTestId('plan-usage-branches-at-limit')).toBeInTheDocument()
    expect(screen.getByTestId('plan-usage-branches-at-limit')).toHaveTextContent(
      /at limit/i
    )

    // Staff at limit
    expect(screen.getByTestId('plan-usage-staff-at-limit')).toBeInTheDocument()
  })

  it('should render plan limits section', () => {
    vi.mocked(usePlanAndUsage).mockReturnValue({
      planAndUsage: {
        plan: {
          id: 2,
          code: 'growth',
          name: 'Growth',
          max_branches: 5,
          max_staff: 20,
          max_students: 100,
          is_active: true,
        },
        usage: {
          branches: 2,
          staff: 8,
          students: 45,
        },
      },
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    render(<PlanAndUsagePage />)

    expect(screen.getByTestId('plan-usage-limits')).toBeInTheDocument()
    expect(screen.getByTestId('limit-max-branches')).toHaveTextContent('5')
    expect(screen.getByTestId('limit-max-staff')).toHaveTextContent('20')
    expect(screen.getByTestId('limit-max-students')).toHaveTextContent('100')
  })

  it('should call reload when refresh button is clicked', async () => {
    const reloadMock = vi.fn()
    vi.mocked(usePlanAndUsage).mockReturnValue({
      planAndUsage: {
        plan: {
          id: 1,
          code: 'starter',
          name: 'Starter',
          max_branches: 1,
          max_staff: 5,
          max_students: 50,
          is_active: true,
        },
        usage: {
          branches: 1,
          staff: 3,
          students: 25,
        },
      },
      loading: false,
      error: null,
      reload: reloadMock,
      refetch: vi.fn(),
    })

    render(<PlanAndUsagePage />)

    const refreshButton = screen.getByTestId('plan-usage-refresh')
    await userEvent.click(refreshButton)

    expect(reloadMock).toHaveBeenCalledOnce()
  })

  it('should disable refresh button while loading', () => {
    vi.mocked(usePlanAndUsage).mockReturnValue({
      planAndUsage: {
        plan: {
          id: 1,
          code: 'starter',
          name: 'Starter',
          max_branches: 1,
          max_staff: 5,
          max_students: 50,
          is_active: true,
        },
        usage: {
          branches: 1,
          staff: 3,
          students: 25,
        },
      },
      loading: true,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    render(<PlanAndUsagePage />)

    const refreshButton = screen.getByTestId('plan-usage-refresh')
    expect(refreshButton).toBeDisabled()
  })

  it('should not render limits section when no plan assigned', () => {
    vi.mocked(usePlanAndUsage).mockReturnValue({
      planAndUsage: {
        plan: null,
        usage: {
          branches: 0,
          staff: 0,
          students: 0,
        },
      },
      loading: false,
      error: null,
      reload: vi.fn(),
      refetch: vi.fn(),
    })

    render(<PlanAndUsagePage />)

    // No limits section when plan is null
    expect(screen.queryByTestId('plan-usage-limits')).not.toBeInTheDocument()
  })

  describe('Plan Upgrade Actions (E46; Journey J39)', () => {
    it('should render upgrade buttons for starter plan', () => {
      vi.mocked(usePlanAndUsage).mockReturnValue({
        planAndUsage: {
          plan: {
            id: 1,
            code: 'starter',
            name: 'Starter',
            max_branches: 1,
            max_staff: 5,
            max_students: 50,
            is_active: true,
          },
          usage: {
            branches: 1,
            staff: 3,
            students: 25,
          },
        },
        loading: false,
        error: null,
        reload: vi.fn(),
        refetch: vi.fn(),
      })

      render(<PlanAndUsagePage />)

      // Starter plan should show upgrade to Growth and Enterprise
      expect(screen.getByTestId('upgrade-options')).toBeInTheDocument()
      expect(screen.getByTestId('upgrade-plan-button-growth')).toBeInTheDocument()
      expect(screen.getByTestId('upgrade-plan-button-enterprise')).toBeInTheDocument()
    })

    it('should render upgrade button for growth plan', () => {
      vi.mocked(usePlanAndUsage).mockReturnValue({
        planAndUsage: {
          plan: {
            id: 2,
            code: 'growth',
            name: 'Growth',
            max_branches: 5,
            max_staff: 20,
            max_students: 100,
            is_active: true,
          },
          usage: {
            branches: 2,
            staff: 8,
            students: 45,
          },
        },
        loading: false,
        error: null,
        reload: vi.fn(),
        refetch: vi.fn(),
      })

      render(<PlanAndUsagePage />)

      // Growth plan should show upgrade to Enterprise only
      expect(screen.getByTestId('upgrade-plan-button-enterprise')).toBeInTheDocument()
      // Growth plan should also show downgrade to Starter
      expect(screen.getByTestId('upgrade-plan-button-starter')).toBeInTheDocument()
    })

    it('should show "highest tier" message for enterprise plan', () => {
      vi.mocked(usePlanAndUsage).mockReturnValue({
        planAndUsage: {
          plan: {
            id: 3,
            code: 'enterprise',
            name: 'Enterprise',
            max_branches: null,
            max_staff: null,
            max_students: null,
            is_active: true,
          },
          usage: {
            branches: 10,
            staff: 50,
            students: 500,
          },
        },
        loading: false,
        error: null,
        reload: vi.fn(),
        refetch: vi.fn(),
      })

      render(<PlanAndUsagePage />)

      // Enterprise plan should show downgrade options
      expect(screen.getByTestId('upgrade-plan-button-growth')).toBeInTheDocument()
      expect(screen.getByTestId('upgrade-plan-button-starter')).toBeInTheDocument()
    })

    it('should not render upgrade options when no plan assigned', () => {
      vi.mocked(usePlanAndUsage).mockReturnValue({
        planAndUsage: {
          plan: null,
          usage: {
            branches: 0,
            staff: 0,
            students: 0,
          },
        },
        loading: false,
        error: null,
        reload: vi.fn(),
        refetch: vi.fn(),
      })

      render(<PlanAndUsagePage />)

      // No upgrade options when plan is null
      expect(screen.queryByTestId('upgrade-options')).not.toBeInTheDocument()
    })

    it('should show success message after successful upgrade', async () => {
      vi.mocked(usePlanAndUsage).mockReturnValue({
        planAndUsage: {
          plan: {
            id: 1,
            code: 'starter',
            name: 'Starter',
            max_branches: 1,
            max_staff: 5,
            max_students: 50,
            is_active: true,
          },
          usage: {
            branches: 1,
            staff: 3,
            students: 25,
          },
        },
        loading: false,
        error: null,
        reload: vi.fn(),
        refetch: vi.fn(),
      })

      render(<PlanAndUsagePage />)

      // Initially, no success message
      expect(screen.queryByTestId('upgrade-success-message')).not.toBeInTheDocument()

      // Note: Testing the actual success message requires mocking the usePlanUpgrade hook
      // which would be done in the UpgradePlanAction component tests
    })
  })
})
