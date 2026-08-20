import { beforeEach, describe, expect, it, vi } from 'vitest'

import { registerStudent } from './students'

const mockRegisterResponse = {
  id: 42,
  email: 'new.student@example.test',
  role: 'student',
  tenant_id: 10,
  branch_id: 1,
  name: 'Rahul Kumar',
  phone: '+91-9876543210',
  date_of_birth: '2000-05-15',
  target_country_id: null,
  target_university_id: null,
  target_program_id: null,
  access_token: 'access-token',
  refresh_token: 'refresh-token',
  token_type: 'bearer',
  created_at: '2026-01-01T00:00:00Z',
}

const validPayload = {
  tenant_slug: 'apex',
  branch_id: 1,
  email: 'new.student@example.test',
  password: 'StudentPass1!',
  name: 'Rahul Kumar',
  phone: '+91-9876543210',
  date_of_birth: '2000-05-15',
}

describe('students API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('registerStudent posts payload without auth header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockRegisterResponse,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await registerStudent(validPayload)

    expect(result).toEqual(mockRegisterResponse)
    expect(fetchMock).toHaveBeenCalledWith('/auth/register-student', {
      method: 'POST',
      body: JSON.stringify(validPayload),
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('registerStudent surfaces backend error detail on failure', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'Email already registered' }),
    }) as typeof fetch

    await expect(registerStudent(validPayload)).rejects.toMatchObject({
      message: 'Email already registered',
      status: 409,
    })
  })

  it('registerStudent surfaces validation error detail on 422', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [{ loc: ['body', 'password'], msg: 'Password is too weak', type: 'value_error' }],
      }),
    }) as typeof fetch

    await expect(registerStudent(validPayload)).rejects.toMatchObject({
      message: 'Password is too weak',
      status: 422,
    })
  })
})
