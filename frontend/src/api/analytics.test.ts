/**
 * Tests for analytics API client (E41, E42, E43; Journey J34, J35, J36).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fetchPlatformWideStats } from './analytics'

// Mock the client
vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

describe('fetchPlatformWideStats (E43; Journey J36)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  it('should fetch platform-wide stats without parameters', async () => {
    const { apiFetch } = await import('./client')
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

  it('should fetch platform-wide stats with date range parameters', async () => {
    const { apiFetch } = await import('./client')
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

  it('should fetch platform-wide stats with only start date', async () => {
    const { apiFetch } = await import('./client')
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

  it('should fetch platform-wide stats with only end date', async () => {
    const { apiFetch } = await import('./client')
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

  it('should handle API errors', async () => {
    const { apiFetch } = await import('./client')
    const mockError = new Error('Network error')
    vi.mocked(apiFetch).mockRejectedValue(mockError)

    await expect(fetchPlatformWideStats()).rejects.toThrow('Network error')
  })

  it('should properly encode date parameters', async () => {
    const { apiFetch } = await import('./client')
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

  it('should return tenants ordered by application count', async () => {
    const { apiFetch } = await import('./client')
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
