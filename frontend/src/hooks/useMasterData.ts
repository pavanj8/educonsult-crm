import { useCallback, useEffect, useRef, useState } from 'react'

import { isApiError } from '../api/client'
import { fetchCountries, fetchPrograms, fetchUniversities } from '../api/masterData'
import type { Country, Program, University } from '../types/masterData'

type UseMasterDataListOptions = {
  enabled?: boolean
  notFoundMessage?: string
}

function useMasterDataList<T>(
  load: () => Promise<T[]>,
  enabled: boolean,
  emptyErrorMessage: string,
  notFoundMessage?: string,
): {
  items: T[]
  loading: boolean
  error: string | null
  reload: () => Promise<void>
} {
  const [items, setItems] = useState<T[]>([])
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<string | null>(null)
  const requestGenerationRef = useRef(0)

  const reload = useCallback(async () => {
    if (!enabled) {
      setItems([])
      setLoading(false)
      setError(null)
      return
    }

    const generation = requestGenerationRef.current + 1
    requestGenerationRef.current = generation
    setLoading(true)
    setError(null)
    try {
      const data = await load()
      if (requestGenerationRef.current !== generation) {
        return
      }
      setItems(data)
    } catch (err) {
      if (requestGenerationRef.current !== generation) {
        return
      }
      if (isApiError(err) && err.status === 404 && notFoundMessage) {
        setError(notFoundMessage)
      } else if (isApiError(err) && err.status === 404) {
        setError(emptyErrorMessage)
      } else {
        setError(emptyErrorMessage)
      }
      setItems([])
    } finally {
      if (requestGenerationRef.current === generation) {
        setLoading(false)
      }
    }
  }, [enabled, emptyErrorMessage, load, notFoundMessage])

  useEffect(() => {
    void reload()
  }, [reload])

  return { items, loading, error, reload }
}

export function useCountries(tenantSlug: string, options: UseMasterDataListOptions = {}) {
  const enabled = (options.enabled ?? true) && tenantSlug.trim().length > 0
  const slug = tenantSlug.trim()

  return useMasterDataList<Country>(
    useCallback(() => fetchCountries(slug), [slug]),
    enabled,
    'Failed to load countries',
    options.notFoundMessage ?? 'Consultancy not found',
  )
}

export function useUniversities(
  tenantSlug: string,
  countryId: number | '',
  options: UseMasterDataListOptions = {},
) {
  const enabled =
    (options.enabled ?? true) && tenantSlug.trim().length > 0 && typeof countryId === 'number'
  const slug = tenantSlug.trim()

  return useMasterDataList<University>(
    useCallback(
      () => fetchUniversities(slug, countryId as number),
      [slug, countryId],
    ),
    enabled,
    'Failed to load universities',
  )
}

export function usePrograms(
  tenantSlug: string,
  universityId: number | '',
  options: UseMasterDataListOptions = {},
) {
  const enabled =
    (options.enabled ?? true) &&
    tenantSlug.trim().length > 0 &&
    typeof universityId === 'number'
  const slug = tenantSlug.trim()

  return useMasterDataList<Program>(
    useCallback(
      () => fetchPrograms(slug, universityId as number),
      [slug, universityId],
    ),
    enabled,
    'Failed to load programs',
  )
}

export function useDebouncedTenantSlug(rawSlug: string, delayMs = 300): string {
  const [debouncedSlug, setDebouncedSlug] = useState(() => rawSlug.trim())

  useEffect(() => {
    const trimmed = rawSlug.trim()
    const timeoutId = window.setTimeout(() => {
      setDebouncedSlug(trimmed)
    }, delayMs)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [delayMs, rawSlug])

  return debouncedSlug
}
