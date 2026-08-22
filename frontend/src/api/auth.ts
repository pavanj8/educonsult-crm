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

export interface ForgotPasswordPayload {
  email: string
}

export interface ForgotPasswordResponse {
  message: string
}

export interface ResetPasswordPayload {
  token: string
  new_password: string
}

export interface ResetPasswordResponse {
  message: string
}

/**
 * Request a password-reset email (E6; Journey J45).
 *
 * The backend always returns the same generic 200 response regardless
 * of whether the address is registered, so callers cannot use this
 * endpoint to enumerate accounts. Errors here therefore indicate a
 * genuine delivery / transport failure surfaced by the backend (503).
 */
export async function requestPasswordReset(
  payload: ForgotPasswordPayload,
): Promise<ForgotPasswordResponse> {
  return apiFetch<ForgotPasswordResponse>('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify(payload),
    skipAuth: true,
  })
}

/**
 * Exchange a one-shot reset token (received via the reset email) for
 * a new password (E6; Journey J45). Invalid / expired / consumed
 * tokens surface as a 400 from the backend.
 */
export async function submitPasswordReset(
  payload: ResetPasswordPayload,
): Promise<ResetPasswordResponse> {
  return apiFetch<ResetPasswordResponse>('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify(payload),
    skipAuth: true,
  })
}

export function authErrorMessage(err: unknown, fallback: string): string {
  if (isApiError(err)) {
    return err.message
  }
  return fallback
}
