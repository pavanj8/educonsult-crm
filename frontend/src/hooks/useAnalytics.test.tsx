/**
 * Tests for useAnalytics hook (E41; Journey J34).
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'

import { renderHook, waitFor } from '@testing-library/react'

import { useAnalytics } from './useAnalytics'
import { fetchConversionFunnel } from '../api/analytics'
import type { DateRange, DateRangePreset } from '../types/analytics'

vi.mock('../api/analytics')

const mockData = {
  funnel: [
    { stage: 'registered', count: 100 },
    { stage: 'enrolled', count: 50 },
  ],
  total_applications: 150,
}

describe('useAnalytics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('initially returns loading state', () => {
    vi.mocked(fetchConversionFunnel).mockImplementation(
      () => new Promise(() => {}), // Never resolves
    )

    const { result } = renderHook(() => useAnalytics())

    expect(result.current.loading).toBe(true)
    expect(result.current.data).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('fetches analytics data successfully', async () => {
    vi.mocked(fetchConversionFunnel).mockResolvedValue(mockData)

    const { result } = renderHook(() => useAnalytics())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toEqual(mockData)
    expect(result.current.error).toBeNull()
  })

  it('passes date range params to API call', async () => {
    vi.mocked(fetchConversionFunnel).mockResolvedValue(mockData)

    const dateRange: DateRange = {
      preset: 'custom',
      startDate: '2024-01-01',
      endDate: '2024-12-31',
    }

    const { result } = renderHook(() => useAnalytics(dateRange))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchConversionFunnel).toHaveBeenCalledWith({
      start_date: '2024-01-01',
      end_date: '2024-12-31',
    })
  })

  it('does not pass null dates to API call', async () => {
    vi.mocked(fetchConversionFunnel).mockResolvedValue(mockData)

    const dateRange: DateRange = {
      preset: 'custom',
      startDate: null,
      endDate: null,
    }

    const { result } = renderHook(() => useAnalytics(dateRange))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchConversionFunnel).toHaveBeenCalledWith({})
  })

  it('handles API errors', async () => {
    const mockError = new Error('Failed to fetch') as Error & { status: number }
    mockError.status = 500

    vi.mocked(fetchConversionFunnel).mockRejectedValue(mockError)

    const { result } = renderHook(() => useAnalytics())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toBeNull()
    expect(result.current.error).toBe('Failed to fetch')
  })

  it('reload function refetches data', async () => {
    vi.mocked(fetchConversionFunnel).mockResolvedValue(mockData)

    const { result } = renderHook(() => useAnalytics())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchConversionFunnel).toHaveBeenCalledTimes(1)

    await result.current.reload()

    expect(fetchConversionFunnel).toHaveBeenCalledTimes(2)
  })

  it('refetches when date range changes', async () => {
    vi.mocked(fetchConversionFunnel).mockResolvedValue(mockData)

    const { result, rerender } = renderHook(
      (props) => useAnalytics(props.dateRange),
      {
        initialProps: {
          dateRange: {
            preset: 'custom' as DateRangePreset,
            startDate: '2024-01-01',
            endDate: '2024-01-31',
          },
        },
      },
    )

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchConversionFunnel).toHaveBeenCalledTimes(1)
    expect(fetchConversionFunnel).toHaveBeenCalledWith({
      start_date: '2024-01-01',
      end_date: '2024-01-31',
    })

    rerender({
      dateRange: {
        preset: 'custom' as DateRangePreset,
        startDate: '2024-02-01',
        endDate: '2024-02-29',
      },
    })

    await waitFor(() => {
      expect(fetchConversionFunnel).toHaveBeenCalledTimes(2)
    })

    expect(fetchConversionFunnel).toHaveBeenCalledWith({
      start_date: '2024-02-01',
      end_date: '2024-02-29',
    })
  })

  it('does not refetch when only preset changes but dates are same', async () => {
    vi.mocked(fetchConversionFunnel).mockResolvedValue(mockData)

    const { result, rerender } = renderHook(
      (props) => useAnalytics(props.dateRange),
      {
        initialProps: {
          dateRange: {
            preset: 'custom' as DateRangePreset,
            startDate: '2024-01-01',
            endDate: '2024-01-31',
          },
        },
      },
    )

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchConversionFunnel).toHaveBeenCalledTimes(1)

    // Change preset only (dates are computed, not provided)
    rerender({
      dateRange: {
        preset: '15d' as DateRangePreset,
        startDate: '2024-01-01',
        endDate: '2024-01-31',
      },
    })

    // Should not refetch since dates are the same
    expect(fetchConversionFunnel).toHaveBeenCalledTimes(1)
  })
})
