import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createStudentByReceptionist } from './receptionistIntake'

const mockIntakeResponse = {
  id: 99,
  email: 'walkin.student@example.test',
  tenant_id: 10,
  branch_id: 1,
  name: 'Aarav Sharma',
  phone: '+91-9876543210',
  date_of_birth: '2001-03-04',
  target_country_id: 1,
  target_university_id: 10,
  target_program_id: 100,
  created_at: '2026-01-01T00:00:00Z',
}

const validPayload = {
  branch_id: 1,
  email: 'walkin.student@example.test',
  password: 'Welcome1!',
  name: 'Aarav Sharma',
  phone: '+91-9876543210',
  date_of_birth: '2001-03-04',
  target_country_id: 1,
  target_university_id: 10,
  target_program_id: 100,
}

describe('receptionist intake API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('createStudentByReceptionist posts payload with auth header', async () => {
    localStorage.setItem('access_token', 'test-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockIntakeResponse,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await createStudentByReceptionist(validPayload)

    expect(result).toEqual(mockIntakeResponse)
    expect(fetchMock).toHaveBeenCalledWith('/students', {
      method: 'POST',
      body: JSON.stringify(validPayload),
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer test-access-token',
      },
    })
  })

  it('createStudentByReceptionist surfaces backend error detail on failure', async () => {
    localStorage.setItem('access_token', 'test-access-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'Email already registered' }),
    }) as typeof fetch

    await expect(createStudentByReceptionist(validPayload)).rejects.toMatchObject({
      message: 'Email already registered',
      status: 409,
    })
  })

  it('createStudentByReceptionist omits optional study preference ids when not provided', async () => {
    localStorage.setItem('access_token', 'test-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockIntakeResponse,
    })
    globalThis.fetch = fetchMock as typeof fetch

    await createStudentByReceptionist({
      branch_id: 1,
      email: 'walkin.student@example.test',
      password: 'Welcome1!',
      name: 'Aarav Sharma',
      phone: '+91-9876543210',
      date_of_birth: '2001-03-04',
    })

    expect(fetchMock).toHaveBeenCalledWith('/students', {
      method: 'POST',
      body: JSON.stringify({
        branch_id: 1,
        email: 'walkin.student@example.test',
        password: 'Welcome1!',
        name: 'Aarav Sharma',
        phone: '+91-9876543210',
        date_of_birth: '2001-03-04',
      }),
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer test-access-token',
      },
    })
  })
})