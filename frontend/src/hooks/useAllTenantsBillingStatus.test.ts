/**
 * Tests for useAllTenantsBillingStatus hook (E47; Journey J40).
 */

import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { useAllTenantsBillingStatus } from './useAllTenantsBillingStatus'
import { fetchAllTenantsBillingStatus } from '../api/plans'

// Mock the API module
vi.mock('../api/plans')

describe('useAllTenantsBillingStatus hook', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should load tenant billing status on mount', async () => {
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

    vi.mocked(fetchAllTenantsBillingStatus).mockResolvedValueOnce(mockTenants)

    const { result } = renderHook(() => useAllTenantsBillingStatus())

    expect(result.current.loading).toBe(true)
    expect(result.current.tenants).toEqual([])
    expect(result.current.error).toBeNull()

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.tenants).toEqual(mockTenants)
    expect(result.current.error).toBeNull()
  })

  it('should handle API error', async () => {
    const errorMessage = 'Failed to load tenant billing status'
    vi.mocked(fetchAllTenantsBillingStatus).mockRejectedValueOnce(new Error(errorMessage))

    const { result } = renderHook(() => useAllTenantsBillingStatus())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.tenants).toEqual([])
    expect(result.current.error).toBe(errorMessage)
  })

  it('should reload data when reload is called', async () => {
    const mockTenants1 = [
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
    ]

    const mockTenants2 = [
      {
        tenant_id: 1,
        tenant_name: 'Tenant A',
        tenant_slug: 'tenant-a',
        plan: {
          code: 'growth' as const,
          name: 'Growth Plan',
          max_branches: 5,
          max_staff: 20,
          max_students: 100,
          is_active: true,
        },
        branches_used: 2,
        staff_used: 5,
        students_used: 20,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ]

    vi.mocked(fetchAllTenantsBillingStatus)
      .mockResolvedValueOnce(mockTenants1)
      .mockResolvedValueOnce(mockTenants2)

    const { result } = renderHook(() => useAllTenantsBillingStatus())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.tenants).toEqual(mockTenants1)

    await act(async () => {
      await result.current.reload()
    })

    expect(result.current.tenants).toEqual(mockTenants2)
  })

  it('should handle empty tenant list', async () => {
    vi.mocked(fetchAllTenantsBillingStatus).mockResolvedValueOnce([])

    const { result } = renderHook(() => useAllTenantsBillingStatus())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.tenants).toEqual([])
    expect(result.current.error).toBeNull()
  })
})
