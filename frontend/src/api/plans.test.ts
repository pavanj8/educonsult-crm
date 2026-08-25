/**
 * Tests for plans API client (E45; Journey J38).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { fetchMyPlanAndUsage } from './plans'
import type { PlanAndUsage } from '../types/plan'

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

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      const result = await fetchMyPlanAndUsage()

      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: 'GET',
        })
      )
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

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response)

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

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      const result = await fetchMyPlanAndUsage()

      expect(result.plan?.max_branches).toBeNull()
      expect(result.plan?.max_staff).toBeNull()
      expect(result.plan?.max_students).toBeNull()
    })

    it('should throw error on network failure', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      await expect(fetchMyPlanAndUsage()).rejects.toThrow('Network error')
    })

    it('should throw error on non-OK response', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
      } as Response)

      await expect(fetchMyPlanAndUsage()).rejects.toThrow()
    })
  })
})
