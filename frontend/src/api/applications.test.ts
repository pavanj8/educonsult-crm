import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchApplications } from './applications'

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
})
