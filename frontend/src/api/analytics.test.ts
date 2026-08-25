/**
 * Tests for analytics API client (E41/E42; Journeys J34/J35).
 */

import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import {
  fetchBranchComparison,
  fetchConversionFunnel,
  fetchRegistrationsOverTime,
} from './analytics'

// Mock the HTTP client
vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

describe('analytics API', () => {
  describe('fetchRegistrationsOverTime', () => {
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

  describe('fetchConversionFunnel', () => {
    it('fetches funnel data without filters', async () => {
      const mockResponse = {
        funnel: [
          { stage: 'registered', count: 100 },
          { stage: 'enrolled', count: 50 },
        ],
        total_applications: 150,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchConversionFunnel()

      expect(apiFetch).toHaveBeenCalledTimes(1)
      expect(apiFetch).toHaveBeenCalledWith('/analytics/funnel')
      expect(result).toEqual(mockResponse)
    })

    it('fetches funnel data with start_date filter', async () => {
      const mockResponse = {
        funnel: [{ stage: 'enrolled', count: 10 }],
        total_applications: 10,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const params = { start_date: '2024-01-01' }
      const result = await fetchConversionFunnel(params)

      expect(apiFetch).toHaveBeenCalledWith('/analytics/funnel?start_date=2024-01-01')
      expect(result).toEqual(mockResponse)
    })

    it('fetches funnel data with end_date filter', async () => {
      const mockResponse = {
        funnel: [{ stage: 'enrolled', count: 10 }],
        total_applications: 10,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const params = { end_date: '2024-12-31' }
      const result = await fetchConversionFunnel(params)

      expect(apiFetch).toHaveBeenCalledWith('/analytics/funnel?end_date=2024-12-31')
      expect(result).toEqual(mockResponse)
    })

    it('fetches funnel data with both start and end date filters', async () => {
      const mockResponse = {
        funnel: [{ stage: 'enrolled', count: 10 }],
        total_applications: 10,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const params = {
        start_date: '2024-01-01',
        end_date: '2024-12-31',
      }
      const result = await fetchConversionFunnel(params)

      expect(apiFetch).toHaveBeenCalledWith(
        '/analytics/funnel?start_date=2024-01-01&end_date=2024-12-31',
      )
      expect(result).toEqual(mockResponse)
    })

    it('handles API errors', async () => {
      const mockError = new Error('Failed to fetch') as Error & { status: number }
      mockError.status = 500

      vi.mocked(apiFetch).mockRejectedValue(mockError)

      await expect(fetchConversionFunnel()).rejects.toThrow('Failed to fetch')
    })
  })

  describe('fetchBranchComparison', () => {
    it('should fetch branch comparison data without filters', async () => {
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

    it('should include start_date filter when provided', async () => {
      const mockResponse = {
        branches: [],
        total_branches: 0,
        total_applications: 0,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      await fetchBranchComparison({ start_date: '2024-01-01' })

      expect(apiFetch).toHaveBeenCalledWith('/analytics/branch-comparison?start_date=2024-01-01')
    })

    it('should include end_date filter when provided', async () => {
      const mockResponse = {
        branches: [],
        total_branches: 0,
        total_applications: 0,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      await fetchBranchComparison({ end_date: '2024-12-31' })

      expect(apiFetch).toHaveBeenCalledWith('/analytics/branch-comparison?end_date=2024-12-31')
    })

    it('should include both start_date and end_date filters when both provided', async () => {
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
})
