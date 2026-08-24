import { beforeEach, describe, expect, it, vi } from 'vitest'

import { updateVisaOutcome } from './visa'

const mockOutcome = {
  id: 11,
  tenant_id: 10,
  application_id: 5,
  status: 'approved',
  outcome_date: '2026-09-30T10:00:00+00:00',
  notes: 'Stamped at US embassy',
  created_at: '2026-09-30T10:01:00+00:00',
  updated_at: '2026-09-30T10:01:00+00:00',
}

describe('updateVisaOutcome API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('patches the outcome payload to the application outcome endpoint', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockOutcome,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await updateVisaOutcome(5, {
      status: 'approved',
      outcome_date: '2026-09-30T10:00:00+00:00',
      notes: 'Stamped at US embassy',
    })

    expect(result).toEqual(mockOutcome)
    expect(fetchMock).toHaveBeenCalledWith(
      '/visa/applications/5/outcome',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          status: 'approved',
          outcome_date: '2026-09-30T10:00:00+00:00',
          notes: 'Stamped at US embassy',
        }),
      }),
    )
    const headers = (fetchMock.mock.calls[0]?.[1]?.headers ?? {}) as Record<string, string>
    expect(headers.Authorization).toBe('Bearer stored-access-token')
    expect(headers['Content-Type']).toBe('application/json')
  })

  it('surfaces the backend 422 detail (in-stage guard)', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail:
          "Application in stage 'enrolled' cannot have its visa outcome updated.",
      }),
    }) as typeof fetch

    await expect(
      updateVisaOutcome(5, { status: 'approved' }),
    ).rejects.toMatchObject({
      message: expect.stringContaining("cannot have its visa outcome updated"),
      status: 422,
    })
  })

  it('surfaces a 503 detail (database unavailable)', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Visa outcome update is temporarily unavailable' }),
    }) as typeof fetch

    await expect(
      updateVisaOutcome(5, { status: 'approved' }),
    ).rejects.toMatchObject({
      message: 'Visa outcome update is temporarily unavailable',
      status: 503,
    })
  })

  it('surfaces the backend 404 detail (cross-tenant application)', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Application not found' }),
    }) as typeof fetch

    await expect(
      updateVisaOutcome(5, { status: 'approved' }),
    ).rejects.toMatchObject({ status: 404, message: 'Application not found' })
  })
})
