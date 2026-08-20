import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import { fetchCountries, fetchPrograms, fetchUniversities } from '../api/masterData'
import type { Country, Program, University } from '../types/masterData'

type UseMasterDataListOptions = {
  enabled?: boolean
}

function useMasterDataList<T>(
  load: () => Promise<T[]>,
  enabled: boolean,
  emptyErrorMessage: string,
): {
  items: T[]
  loading: boolean
  error: string | null
  reload: () => Promise<void>
} {
  const [items, setItems] = useState<T[]>([])
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    if (!enabled) {
      setItems([])
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const data = await load()
      setItems(data)
    } catch (err) {
      if (isApiError(err) && err.status === 404) {
        setError('Consultancy not found')
      } else {
        setError(emptyErrorMessage)
      }
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [enabled, emptyErrorMessage, load])

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
