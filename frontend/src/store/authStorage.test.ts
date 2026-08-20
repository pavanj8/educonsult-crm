import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  hasAccessToken,
  setTokens,
} from './authStorage'

describe('authStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('stores and retrieves access and refresh tokens', () => {
    setTokens('access-token', 'refresh-token')

    expect(getAccessToken()).toBe('access-token')
    expect(getRefreshToken()).toBe('refresh-token')
    expect(hasAccessToken()).toBe(true)
  })

  it('clears stored tokens', () => {
    setTokens('access-token', 'refresh-token')

    clearTokens()

    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
    expect(hasAccessToken()).toBe(false)
  })
})
