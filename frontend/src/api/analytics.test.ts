/**
 * Tests for analytics API client (E41; Journey J34).
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'

import { apiFetch } from './client'
import {
  fetchConversionFunnel,
  fetchRegistrationsOverTime,
} from './analytics'

vi.mock('./client')

describe('analytics API client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

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

      expect(apiFetch).toHaveBeenCalledWith(
        '/analytics/registrations?start_date=2024-01-01',
      )
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
})
