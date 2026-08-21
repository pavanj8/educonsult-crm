import { getAccessToken } from '../store/authStorage'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export type ApiError = Error & { status: number }

type ApiFetchInit = RequestInit & {
  skipAuth?: boolean
  /**
   * When ``true`` the helper will not set the ``Content-Type`` JSON
   * header — letting the browser set the boundary for a
   * ``multipart/form-data`` upload (Journey J20). Any caller-provided
   * ``Content-Type`` still wins. Defaults to ``false`` (JSON).
   *
   * Note: callers can also pass ``headers: { 'Content-Type': undefined }``
   * to explicitly clear the default JSON header without flipping
   * ``skipContentType`` — caller-supplied headers are merged last, so
   * the ``undefined`` overwrites the default. This is the same
   * "caller-wins" rule that applies to every other header.
   */
  skipContentType?: boolean
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
  const { skipAuth = false, skipContentType = false, ...requestInit } = init ?? {}
  const headers: Record<string, string> = {}
  if (!skipContentType) {
    headers['Content-Type'] = 'application/json'
  }
  Object.assign(headers, skipAuth ? {} : authHeaders())
  // Caller-provided headers always win last (lets them pass an explicit
  // ``Content-Type`` for multipart or ``undefined`` to clear the default).
  Object.assign(headers, requestInit.headers ?? {})

  const response = await fetch(`${API_BASE}${path}`, {
    ...requestInit,
    headers,
  })

  if (!response.ok) {
    throw createApiError(await parseErrorMessage(response), response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}
