import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

import { AuthProvider, useAuth } from './authStore'

const mockUser = {
  id: 1,
  email: 'counselor@demo.test',
  role: 'counselor' as const,
  tenant_id: 10,
  branch_id: 1,
}

const mockTokens = {
  access_token: 'access-token',
  refresh_token: 'refresh-token',
  token_type: 'bearer',
}

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('starts unauthenticated when no tokens are stored', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
  })

  it('loads user profile when access token is present', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user).toEqual(mockUser)
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/auth/me',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer stored-access-token',
        }),
      }),
    )
  })

  it('login stores tokens and user profile', async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTokens,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUser,
      }) as typeof fetch

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    await result.current.login('counselor@demo.test', 'demo-password')

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    expect(localStorage.getItem('access_token')).toBe('access-token')
    expect(localStorage.getItem('refresh_token')).toBe('refresh-token')
    expect(result.current.user).toEqual(mockUser)
    expect(result.current.error).toBeNull()
  })

  it('login sets error and clears tokens on failure', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Invalid email or password' }),
    }) as typeof fetch

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    await expect(result.current.login('bad@example.test', 'wrong')).rejects.toThrow()

    await waitFor(() => {
      expect(result.current.error).toBe('Invalid email or password')
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('login rejects responses missing access_token', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ refresh_token: 'refresh-only' }),
    }) as typeof fetch

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    await expect(result.current.login('counselor@demo.test', 'demo-password')).rejects.toThrow()

    await waitFor(() => {
      expect(result.current.error).toBe('Unable to sign in')
    })

    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('logout clears tokens and user state', async () => {
    localStorage.setItem('access_token', 'stored-access-token')
    localStorage.setItem('refresh_token', 'stored-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    result.current.logout()

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(false)
    })

    expect(result.current.user).toBeNull()
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })

  it('refreshSession exchanges refresh token and reloads profile', async () => {
    localStorage.setItem('access_token', 'current-access-token')
    localStorage.setItem('refresh_token', 'valid-refresh-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUser,
    }) as typeof fetch

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          access_token: 'new-access-token',
          refresh_token: 'new-refresh-token',
          token_type: 'bearer',
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUser,
      }) as typeof fetch

    const refreshed = await result.current.refreshSession()

    expect(refreshed).toBe(true)
    expect(localStorage.getItem('access_token')).toBe('new-access-token')
    expect(localStorage.getItem('refresh_token')).toBe('new-refresh-token')
    expect(result.current.user).toEqual(mockUser)
  })

  it('attempts refresh when fetchMe fails with expired access token', async () => {
    localStorage.setItem('access_token', 'expired-access-token')
    localStorage.setItem('refresh_token', 'valid-refresh-token')
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Access token has expired' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          access_token: 'new-access-token',
          refresh_token: 'new-refresh-token',
          token_type: 'bearer',
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUser,
      }) as typeof fetch

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    expect(result.current.user).toEqual(mockUser)
    expect(globalThis.fetch).toHaveBeenCalledTimes(3)
  })
})
