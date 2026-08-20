import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createApplication } from './applications'

const mockApplication = {
  id: 1,
  tenant_id: 10,
  student_id: 8,
  university_id: 1,
  program_id: 10,
  stage: 'registered' as const,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const validPayload = {
  university_id: 1,
  program_id: 10,
}

describe('applications API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
  })

  it('createApplication posts payload with auth header', async () => {
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
