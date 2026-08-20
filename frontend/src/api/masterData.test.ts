import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchCountries, fetchPrograms, fetchUniversities } from './masterData'

const mockCountries = [
  { id: 1, tenant_id: 10, name: 'Canada', code: 'CA' },
  { id: 2, tenant_id: 10, name: 'United Kingdom', code: 'GB' },
]

const mockUniversities = [
  { id: 10, tenant_id: 10, country_id: 1, name: 'University of Toronto' },
]

const mockPrograms = [{ id: 100, tenant_id: 10, university_id: 10, name: 'Computer Science MSc' }]

describe('masterData API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('fetchCountries requests tenant-scoped countries without auth', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockCountries,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchCountries('apex')

    expect(result).toEqual(mockCountries)
    expect(fetchMock).toHaveBeenCalledWith('/tenants/apex/countries', {
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('fetchUniversities requests universities filtered by country', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUniversities,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchUniversities('apex', 1)

    expect(result).toEqual(mockUniversities)
    expect(fetchMock).toHaveBeenCalledWith('/tenants/apex/universities?country_id=1', {
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('fetchPrograms requests programs filtered by university', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockPrograms,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchPrograms('apex', 10)

    expect(result).toEqual(mockPrograms)
    expect(fetchMock).toHaveBeenCalledWith('/tenants/apex/programs?university_id=10', {
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('encodes tenant slug in request path', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    })
    globalThis.fetch = fetchMock as typeof fetch

    await fetchCountries('apex consulting')

    expect(fetchMock).toHaveBeenCalledWith('/tenants/apex%20consulting/countries', {
      headers: { 'Content-Type': 'application/json' },
    })
  })
})
