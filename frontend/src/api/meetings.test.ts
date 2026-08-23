import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  listMeetingsForApplication,
  listMyMeetings,
  scheduleMeeting,
  updateMeeting,
} from './meetings'

const baseMeeting = {
  id: 99,
  tenant_id: 10,
  application_id: 5,
  counselor_id: 7,
  student_id: 42,
  scheduled_at: '2026-05-01T09:30:00Z',
  duration_minutes: 30,
  location: 'Room 2',
  notes: 'Bring documents',
  created_at: '2026-04-01T09:00:00Z',
  updated_at: '2026-04-01T09:00:00Z',
}

describe('meetings API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('listMeetingsForApplication sends bearer token', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [baseMeeting],
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await listMeetingsForApplication(5)

    expect(result).toEqual([baseMeeting])
    expect(fetchMock).toHaveBeenCalledWith('/applications/5/meetings', {
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer test-token' },
    })
  })

  it('listMeetingsForApplication surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    await expect(listMeetingsForApplication(5)).rejects.toMatchObject({
      message: 'Insufficient permissions',
      status: 403,
    })
  })

  it('scheduleMeeting posts payload with auth header', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => baseMeeting,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const payload = {
      scheduled_at: '2026-05-01T09:30:00Z',
      duration_minutes: 30,
      location: 'Room 2',
      notes: null,
    }
    const result = await scheduleMeeting(5, payload)

    expect(result).toEqual(baseMeeting)
    expect(fetchMock).toHaveBeenCalledWith('/applications/5/meetings', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer test-token' },
    })
  })

  it('scheduleMeeting surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'scheduled_at must be a future timestamp' }),
    }) as typeof fetch

    await expect(
      scheduleMeeting(5, {
        scheduled_at: '2020-01-01T00:00:00Z',
        duration_minutes: 30,
        location: null,
        notes: null,
      }),
    ).rejects.toMatchObject({
      message: 'scheduled_at must be a future timestamp',
      status: 422,
    })
  })

  it('updateMeeting patches the payload to /meetings/{id}', async () => {
    localStorage.setItem('access_token', 'test-token')
    const updated = { ...baseMeeting, scheduled_at: '2026-06-01T09:30:00Z' }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => updated,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await updateMeeting(99, { scheduled_at: '2026-06-01T09:30:00Z' })

    expect(result).toEqual(updated)
    expect(fetchMock).toHaveBeenCalledWith('/meetings/99', {
      method: 'PATCH',
      body: JSON.stringify({ scheduled_at: '2026-06-01T09:30:00Z' }),
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer test-token' },
    })
  })

  it('updateMeeting surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Meeting not found' }),
    }) as typeof fetch

    await expect(updateMeeting(99, { notes: 'x' })).rejects.toMatchObject({
      message: 'Meeting not found',
      status: 404,
    })
  })

  it('listMyMeetings hits /me/meetings with the bearer token', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [baseMeeting],
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await listMyMeetings()

    expect(result).toEqual([baseMeeting])
    expect(fetchMock).toHaveBeenCalledWith('/me/meetings', {
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer test-token' },
    })
  })

  it('listMyMeetings surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'test-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Insufficient permissions' }),
    }) as typeof fetch

    await expect(listMyMeetings()).rejects.toMatchObject({
      message: 'Insufficient permissions',
      status: 403,
    })
  })
})
