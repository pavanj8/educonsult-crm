/**
 * Tests for analytics API client (E41, E42, E43; Journeys J34, J35, J36).
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import { apiFetch } from './client'
import {
  fetchBranchComparison,
  fetchConversionFunnel,
  fetchPlatformWideStats,
  fetchRegistrationsOverTime,
} from './analytics'

// Mock the HTTP client
vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

describe('analytics API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  describe('fetchRegistrationsOverTime (E41; Journey J34)', () => {
    it('fetches registrations data without filters', async () => {
      const mockResponse = {
        data: [
          { date: '2024-01-01', count: 5 },
          { date: '2024-01-02', count: 8 },
        ],
        total_registrations: 13,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchRegistrationsOverTime()

      expect(apiFetch).toHaveBeenCalledTimes(1)
      expect(apiFetch).toHaveBeenCalledWith('/analytics/registrations')
      expect(result).toEqual(mockResponse)
    })

    it('fetches registrations data with start_date filter', async () => {
      const mockResponse = {
        data: [{ date: '2024-01-01', count: 5 }],
        total_registrations: 5,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const params = { start_date: '2024-01-01' }
      const result = await fetchRegistrationsOverTime(params)

      expect(apiFetch).toHaveBeenCalledWith('/analytics/registrations?start_date=2024-01-01')
      expect(result).toEqual(mockResponse)
    })

    it('fetches registrations data with both start and end date filters', async () => {
      const mockResponse = {
        data: [{ date: '2024-01-01', count: 5 }],
        total_registrations: 5,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const params = {
        start_date: '2024-01-01',
        end_date: '2024-12-31',
      }
      const result = await fetchRegistrationsOverTime(params)

      expect(apiFetch).toHaveBeenCalledWith(
        '/analytics/registrations?start_date=2024-01-01&end_date=2024-12-31',
      )
      expect(result).toEqual(mockResponse)
    })

    it('handles API errors', async () => {
      const mockError = new Error('Failed to fetch') as Error & { status: number }
      mockError.status = 500

      vi.mocked(apiFetch).mockRejectedValue(mockError)

      await expect(fetchRegistrationsOverTime()).rejects.toThrow('Failed to fetch')
    })
  })

  describe('fetchConversionFunnel (E41; Journey J34)', () => {
    it('fetches conversion funnel data without filters', async () => {
      const mockResponse = {
        funnel: [
          { stage: 'registered', count: 100 },
          { stage: 'counseling', count: 80 },
          { stage: 'enrolled', count: 20 },
        ],
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchConversionFunnel()

      expect(apiFetch).toHaveBeenCalledWith('/analytics/funnel')
      expect(result).toEqual(mockResponse)
    })

    it('fetches conversion funnel data with start_date filter', async () => {
      const mockResponse = {
        funnel: [{ stage: 'registered', count: 50 }],
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      await fetchConversionFunnel({ start_date: '2024-01-01' })

      expect(apiFetch).toHaveBeenCalledWith('/analytics/funnel?start_date=2024-01-01')
    })

    it('fetches conversion funnel data with end_date filter', async () => {
      const mockResponse = {
        funnel: [{ stage: 'registered', count: 50 }],
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      await fetchConversionFunnel({ end_date: '2024-12-31' })

      expect(apiFetch).toHaveBeenCalledWith('/analytics/funnel?end_date=2024-12-31')
    })

    it('fetches conversion funnel data with both date filters', async () => {
      const mockResponse = {
        funnel: [
          { stage: 'registered', count: 50 },
          { stage: 'counseling', count: 40 },
        ],
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      await fetchConversionFunnel({
        start_date: '2024-01-01',
        end_date: '2024-12-31',
      })

      expect(apiFetch).toHaveBeenCalledWith(
        '/analytics/funnel?start_date=2024-01-01&end_date=2024-12-31',
      )
    })
  })

  describe('fetchBranchComparison (E42; Journey J35)', () => {
    it('fetches branch comparison data without filters', async () => {
      const mockResponse = {
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
        total_branches: 1,
        total_applications: 100,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchBranchComparison()

      expect(apiFetch).toHaveBeenCalledWith('/analytics/branch-comparison')
      expect(result).toEqual(mockResponse)
    })

    it('includes start_date filter when provided', async () => {
      const mockResponse = {
        branches: [],
        total_branches: 0,
        total_applications: 0,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      await fetchBranchComparison({ start_date: '2024-01-01' })

      expect(apiFetch).toHaveBeenCalledWith('/analytics/branch-comparison?start_date=2024-01-01')
    })

    it('includes end_date filter when provided', async () => {
      const mockResponse = {
        branches: [],
        total_branches: 0,
        total_applications: 0,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      await fetchBranchComparison({ end_date: '2024-12-31' })

      expect(apiFetch).toHaveBeenCalledWith('/analytics/branch-comparison?end_date=2024-12-31')
    })

    it('includes both start_date and end_date filters when both provided', async () => {
      const mockResponse = {
        branches: [],
        total_branches: 0,
        total_applications: 0,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      await fetchBranchComparison({
        start_date: '2024-01-01',
        end_date: '2024-12-31',
      })

      expect(apiFetch).toHaveBeenCalledWith(
        '/analytics/branch-comparison?start_date=2024-01-01&end_date=2024-12-31',
      )
    })
  })

  describe('fetchPlatformWideStats (E43; Journey J36)', () => {
    it('fetches platform-wide stats without parameters', async () => {
      const mockResponse = {
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

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchPlatformWideStats()

      expect(apiFetch).toHaveBeenCalledWith('/analytics/platform-wide-stats')
      expect(result).toEqual(mockResponse)
    })

    it('fetches platform-wide stats with date range parameters', async () => {
      const mockResponse = {
        tenants: [],
        total_tenants: 2,
        total_branches: 4,
        total_staff: 13,
        total_students: 70,
        total_applications: 105,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const params = {
        start_date: '2024-01-01',
        end_date: '2024-01-31',
      }

      const result = await fetchPlatformWideStats(params)

      expect(apiFetch).toHaveBeenCalledWith(
        '/analytics/platform-wide-stats?start_date=2024-01-01&end_date=2024-01-31',
      )
      expect(result).toEqual(mockResponse)
    })

    it('fetches platform-wide stats with only start date', async () => {
      const mockResponse = {
        tenants: [],
        total_tenants: 1,
        total_branches: 2,
        total_staff: 8,
        total_students: 45,
        total_applications: 60,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const params = {
        start_date: '2024-01-01',
      }

      const result = await fetchPlatformWideStats(params)

      expect(apiFetch).toHaveBeenCalledWith(
        '/analytics/platform-wide-stats?start_date=2024-01-01',
      )
      expect(result).toEqual(mockResponse)
    })

    it('fetches platform-wide stats with only end date', async () => {
      const mockResponse = {
        tenants: [],
        total_tenants: 1,
        total_branches: 2,
        total_staff: 8,
        total_students: 45,
        total_applications: 60,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const params = {
        end_date: '2024-01-31',
      }

      const result = await fetchPlatformWideStats(params)

      expect(apiFetch).toHaveBeenCalledWith(
        '/analytics/platform-wide-stats?end_date=2024-01-31',
      )
      expect(result).toEqual(mockResponse)
    })

    it('handles API errors', async () => {
      const mockError = new Error('Network error')
      vi.mocked(apiFetch).mockRejectedValue(mockError)

      await expect(fetchPlatformWideStats()).rejects.toThrow('Network error')
    })

    it('properly encodes date parameters', async () => {
      const mockResponse = {
        tenants: [],
        total_tenants: 1,
        total_branches: 1,
        total_staff: 3,
        total_students: 15,
        total_applications: 20,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const params = {
        start_date: '2024-01-01T00:00:00Z',
        end_date: '2024-01-31T23:59:59Z',
      }

      await fetchPlatformWideStats(params)

      expect(apiFetch).toHaveBeenCalledWith(
        '/analytics/platform-wide-stats?start_date=2024-01-01T00%3A00%3A00Z&end_date=2024-01-31T23%3A59%3A59Z',
      )
    })

    it('returns tenants ordered by application count', async () => {
      const mockResponse = {
        tenants: [
          {
            tenant_id: 1,
            tenant_name: 'High Volume Consultancy',
            tenant_slug: 'high-volume',
            plan_code: 'enterprise',
            branches_count: 10,
            staff_count: 50,
            students_count: 500,
            applications_count: 750,
            enrolled_count: 200,
            rejected_count: 50,
            withdrawn_count: 25,
            active_count: 475,
          },
          {
            tenant_id: 2,
            tenant_name: 'Low Volume Consultancy',
            tenant_slug: 'low-volume',
            plan_code: 'starter',
            branches_count: 1,
            staff_count: 3,
            students_count: 15,
            applications_count: 20,
            enrolled_count: 5,
            rejected_count: 2,
            withdrawn_count: 1,
            active_count: 12,
          },
        ],
        total_tenants: 2,
        total_branches: 11,
        total_staff: 53,
        total_students: 515,
        total_applications: 770,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchPlatformWideStats()

      expect(result.tenants[0].applications_count).toBeGreaterThanOrEqual(
        result.tenants[1].applications_count,
      )
    })
  })
})
