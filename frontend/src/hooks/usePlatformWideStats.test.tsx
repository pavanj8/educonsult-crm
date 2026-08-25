/**
 * Tests for usePlatformWideStats hook (E43; Journey J36).
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { fetchPlatformWideStats } from '../api/analytics'
import { usePlatformWideStats } from '../hooks/usePlatformWideStats'

// Mock the API function
vi.mock('../api/analytics', () => ({
  fetchPlatformWideStats: vi.fn(),
}))

describe('usePlatformWideStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  it('should fetch platform-wide stats on mount', async () => {
    const mockStats = {
      tenants: [
        {
          tenant_id: 1,
          tenant_name: 'Test Consultancy',
          tenant_slug: 'test-consultancy',
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
      ],
      total_tenants: 1,
      total_branches: 3,
      total_staff: 10,
      total_students: 50,
      total_applications: 75,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    const { result } = renderHook(() => usePlatformWideStats())

    expect(result.current.loading).toBe(true)
    expect(result.current.stats).toBe(null)
    expect(result.current.error).toBe(null)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchPlatformWideStats).toHaveBeenCalledWith(undefined)
    expect(result.current.stats).toEqual(mockStats)
    expect(result.current.error).toBe(null)
  })

  it('should fetch stats with date range params', async () => {
    const mockStats = {
      tenants: [],
      total_tenants: 1,
      total_branches: 2,
      total_staff: 5,
      total_students: 25,
      total_applications: 40,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    const dateRange = {
      preset: '7d' as const,
      startDate: '2024-01-01',
      endDate: '2024-01-07',
    }

    const { result } = renderHook(() => usePlatformWideStats(dateRange))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchPlatformWideStats).toHaveBeenCalledWith({
      start_date: '2024-01-01',
      end_date: '2024-01-07',
    })
    expect(result.current.stats).toEqual(mockStats)
  })

  it('should handle API errors gracefully', async () => {
    const mockError = new Error('Failed to fetch')
    vi.mocked(fetchPlatformWideStats).mockRejectedValue(mockError)

    const { result } = renderHook(() => usePlatformWideStats())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.stats).toBe(null)
    expect(result.current.error).toBe('Failed to fetch')
  })

  it('should reload stats when reload function is called', async () => {
    const mockStats = {
      tenants: [],
      total_tenants: 1,
      total_branches: 1,
      total_staff: 3,
      total_students: 15,
      total_applications: 20,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    const { result } = renderHook(() => usePlatformWideStats())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchPlatformWideStats).toHaveBeenCalledTimes(1)

    await result.current.reload()

    expect(fetchPlatformWideStats).toHaveBeenCalledTimes(2)
  })

  it('should handle date range with only start date', async () => {
    const mockStats = {
      tenants: [],
      total_tenants: 1,
      total_branches: 1,
      total_staff: 2,
      total_students: 10,
      total_applications: 15,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    const dateRange = {
      preset: 'custom' as const,
      startDate: '2024-01-01',
      endDate: null,
    }

    const { result } = renderHook(() => usePlatformWideStats(dateRange))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchPlatformWideStats).toHaveBeenCalledWith({
      start_date: '2024-01-01',
      end_date: undefined,
    })
  })

  it('should handle date range with only end date', async () => {
    const mockStats = {
      tenants: [],
      total_tenants: 1,
      total_branches: 1,
      total_staff: 2,
      total_students: 10,
      total_applications: 15,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    const dateRange = {
      preset: 'custom' as const,
      startDate: null,
      endDate: '2024-01-31',
    }

    const { result } = renderHook(() => usePlatformWideStats(dateRange))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchPlatformWideStats).toHaveBeenCalledWith({
      start_date: undefined,
      end_date: '2024-01-31',
    })
  })

  it('should handle undefined dateRange (default case)', async () => {
    const mockStats = {
      tenants: [],
      total_tenants: 2,
      total_branches: 3,
      total_staff: 8,
      total_students: 40,
      total_applications: 60,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    const { result } = renderHook(() => usePlatformWideStats(undefined))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchPlatformWideStats).toHaveBeenCalledWith(undefined)
    expect(result.current.stats).toEqual(mockStats)
  })

  it('should handle explicit undefined dateRange (default case)', async () => {
    const mockStats = {
      tenants: [],
      total_tenants: 2,
      total_branches: 3,
      total_staff: 8,
      total_students: 40,
      total_applications: 60,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    const { result } = renderHook(() => usePlatformWideStats(undefined))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchPlatformWideStats).toHaveBeenCalledWith(undefined)
    expect(result.current.stats).toEqual(mockStats)
  })

  it('should handle dateRange with null dates (default case)', async () => {
    const mockStats = {
      tenants: [],
      total_tenants: 1,
      total_branches: 1,
      total_staff: 2,
      total_students: 10,
      total_applications: 15,
    }

    vi.mocked(fetchPlatformWideStats).mockResolvedValue(mockStats)

    const dateRange = {
      preset: 'custom' as const,
      startDate: null,
      endDate: null,
    }

    const { result } = renderHook(() => usePlatformWideStats(dateRange))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchPlatformWideStats).toHaveBeenCalledWith(undefined)
  })
})
