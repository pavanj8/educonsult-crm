/**
 * Tests for usePlanAndUsage hook (E45; Journey J38).
 */

import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { usePlanAndUsage } from './usePlanAndUsage'
import { fetchMyPlanAndUsage } from '../api/plans'
import type { PlanAndUsage } from '../types/plan'

// Mock the API module
vi.mock('../api/plans')

describe('usePlanAndUsage hook', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should load plan and usage data on mount', async () => {
    const mockData: PlanAndUsage = {
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
    }

    vi.mocked(fetchMyPlanAndUsage).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => usePlanAndUsage())

    expect(result.current.loading).toBe(true)
    expect(result.current.planAndUsage).toBeNull()
    expect(result.current.error).toBeNull()

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.planAndUsage).toEqual(mockData)
    expect(result.current.error).toBeNull()
  })

  it('should handle API error', async () => {
    const errorMessage = 'Failed to load plan data'
    vi.mocked(fetchMyPlanAndUsage).mockRejectedValueOnce(new Error(errorMessage))

    const { result } = renderHook(() => usePlanAndUsage())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.planAndUsage).toBeNull()
    expect(result.current.error).toBe(errorMessage)
  })

  it('should handle null plan (no plan assigned yet)', async () => {
    const mockData: PlanAndUsage = {
      plan: null,
      usage: {
        branches: 0,
        staff: 0,
        students: 0,
      },
    }

    vi.mocked(fetchMyPlanAndUsage).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => usePlanAndUsage())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.planAndUsage?.plan).toBeNull()
    expect(result.current.planAndUsage?.usage).toEqual({
      branches: 0,
      staff: 0,
      students: 0,
    })
  })

  it('should reload data when reload is called', async () => {
    const mockData1: PlanAndUsage = {
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
    }

    const mockData2: PlanAndUsage = {
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
    }

    vi.mocked(fetchMyPlanAndUsage)
      .mockResolvedValueOnce(mockData1)
      .mockResolvedValueOnce(mockData2)

    const { result } = renderHook(() => usePlanAndUsage())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.planAndUsage).toEqual(mockData1)

    await act(async () => {
      await result.current.reload()
    })

    expect(result.current.planAndUsage).toEqual(mockData2)
  })

  it('should refetch data when refetch is called', async () => {
    const mockData: PlanAndUsage = {
      plan: {
        id: 1,
        code: 'enterprise',
        name: 'Enterprise',
        max_branches: null,
        max_staff: null,
        max_students: null,
        is_active: true,
      },
      usage: {
        branches: 10,
        staff: 100,
        students: 1000,
      },
    }

    vi.mocked(fetchMyPlanAndUsage).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => usePlanAndUsage())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.planAndUsage).toEqual(mockData)
  })
})
