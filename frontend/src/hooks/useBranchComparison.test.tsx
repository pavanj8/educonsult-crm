/**
 * Tests for useBranchComparison hook (E42; Journey J35).
 */

import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { isApiError } from '../api/client'
import { fetchBranchComparison } from '../api/analytics'
import { hasAccessToken } from '../store/authStorage'
import { useBranchComparison } from './useBranchComparison'

// Mock dependencies
vi.mock('../api/analytics', () => ({
  fetchBranchComparison: vi.fn(),
}))

vi.mock('../api/client', () => ({
  isApiError: vi.fn(),
}))

vi.mock('../store/authStorage', () => ({
  hasAccessToken: vi.fn(),
}))

const mockFetchBranchComparison = vi.mocked(fetchBranchComparison)
const mockHasAccessToken = vi.mocked(hasAccessToken)
const mockIsApiError = vi.mocked(isApiError)

describe('useBranchComparison', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockHasAccessToken.mockReturnValue(true)
  })

  it('should load branch comparison data on mount', async () => {
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

    mockFetchBranchComparison.mockResolvedValue(mockResponse)

    const { result } = renderHook(() => useBranchComparison())

    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.branches).toEqual(mockResponse.branches)
    expect(result.current.totalBranches).toBe(1)
    expect(result.current.totalApplications).toBe(100)
    expect(result.current.error).toBeNull()
  })

  it('should return empty state when no access token', async () => {
    mockHasAccessToken.mockReturnValue(false)

    const { result } = renderHook(() => useBranchComparison())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.branches).toEqual([])
    expect(result.current.totalBranches).toBe(0)
    expect(result.current.totalApplications).toBe(0)
    expect(result.current.error).toBeNull()
  })

  it('should handle 403 error', async () => {
    const mockError = { status: 403, message: 'Forbidden' }
    mockFetchBranchComparison.mockRejectedValue(mockError)
    mockIsApiError.mockReturnValue(true)

    const { result } = renderHook(() => useBranchComparison())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('You do not have permission to view branch analytics')
  })

  it('should handle 401 error', async () => {
    const mockError = { status: 401, message: 'Unauthorized' }
    mockFetchBranchComparison.mockRejectedValue(mockError)
    mockIsApiError.mockReturnValue(true)

    const { result } = renderHook(() => useBranchComparison())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Sign in to view branch analytics')
  })

  it('should handle generic error', async () => {
    mockFetchBranchComparison.mockRejectedValue(new Error('Network error'))
    mockIsApiError.mockReturnValue(false)

    const { result } = renderHook(() => useBranchComparison())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Failed to load branch comparison data')
  })

  it('should support reload', async () => {
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

    mockFetchBranchComparison.mockResolvedValue(mockResponse)

    const { result } = renderHook(() => useBranchComparison())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(mockFetchBranchComparison).toHaveBeenCalledTimes(1)

    await result.current.reload()

    expect(mockFetchBranchComparison).toHaveBeenCalledTimes(2)
  })

  it('should support refetch with new params', async () => {
    const mockResponse = {
      branches: [],
      total_branches: 0,
      total_applications: 0,
    }

    mockFetchBranchComparison.mockResolvedValue(mockResponse)

    const { result } = renderHook(() => useBranchComparison())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(mockFetchBranchComparison).toHaveBeenCalledTimes(1)
    expect(mockFetchBranchComparison).toHaveBeenCalledWith(undefined)

    await result.current.refetch({ start_date: '2024-01-01' })

    expect(mockFetchBranchComparison).toHaveBeenCalledTimes(2)
    expect(mockFetchBranchComparison).toHaveBeenCalledWith({ start_date: '2024-01-01' })
  })

  it('should pass initial params to API', async () => {
    const mockResponse = {
      branches: [],
      total_branches: 0,
      total_applications: 0,
    }

    mockFetchBranchComparison.mockResolvedValue(mockResponse)

    renderHook(() =>
      useBranchComparison({
        start_date: '2024-01-01',
        end_date: '2024-12-31',
      }),
    )

    await waitFor(() => {
      expect(mockFetchBranchComparison).toHaveBeenCalledTimes(1)
    })

    expect(mockFetchBranchComparison).toHaveBeenCalledWith({
      start_date: '2024-01-01',
      end_date: '2024-12-31',
    })
  })
})
