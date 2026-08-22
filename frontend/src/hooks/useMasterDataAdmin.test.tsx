import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useMasterDataAdmin } from './useMasterDataAdmin'

const mockCountries = [
  { id: 1, tenant_id: 10, name: 'Canada', code: 'CA' },
]

const mockUniversities = [
  { id: 10, tenant_id: 10, country_id: 1, name: 'University of Toronto' },
]

const mockPrograms = [
  { id: 100, tenant_id: 10, university_id: 10, name: 'Computer Science MSc' },
]

function mockFetchSequence(responses: Array<{ ok: boolean; status: number; body: unknown }>) {
  const queue = [...responses]
  const fetchSpy = vi.fn(async () => {
    const next = queue.shift() ?? {
      ok: true,
      status: 200,
      body: [],
    }
    return {
      ok: next.ok,
      status: next.status,
      json: async () => next.body,
    }
  })
  globalThis.fetch = fetchSpy as unknown as typeof fetch
  return fetchSpy
}

describe('useMasterDataAdmin', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('loads countries, universities, and programs on mount when authenticated', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchSpy = mockFetchSequence([
      { ok: true, status: 200, body: mockCountries },
      { ok: true, status: 200, body: mockUniversities },
      { ok: true, status: 200, body: mockPrograms },
    ])

    const { result } = renderHook(() => useMasterDataAdmin())

    await waitFor(() => {
      expect(result.current.countriesLoading).toBe(false)
    })

    expect(result.current.countries).toEqual(mockCountries)
    expect(result.current.universities).toEqual(mockUniversities)
    expect(result.current.programs).toEqual(mockPrograms)

    const urls = fetchSpy.mock.calls.map((call) => String(call[0]))
    expect(urls).toContain('/master-data/admin/countries')
    expect(urls).toContain('/master-data/admin/universities')
    expect(urls).toContain('/master-data/admin/programs')
  })

  it('does not fetch when no access token is present', async () => {
    globalThis.fetch = vi.fn() as unknown as typeof fetch
    const { result } = renderHook(() => useMasterDataAdmin())
    await waitFor(() => {
      expect(result.current.countriesLoading).toBe(false)
    })
    expect(result.current.countries).toEqual([])
    expect(result.current.universities).toEqual([])
    expect(result.current.programs).toEqual([])
  })

  it('creates a country and surfaces API errors', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchSpy = mockFetchSequence([
      { ok: true, status: 200, body: mockCountries },
      { ok: true, status: 200, body: mockUniversities },
      { ok: true, status: 200, body: mockPrograms },
      { ok: false, status: 422, body: { detail: 'Country name is required' } },
    ])

    const { result } = renderHook(() => useMasterDataAdmin())

    await waitFor(() => {
      expect(result.current.countriesLoading).toBe(false)
    })

    await act(async () => {
      await expect(
        result.current.createCountry({ name: '', code: 'XX' }),
      ).rejects.toMatchObject({ status: 422 })
    })

    await waitFor(() => {
      expect(result.current.createError).toBe('Country name is required')
    })

    const postCall = fetchSpy.mock.calls.find((call) => {
      const [url, init] = call
      return (
        typeof url === 'string' &&
        url.endsWith('/master-data/admin/countries') &&
        ((init as RequestInit | undefined)?.method ?? 'GET') === 'POST'
      )
    })
    expect(postCall).toBeDefined()
  })

  it('updates a country via PATCH and surfaces errors', async () => {
    localStorage.setItem('access_token', 'test-token')
    const updatedCountry = { ...mockCountries[0], name: 'Canada Renamed' }
    const fetchSpy = mockFetchSequence([
      { ok: true, status: 200, body: mockCountries },
      { ok: true, status: 200, body: mockUniversities },
      { ok: true, status: 200, body: mockPrograms },
      { ok: false, status: 404, body: { detail: 'Country not found' } },
    ])

    const { result } = renderHook(() => useMasterDataAdmin())
    await waitFor(() => {
      expect(result.current.countriesLoading).toBe(false)
    })

    await act(async () => {
      await expect(
        result.current.updateCountry(1, { name: 'Canada Renamed' }),
      ).rejects.toMatchObject({ status: 404 })
    })

    await waitFor(() => {
      expect(result.current.updateError).toBe('Country not found')
    })

    const patchCall = fetchSpy.mock.calls.find((call) => {
      const [url, init] = call
      return (
        typeof url === 'string' &&
        url.endsWith('/master-data/admin/countries/1') &&
        ((init as RequestInit | undefined)?.method ?? 'GET') === 'PATCH'
      )
    })
    expect(patchCall).toBeDefined()
    expect(updatedCountry.name).toBe('Canada Renamed') // touch fixture
  })

  it('deletes a country via DELETE and surfaces errors', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchSpy = mockFetchSequence([
      { ok: true, status: 200, body: mockCountries },
      { ok: true, status: 200, body: mockUniversities },
      { ok: true, status: 200, body: mockPrograms },
      { ok: false, status: 409, body: { detail: 'Country is in use' } },
    ])

    const { result } = renderHook(() => useMasterDataAdmin())
    await waitFor(() => {
      expect(result.current.countriesLoading).toBe(false)
    })

    await act(async () => {
      await expect(result.current.deleteCountry(1)).rejects.toMatchObject({ status: 409 })
    })

    await waitFor(() => {
      expect(result.current.deleteError).toBe('Country is in use')
    })

    const deleteCall = fetchSpy.mock.calls.find((call) => {
      const [url, init] = call
      return (
        typeof url === 'string' &&
        url.endsWith('/master-data/admin/countries/1') &&
        ((init as RequestInit | undefined)?.method ?? 'GET') === 'DELETE'
      )
    })
    expect(deleteCall).toBeDefined()
  })
})