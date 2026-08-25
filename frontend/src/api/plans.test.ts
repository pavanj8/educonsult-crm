/**
 * Tests for plans API client (E45; Journey J38).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { fetchMyPlanAndUsage } from './plans'
import { apiFetch } from './client'
import type { PlanAndUsage } from '../types/plan'

// Mock the HTTP client
vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

describe('plans API client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('fetchMyPlanAndUsage', () => {
    it('should fetch plan and usage data successfully', async () => {
      const mockResponse: PlanAndUsage = {
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
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchMyPlanAndUsage()

      expect(apiFetch).toHaveBeenCalledWith('/me/plan-usage')
      expect(result).toEqual(mockResponse)
    })

    it('should handle null plan (no plan assigned)', async () => {
      const mockResponse: PlanAndUsage = {
        plan: null,
        usage: {
          branches: 2,
          staff: 5,
          students: 30,
        },
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchMyPlanAndUsage()

      expect(result.plan).toBeNull()
      expect(result.usage).toEqual({
        branches: 2,
        staff: 5,
        students: 30,
      })
    })

    it('should handle enterprise unlimited limits (null values)', async () => {
      const mockResponse: PlanAndUsage = {
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
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchMyPlanAndUsage()

      expect(result.plan?.max_branches).toBeNull()
      expect(result.plan?.max_staff).toBeNull()
      expect(result.plan?.max_students).toBeNull()
    })

    it('should throw error on network failure', async () => {
      vi.mocked(apiFetch).mockRejectedValue(new Error('Network error'))

      await expect(fetchMyPlanAndUsage()).rejects.toThrow('Network error')
    })

    it('should throw error on non-OK response', async () => {
      const mockError = new Error('Forbidden') as Error & { status: number }
      mockError.status = 403

      vi.mocked(apiFetch).mockRejectedValue(mockError)

      await expect(fetchMyPlanAndUsage()).rejects.toThrow('Forbidden')
    })
  })
})
