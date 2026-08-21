import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createApplication, fetchApplications } from './applications'

const mockApplication = {
  id: 1,
  tenant_id: 10,
  student_id: 42,
  university_id: 1,
  program_id: 10,
  stage: 'registered' as const,
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
}

const validPayload = {
  university_id: 1,
  program_id: 10,
}

describe('applications API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('fetchApplications sends bearer token from storage', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [mockApplication],
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchApplications()

    expect(result).toEqual([mockApplication])
    expect(fetchMock).toHaveBeenCalledWith('/applications', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer stored-access-token',
      },
    })
  })

  it('fetchApplications surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    await expect(fetchApplications()).rejects.toMatchObject({
      message: 'Insufficient permissions',
      status: 403,
    })
  })

  it('createApplication posts payload with auth header', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockApplication,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await createApplication(validPayload)

    expect(result).toEqual(mockApplication)
    expect(fetchMock).toHaveBeenCalledWith('/applications', {
      method: 'POST',
      body: JSON.stringify(validPayload),
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer test-token',
      },
    })
  })

  it('createApplication surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    await expect(createApplication(validPayload)).rejects.toMatchObject({
      message: 'Insufficient permissions',
      status: 403,
    })
  })

  it('createApplication surfaces validation error detail on 422', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [{ loc: ['body', 'program_id'], msg: 'Field required', type: 'value_error' }],
      }),
    }) as typeof fetch

    await expect(createApplication(validPayload)).rejects.toMatchObject({
      message: 'Field required',
      status: 422,
    })
  })
})

describe('markEnrolled API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('posts trimmed details to the mark-enrolled endpoint', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const result = { application: { id: 5 }, history_entry: { to_stage: 'enrolled' } }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => result })
    globalThis.fetch = fetchMock as typeof fetch

    const { markEnrolled } = await import('./applications')
    const res = await markEnrolled(5, '  Fall 2026  ')

    expect(res).toEqual(result)
    expect(fetchMock).toHaveBeenCalledWith(
      '/applications/5/mark-enrolled',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ details: 'Fall 2026' }) }),
    )
  })

  it('sends null details when omitted', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) })
    globalThis.fetch = fetchMock as typeof fetch
    const { markEnrolled } = await import('./applications')
    await markEnrolled(5)
    expect(fetchMock).toHaveBeenCalledWith(
      '/applications/5/mark-enrolled',
      expect.objectContaining({ body: JSON.stringify({ details: null }) }),
    )
  })
})

describe('fetchAssignedApplications API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('calls the assigned-to-me endpoint with the bearer token', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const apps = [{ id: 1, stage: 'registered' }]
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => apps })
    globalThis.fetch = fetchMock as typeof fetch
    const { fetchAssignedApplications } = await import('./applications')
    const res = await fetchAssignedApplications()
    expect(res).toEqual(apps)
    expect(fetchMock).toHaveBeenCalledWith('/applications/assigned-to-me', {
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer stored-access-token' },
    })
  })

  it('forwards a stage filter as a query param', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => [] })
    globalThis.fetch = fetchMock as typeof fetch
    const { fetchAssignedApplications } = await import('./applications')
    await fetchAssignedApplications({ stage: 'counseling' })
    expect(fetchMock).toHaveBeenCalledWith('/applications/assigned-to-me?stage=counseling', expect.anything())
  })
})
