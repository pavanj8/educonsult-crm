const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export type ApiError = Error & { status: number }

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
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function errorMessageForStatus(status: number): string {
  if (status === 401 || status === 403) {
    return 'Sign in to view notifications'
  }
  return 'Failed to load notifications'
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    throw createApiError(errorMessageForStatus(response.status), response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}
