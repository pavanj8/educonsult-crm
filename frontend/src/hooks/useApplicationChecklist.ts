import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import { fetchApplicationChecklist } from '../api/checklist'
import type { ChecklistItem } from '../types/checklist'

import { hasAccessToken } from '../store/authStorage'

/**
 * Hook return shape for {@link useApplicationChecklist}.
 *
 * ``items`` is sorted by ``(orderIndex NULLS LAST, templateId)`` as
 * returned by the backend (ADR-0012: stable list ordering at the API
 * boundary), so the consumer can render the list directly.
 */
export interface UseApplicationChecklistResult {
  items: ChecklistItem[]
  loading: boolean
  error: string | null
  reload: () => Promise<void>
}

/**
 * Load the document checklist (templates + latest upload status) for
 * one application (E26; Journey J19).
 *
 * Behaviour mirrors the other resource hooks in this codebase
 * (``useNotifications``, ``useApplications``): skip the fetch when no
 * access token is present, surface a 401/403-specific error so the UI
 * can prompt the user to sign in, and fall back to a generic message
 * for every other failure (network, 5xx, ...).
 *
 * The fetch is keyed on ``applicationId`` so callers can swap
 * applications (e.g. one per row in the student dashboard) without
 * tearing the component down. A new fetch replaces the previous
 * ``items`` with the new application's items.
 */
export function useApplicationChecklist(
  applicationId: number | null,
): UseApplicationChecklistResult {
  const [items, setItems] = useState<ChecklistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (applicationId == null || !hasAccessToken()) {
      setItems([])
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const data = await fetchApplicationChecklist({ applicationId })
      setItems(data.items ?? [])
    } catch (err) {
      if (isApiError(err) && (err.status === 401 || err.status === 403)) {
        setError('Sign in to view the document checklist')
      } else {
        setError('Failed to load the document checklist')
      }
    } finally {
      setLoading(false)
    }
  }, [applicationId])

  useEffect(() => {
    void load()
  }, [load])

  return { items, loading, error, reload: load }
}