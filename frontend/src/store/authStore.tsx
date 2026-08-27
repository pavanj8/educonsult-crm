import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { authErrorMessage, fetchMe, login as loginApi, refresh as refreshApi } from '../api/auth'
import { registerStudent as registerStudentApi } from '../api/students'
import type { AuthUser } from '../types/auth'
import type { RegisterStudentRequest } from '../types/student'
import { clearTokens, getRefreshToken, hasAccessToken, setTokens } from './authStorage'

type AuthContextValue = {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  registerStudent: (payload: RegisterStudentRequest) => Promise<void>
  logout: () => void
  /**
   * True once the user has deliberately signed out in this browsing session,
   * as opposed to simply never having signed in. ProtectedRoute uses it to
   * choose between the landing page (a visitor) and the login form (someone
   * who just left, most likely to come back as a different user). Resets on a
   * page load, so a returning visitor is not permanently routed past the
   * landing page.
   */
  hasSignedOut: boolean
  refreshSession: () => Promise<boolean>
  clearError: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hasSignedOut, setHasSignedOut] = useState(false)

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
    setError(null)
    setHasSignedOut(true)
  }, [])

  const refreshSession = useCallback(async (): Promise<boolean> => {
    const refreshToken = getRefreshToken()
    if (!refreshToken) {
      logout()
      return false
    }

    try {
      const tokens = await refreshApi(refreshToken)
      setTokens(tokens.access_token, tokens.refresh_token)
      const profile = await fetchMe()
      setUser(profile)
      setError(null)
      return true
    } catch {
      logout()
      return false
    }
  }, [logout])

  const loadUser = useCallback(async () => {
    if (!hasAccessToken()) {
      setUser(null)
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    try {
      const profile = await fetchMe()
      setUser(profile)
      setError(null)
    } catch (err) {
      const refreshed = await refreshSession()
      if (!refreshed) {
        setError(authErrorMessage(err, 'Session expired'))
      }
    } finally {
      setIsLoading(false)
    }
  }, [refreshSession])

  useEffect(() => {
    void loadUser()
  }, [loadUser])

  const login = useCallback(
    async (email: string, password: string) => {
      setIsLoading(true)
      setError(null)
      try {
        const tokens = await loginApi({ email, password })
        if (typeof tokens.access_token !== 'string' || tokens.access_token.length === 0) {
          throw new Error('Unable to sign in')
        }
        setTokens(tokens.access_token, tokens.refresh_token)
        const profile = await fetchMe()
        setUser(profile)
      } catch (err) {
        logout()
        const message =
          err instanceof Error && err.message.length > 0
            ? err.message
            : authErrorMessage(err, 'Invalid email or password')
        setError(message)
        throw err
      } finally {
        setIsLoading(false)
      }
    },
    [logout],
  )

  const registerStudent = useCallback(
    async (payload: RegisterStudentRequest) => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await registerStudentApi(payload)
        if (typeof response.access_token !== 'string' || response.access_token.length === 0) {
          throw new Error('Unable to create account')
        }
        setTokens(response.access_token, response.refresh_token)
        const profile = await fetchMe()
        setUser(profile)
      } catch (err) {
        logout()
        const message =
          err instanceof Error && err.message.length > 0
            ? err.message
            : authErrorMessage(err, 'Unable to create account')
        setError(message)
        throw err
      } finally {
        setIsLoading(false)
      }
    },
    [logout],
  )

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      error,
      login,
      registerStudent,
      logout,
      // Derived rather than reset at each of the four places a session can be
      // established (login, register, refresh, restore-on-load): you cannot be
      // signed out while signed in, so a successful auth clears it for free.
      hasSignedOut: user === null && hasSignedOut,
      refreshSession,
      clearError,
    }),
    [
      user,
      isLoading,
      error,
      login,
      registerStudent,
      logout,
      hasSignedOut,
      refreshSession,
      clearError,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
