import { beforeEach, describe, expect, it, vi } from 'vitest'

<<<<<<< HEAD
import { isApiError } from './client'
import { fetchVisaDetail, updateVisaDetail } from './visa'

const mockVisaDetail = {
  id: 1,
  tenant_id: 10,
  application_id: 5,
  visa_type: 'F-1 Student',
  interview_date: '2026-11-05T14:30:00Z',
  created_at: '2026-09-01T09:00:00Z',
  updated_at: '2026-09-01T09:00:00Z',
}

describe('visa API client', () => {
=======
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
>>>>>>> origin/main
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

<<<<<<< HEAD
  describe('fetchVisaDetail', () => {
    it('GETs the visa detail endpoint with the bearer token', async () => {
      localStorage.setItem('access_token', 'stored-token')
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockVisaDetail,
      })
      globalThis.fetch = fetchMock as typeof fetch

      const result = await fetchVisaDetail(5)

      expect(result).toEqual(mockVisaDetail)
      expect(fetchMock).toHaveBeenCalledWith('/visa/applications/5/details', {
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer stored-token',
        },
      })
    })

    it('returns null when the backend responds 404 (no detail recorded yet)', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Visa detail not found' }),
      })
      globalThis.fetch = fetchMock as typeof fetch

      const result = await fetchVisaDetail(5)

      expect(result).toBeNull()
    })

    it('propagates non-404 errors as ApiError', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Insufficient permissions' }),
      })
      globalThis.fetch = fetchMock as typeof fetch

      await expect(fetchVisaDetail(5)).rejects.toThrow()
      try {
        await fetchVisaDetail(5)
      } catch (err) {
        expect(isApiError(err) && err.status).toBe(403)
      }
    })
  })

  describe('updateVisaDetail', () => {
    it('PUTs the visa type + interview_date to the details endpoint', async () => {
      localStorage.setItem('access_token', 'stored-token')
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockVisaDetail,
      })
      globalThis.fetch = fetchMock as typeof fetch

      const result = await updateVisaDetail(5, {
        visa_type: 'F-1 Student',
        interview_date: '2026-11-05T14:30:00Z',
      })

      expect(result).toEqual(mockVisaDetail)
      expect(fetchMock).toHaveBeenCalledWith(
        '/visa/applications/5/details',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({
            visa_type: 'F-1 Student',
            interview_date: '2026-11-05T14:30:00Z',
          }),
        }),
      )
      const headers = (fetchMock.mock.calls[0]?.[1]?.headers ?? {}) as Record<string, string>
      expect(headers.Authorization).toBe('Bearer stored-token')
      expect(headers['Content-Type']).toBe('application/json')
    })

    it('trims the visa_type before sending', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockVisaDetail,
      })
      globalThis.fetch = fetchMock as typeof fetch

      await updateVisaDetail(5, {
        visa_type: '  F-1 Student  ',
        interview_date: null,
      })

      expect(fetchMock).toHaveBeenCalledWith(
        '/visa/applications/5/details',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({
            visa_type: 'F-1 Student',
            interview_date: null,
          }),
        }),
      )
    })

    it('forwards a null interview_date to clear an existing interview date', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ...mockVisaDetail, interview_date: null }),
      })
      globalThis.fetch = fetchMock as typeof fetch

      await updateVisaDetail(5, {
        visa_type: 'F-1 Student',
        interview_date: null,
      })

      const body = JSON.parse((fetchMock.mock.calls[0]?.[1]?.body ?? '{}') as string)
      expect(body.interview_date).toBeNull()
    })

    it('surfaces the backend detail message on 422', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: [{ loc: ['body', 'visa_type'], msg: 'Field required' }] }),
      }) as typeof fetch

      await expect(
        updateVisaDetail(5, { visa_type: '', interview_date: null }),
      ).rejects.toMatchObject({
        message: 'Field required',
        status: 422,
      })
    })
=======
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
>>>>>>> origin/main
  })
})
