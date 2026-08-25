/**
 * Tests for BillingStatusPage component (E47; Journey J40).
 */

import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import BillingStatusPage from './BillingStatusPage'

// Mock the hook
vi.mock('../hooks/useAllTenantsBillingStatus', () => ({
  useAllTenantsBillingStatus: vi.fn(),
}))

import { useAllTenantsBillingStatus } from '../hooks/useAllTenantsBillingStatus'

describe('BillingStatusPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
  })

  it('should show loading state', () => {
    vi.mocked(useAllTenantsBillingStatus).mockReturnValue({
      tenants: [],
      loading: true,
      error: null,
      reload: vi.fn(),
    })

    render(<BillingStatusPage />)

    expect(screen.getByTestId('billing-status-loading')).toHaveTextContent(
      'Loading tenant billing status…'
    )
  })

  it('should show error state', () => {
    vi.mocked(useAllTenantsBillingStatus).mockReturnValue({
      tenants: [],
      loading: false,
      error: 'Failed to load',
      reload: vi.fn(),
    })

    render(<BillingStatusPage />)

    expect(screen.getByTestId('billing-status-error')).toHaveTextContent('Failed to load')
  })

  it('should show empty state', () => {
    vi.mocked(useAllTenantsBillingStatus).mockReturnValue({
      tenants: [],
      loading: false,
      error: null,
      reload: vi.fn(),
    })

    render(<BillingStatusPage />)

    expect(screen.getByTestId('no-tenants')).toHaveTextContent('No tenants found')
  })

  it('should render tenants table', () => {
    const mockTenants = [
      {
        tenant_id: 1,
        tenant_name: 'Tenant A',
        tenant_slug: 'tenant-a',
        plan: {
          code: 'starter' as const,
          name: 'Starter Plan',
          max_branches: 1,
          max_staff: 5,
          max_students: 50,
          is_active: true,
        },
        branches_used: 1,
        staff_used: 2,
        students_used: 10,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
      {
        tenant_id: 2,
        tenant_name: 'Tenant B',
        tenant_slug: 'tenant-b',
        plan: null,
        branches_used: 0,
        staff_used: 0,
        students_used: 0,
        created_at: '2024-01-02T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      },
    ]

    vi.mocked(useAllTenantsBillingStatus).mockReturnValue({
      tenants: mockTenants,
      loading: false,
      error: null,
      reload: vi.fn(),
    })

    render(<BillingStatusPage />)

    // Check headers
    expect(screen.getByRole('columnheader', { name: 'Tenant' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Plan' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Branches' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Staff' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Students' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Created' })).toBeInTheDocument()

    // Check tenant A row
    expect(screen.getByTestId('tenant-row-1')).toBeInTheDocument()
    expect(screen.getByText('Tenant A')).toBeInTheDocument()
    expect(screen.getByText('tenant-a')).toBeInTheDocument()
    expect(screen.getByTestId('plan-1')).toHaveTextContent('Starter')
    expect(screen.getByTestId('branches-1')).toHaveTextContent('1')
    expect(screen.getByTestId('staff-1')).toHaveTextContent('2')
    expect(screen.getByTestId('students-1')).toHaveTextContent('10')

    // Check tenant B row (no plan)
    expect(screen.getByTestId('tenant-row-2')).toBeInTheDocument()
    expect(screen.getByText('Tenant B')).toBeInTheDocument()
    expect(screen.getByText('tenant-b')).toBeInTheDocument()
    expect(screen.getByTestId('plan-2')).toHaveTextContent('—')
  })

  it('should render reload button', () => {
    const reloadMock = vi.fn()

    vi.mocked(useAllTenantsBillingStatus).mockReturnValue({
      tenants: [],
      loading: false,
      error: null,
      reload: reloadMock,
    })

    render(<BillingStatusPage />)

    const reloadButton = screen.getByTestId('reload-button')
    expect(reloadButton).toBeInTheDocument()

    reloadButton.click()
    expect(reloadMock).toHaveBeenCalled()
  })

  it('should show at-limit class when at limit', () => {
    const mockTenants = [
      {
        tenant_id: 1,
        tenant_name: 'Tenant A',
        tenant_slug: 'tenant-a',
        plan: {
          code: 'starter' as const,
          name: 'Starter Plan',
          max_branches: 1,
          max_staff: 5,
          max_students: 50,
          is_active: true,
        },
        branches_used: 1, // At limit
        staff_used: 2,
        students_used: 10,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ]

    vi.mocked(useAllTenantsBillingStatus).mockReturnValue({
      tenants: mockTenants,
      loading: false,
      error: null,
      reload: vi.fn(),
    })

    render(<BillingStatusPage />)

    const branchesCell = screen.getByTestId('branches-1')
    expect(branchesCell).toHaveClass('at-limit')
  })

  it('should show near-limit class when near limit', () => {
    const mockTenants = [
      {
        tenant_id: 1,
        tenant_name: 'Tenant A',
        tenant_slug: 'tenant-a',
        plan: {
          code: 'starter' as const,
          name: 'Starter Plan',
          max_branches: 10,
          max_staff: 5,
          max_students: 50,
          is_active: true,
        },
        branches_used: 9, // Near limit (80%)
        staff_used: 2,
        students_used: 10,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ]

    vi.mocked(useAllTenantsBillingStatus).mockReturnValue({
      tenants: mockTenants,
      loading: false,
      error: null,
      reload: vi.fn(),
    })

    render(<BillingStatusPage />)

    const branchesCell = screen.getByTestId('branches-1')
    expect(branchesCell).toHaveClass('near-limit')
  })

  it('should show unlimited when plan limit is null', () => {
    const mockTenants = [
      {
        tenant_id: 1,
        tenant_name: 'Tenant A',
        tenant_slug: 'tenant-a',
        plan: {
          code: 'enterprise' as const,
          name: 'Enterprise Plan',
          max_branches: null,
          max_staff: null,
          max_students: null,
          is_active: true,
        },
        branches_used: 100,
        staff_used: 200,
        students_used: 500,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ]

    vi.mocked(useAllTenantsBillingStatus).mockReturnValue({
      tenants: mockTenants,
      loading: false,
      error: null,
      reload: vi.fn(),
    })

    render(<BillingStatusPage />)

    const branchesCell = screen.getByTestId('branches-1')
    expect(branchesCell).toHaveTextContent('100 / ∞')
    expect(branchesCell).not.toHaveClass('at-limit')
    expect(branchesCell).not.toHaveClass('near-limit')
  })
})
