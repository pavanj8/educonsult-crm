import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useCountries, usePrograms, useUniversities } from './useMasterData'

const mockCountries = [{ id: 1, tenant_id: 10, name: 'Canada', code: 'CA' }]
const mockUniversities = [{ id: 10, tenant_id: 10, country_id: 1, name: 'University of Toronto' }]
const mockPrograms = [{ id: 100, tenant_id: 10, university_id: 10, name: 'Computer Science MSc' }]

describe('useMasterData hooks', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('useCountries loads countries when tenant slug is provided', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockCountries,
    }) as typeof fetch

    const { result } = renderHook(() => useCountries('apex'))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.items).toEqual(mockCountries)
    expect(result.current.error).toBeNull()
  })

  it('useCountries skips fetch when tenant slug is empty', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useCountries(''))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.items).toHaveLength(0)
  })

  it('useCountries sets error on 404', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Tenant not found' }),
    }) as typeof fetch

    const { result } = renderHook(() => useCountries('missing'))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Consultancy not found')
    expect(result.current.items).toHaveLength(0)
  })

  it('useUniversities loads universities when country is selected', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUniversities,
    }) as typeof fetch

    const { result } = renderHook(() => useUniversities('apex', 1))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.items).toEqual(mockUniversities)
  })

  it('useUniversities skips fetch when country is not selected', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => useUniversities('apex', ''))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('usePrograms loads programs when university is selected', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockPrograms,
    }) as typeof fetch

    const { result } = renderHook(() => usePrograms('apex', 10))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.items).toEqual(mockPrograms)
  })

  it('usePrograms skips fetch when university is not selected', async () => {
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock as typeof fetch

    const { result } = renderHook(() => usePrograms('apex', ''))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
