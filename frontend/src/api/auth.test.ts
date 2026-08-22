import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchMe, login, refresh, requestPasswordReset, submitPasswordReset } from './auth'

const mockUser = {
  id: 1,
  email: 'counselor@demo.test',
  role: 'counselor',
  tenant_id: 10,
  branch_id: 1,
}

const mockTokens = {
  access_token: 'access-token',
  refresh_token: 'refresh-token',
  token_type: 'bearer',
}

describe('auth API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('login posts credentials without auth header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockTokens,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await login({ email: 'counselor@demo.test', password: 'demo-password' })

    expect(result).toEqual(mockTokens)
    expect(fetchMock).toHaveBeenCalledWith('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: 'counselor@demo.test', password: 'demo-password' }),
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('login surfaces backend error detail on failure', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Invalid email or password' }),
    }) as typeof fetch

    await expect(login({ email: 'bad@example.test', password: 'wrong' })).rejects.toMatchObject({
      message: 'Invalid email or password',
      status: 401,
    })
  })

  it('refresh posts refresh token without auth header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockTokens,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await refresh('old-refresh-token')

    expect(result).toEqual(mockTokens)
    expect(fetchMock).toHaveBeenCalledWith('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: 'old-refresh-token' }),
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('fetchMe sends bearer token from storage', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await fetchMe()

    expect(result).toEqual(mockUser)
    expect(fetchMock).toHaveBeenCalledWith('/auth/me', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer stored-access-token',
      },
    })
  })

  it('fetchMe returns auth error detail on 401', async () => {
    localStorage.setItem('access_token', 'expired-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Access token has expired' }),
    }) as typeof fetch

    await expect(fetchMe()).rejects.toMatchObject({
      message: 'Access token has expired',
      status: 401,
    })
  })

  it('requestPasswordReset posts email without auth header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        message: 'If an account exists for that email, a reset link has been sent.',
      }),
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await requestPasswordReset({ email: 'counselor@demo.test' })

    expect(result).toEqual({
      message: 'If an account exists for that email, a reset link has been sent.',
    })
    expect(fetchMock).toHaveBeenCalledWith('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email: 'counselor@demo.test' }),
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('requestPasswordReset surfaces backend error on delivery failure', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Unable to send password reset email' }),
    }) as typeof fetch

    await expect(
      requestPasswordReset({ email: 'counselor@demo.test' }),
    ).rejects.toMatchObject({
      message: 'Unable to send password reset email',
      status: 503,
    })
  })

  it('submitPasswordReset posts token + new password without auth header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: 'Your password has been reset successfully.' }),
    })
    globalThis.fetch = fetchMock as typeof fetch

    const result = await submitPasswordReset({
      token: 'reset-token',
      new_password: 'new-strong-password',
    })

    expect(result).toEqual({ message: 'Your password has been reset successfully.' })
    expect(fetchMock).toHaveBeenCalledWith('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token: 'reset-token', new_password: 'new-strong-password' }),
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('submitPasswordReset surfaces backend error for invalid/expired token', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'Invalid or expired reset token' }),
    }) as typeof fetch

    await expect(
      submitPasswordReset({ token: 'expired-token', new_password: 'new-strong-password' }),
    ).rejects.toMatchObject({
      message: 'Invalid or expired reset token',
      status: 400,
    })
  })
})
