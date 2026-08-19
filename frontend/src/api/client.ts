import { getAccessToken } from '../store/authStorage'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export type ApiError = Error & { status: number }

type ApiFetchInit = RequestInit & {
  skipAuth?: boolean
}

function createApiError(message: string, status: number): ApiError {
  const error = new Error(message) as ApiError
  error.name = 'ApiError'
  error.status = status
  return error
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof Error && 'status' in err && typeof (err as ApiError).status === 'number'
}

function authHeaders(): HeadersInit {
  const token = getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string | Array<{ msg?: string }> }
    if (typeof body.detail === 'string') {
      return body.detail
    }
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      return body.detail[0]?.msg ?? 'Request failed'
    }
  } catch {
    // Fall through to status-based defaults.
  }

  if (response.status === 401 || response.status === 403) {
    return 'Not authenticated'
  }
  return 'Request failed'
}

export async function apiFetch<T>(path: string, init?: ApiFetchInit): Promise<T> {
  const { skipAuth = false, ...requestInit } = init ?? {}
  const response = await fetch(`${API_BASE}${path}`, {
    ...requestInit,
    headers: {
      'Content-Type': 'application/json',
      ...(skipAuth ? {} : authHeaders()),
      ...requestInit.headers,
    },
  })

  if (!response.ok) {
    throw createApiError(await parseErrorMessage(response), response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}
