import { apiFetch, isApiError } from './client'
import type { AuthUser, LoginCredentials, TokenResponse } from '../types/auth'

export async function login(credentials: LoginCredentials): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
    skipAuth: true,
  })
}

export async function refresh(refreshToken: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken }),
    skipAuth: true,
  })
}

export async function fetchMe(): Promise<AuthUser> {
  return apiFetch<AuthUser>('/auth/me')
}

export function authErrorMessage(err: unknown, fallback: string): string {
  if (isApiError(err)) {
    return err.message
  }
  return fallback
}
