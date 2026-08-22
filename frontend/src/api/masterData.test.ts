import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createAdminCountry,
  createAdminProgram,
  createAdminUniversity,
  deleteAdminCountry,
  deleteAdminProgram,
  deleteAdminUniversity,
  fetchAdminCountries,
  fetchAdminPrograms,
  fetchAdminUniversities,
  fetchCountries,
  fetchPrograms,
  fetchUniversities,
  updateAdminCountry,
  updateAdminProgram,
  updateAdminUniversity,
} from './masterData'

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

  it('fetchAdminCountries requests countries from the admin endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockCountries,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchAdminCountries()

    expect(result).toEqual(mockCountries)
    expect(fetchMock).toHaveBeenCalledWith('/master-data/admin/countries', {
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('createAdminCountry posts to the admin endpoint with JSON body', async () => {
    const created = { id: 3, tenant_id: 10, name: 'Australia', code: 'AU' }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => created,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await createAdminCountry({ name: 'Australia', code: 'AU' })

    expect(result).toEqual(created)
    expect(fetchMock).toHaveBeenCalledWith('/master-data/admin/countries', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Australia', code: 'AU' }),
    })
  })

  it('updateAdminCountry patches the admin endpoint with id in path', async () => {
    const updated = { id: 1, tenant_id: 10, name: 'Canada Renamed', code: 'CA' }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => updated,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await updateAdminCountry(1, { name: 'Canada Renamed' })

    expect(result).toEqual(updated)
    expect(fetchMock).toHaveBeenCalledWith('/master-data/admin/countries/1', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Canada Renamed' }),
    })
  })

  it('deleteAdminCountry issues DELETE on the admin endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => undefined,
    })
    globalThis.fetch = fetchMock as typeof fetch

    await deleteAdminCountry(1)

    expect(fetchMock).toHaveBeenCalledWith('/master-data/admin/countries/1', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('fetchAdminUniversities requests universities from the admin endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUniversities,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchAdminUniversities()

    expect(result).toEqual(mockUniversities)
    expect(fetchMock).toHaveBeenCalledWith('/master-data/admin/universities', {
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('createAdminUniversity posts to the admin endpoint with country FK', async () => {
    const created = { id: 99, tenant_id: 10, country_id: 1, name: 'UBC' }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => created,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await createAdminUniversity({ country_id: 1, name: 'UBC' })

    expect(result).toEqual(created)
    expect(fetchMock).toHaveBeenCalledWith('/master-data/admin/universities', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ country_id: 1, name: 'UBC' }),
    })
  })

  it('updateAdminUniversity patches the admin endpoint', async () => {
    const updated = { id: 99, tenant_id: 10, country_id: 2, name: 'UBC Renamed' }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => updated,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await updateAdminUniversity(99, { country_id: 2, name: 'UBC Renamed' })

    expect(result).toEqual(updated)
    expect(fetchMock).toHaveBeenCalledWith('/master-data/admin/universities/99', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ country_id: 2, name: 'UBC Renamed' }),
    })
  })

  it('deleteAdminUniversity issues DELETE on the admin endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => undefined,
    })
    globalThis.fetch = fetchMock as typeof fetch

    await deleteAdminUniversity(99)

    expect(fetchMock).toHaveBeenCalledWith('/master-data/admin/universities/99', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('fetchAdminPrograms requests programs from the admin endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockPrograms,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchAdminPrograms()

    expect(result).toEqual(mockPrograms)
    expect(fetchMock).toHaveBeenCalledWith('/master-data/admin/programs', {
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('createAdminProgram posts to the admin endpoint with university FK', async () => {
    const created = { id: 200, tenant_id: 10, university_id: 10, name: 'MDS' }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => created,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await createAdminProgram({ university_id: 10, name: 'MDS' })

    expect(result).toEqual(created)
    expect(fetchMock).toHaveBeenCalledWith('/master-data/admin/programs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ university_id: 10, name: 'MDS' }),
    })
  })

  it('updateAdminProgram patches the admin endpoint', async () => {
    const updated = { id: 200, tenant_id: 10, university_id: 11, name: 'MDS Renamed' }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => updated,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await updateAdminProgram(200, { university_id: 11, name: 'MDS Renamed' })

    expect(result).toEqual(updated)
    expect(fetchMock).toHaveBeenCalledWith('/master-data/admin/programs/200', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ university_id: 11, name: 'MDS Renamed' }),
    })
  })

  it('deleteAdminProgram issues DELETE on the admin endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => undefined,
    })
    globalThis.fetch = fetchMock as typeof fetch

    await deleteAdminProgram(200)

    expect(fetchMock).toHaveBeenCalledWith('/master-data/admin/programs/200', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    })
  })
})
