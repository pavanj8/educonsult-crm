/**
 * Tests for analytics API client (E42; Journey J35).
 */

import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import { fetchBranchComparison } from './analytics'

// Mock the HTTP client
vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

describe('analytics API', () => {
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

      expect(apiFetch).toHaveBeenCalledWith(
        '/analytics/branch-comparison?start_date=2024-01-01',
      )
    })

    it('should include end_date filter when provided', async () => {
      const mockResponse = {
        branches: [],
        total_branches: 0,
        total_applications: 0,
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      await fetchBranchComparison({ end_date: '2024-12-31' })

      expect(apiFetch).toHaveBeenCalledWith(
        '/analytics/branch-comparison?end_date=2024-12-31',
      )
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
