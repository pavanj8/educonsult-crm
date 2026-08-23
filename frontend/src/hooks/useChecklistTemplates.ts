/** Hook for E15 checklist template admin CRUD (Journey J8; sibling #132).

Wraps the ``/checklist-templates/admin/templates`` CRUD client with the
same patterns as :mod:`useMasterDataAdmin`:

* A list state (items / loading / error / reload) owned by the page.
* A single ``submitting`` flag for create/update so the create and
  edit forms can both render the same "Saving…" affordance.
* A single ``deletingId`` flag so the row can flip into a busy state
  without disabling the whole table.
* Three separate error slots (``createError`` / ``updateError`` /
  ``deleteError``) that mirror the master-data admin UI so the page
  can render them above the form.

The page is responsible for the actual form / table rendering; this
hook only owns the data + the network surface. The hook also kicks
off the initial ``GET`` on mount so the page can render the table
without having to wire its own ``useEffect`` (mirroring
:mod:`useMasterDataAdmin`'s ``useLoadableList``).
*/

import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import {
  createAdminChecklistItemTemplate,
  deleteAdminChecklistItemTemplate,
  fetchAdminChecklistItemTemplates,
  updateAdminChecklistItemTemplate,
} from '../api/checklist'
import type {
  ChecklistItemTemplate,
  ChecklistItemTemplateCreateRequest,
  ChecklistItemTemplateUpdateRequest,
} from '../types/checklist'
import { hasAccessToken } from '../store/authStorage'

export interface UseChecklistTemplatesResult {
  templates: ChecklistItemTemplate[]
  loading: boolean
  error: string | null
  createError: string | null
  updateError: string | null
  deleteError: string | null
  submitting: boolean
  deletingId: number | null
  reload: () => Promise<void>
  createTemplate: (
    payload: ChecklistItemTemplateCreateRequest,
  ) => Promise<ChecklistItemTemplate>
  updateTemplate: (
    id: number,
    payload: ChecklistItemTemplateUpdateRequest,
  ) => Promise<ChecklistItemTemplate>
  deleteTemplate: (id: number) => Promise<void>
  clearErrors: () => void
}

export function useChecklistTemplates(): UseChecklistTemplatesResult {
  const [templates, setTemplates] = useState<ChecklistItemTemplate[]>([])
  const [loading, setLoading] = useState<boolean>(hasAccessToken())
  const [error, setError] = useState<string | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)
  const [updateError, setUpdateError] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const reload = useCallback(async () => {
    if (!hasAccessToken()) {
      setTemplates([])
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const data = await fetchAdminChecklistItemTemplates()
      setTemplates(data)
    } catch (err) {
      if (isApiError(err) && (err.status === 401 || err.status === 403)) {
        setError('You do not have permission to manage checklist templates')
      } else {
        setError('Failed to load checklist templates')
      }
      setTemplates([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  function setCreateErrorFromException(err: unknown, fallback: string) {
    if (isApiError(err)) {
      setCreateError(err.message)
    } else {
      setCreateError(fallback)
    }
  }

  function setUpdateErrorFromException(err: unknown, fallback: string) {
    if (isApiError(err)) {
      setUpdateError(err.message)
    } else {
      setUpdateError(fallback)
    }
  }

  function setDeleteErrorFromException(err: unknown, fallback: string) {
    if (isApiError(err)) {
      setDeleteError(err.message)
    } else {
      setDeleteError(fallback)
    }
  }

  const createTemplate = useCallback(
    async (payload: ChecklistItemTemplateCreateRequest) => {
      setSubmitting(true)
      setCreateError(null)
      try {
        const created = await createAdminChecklistItemTemplate(payload)
        setTemplates((current) => [...current, created])
        return created
      } catch (err) {
        setCreateErrorFromException(err, 'Failed to create checklist template')
        throw err
      } finally {
        setSubmitting(false)
      }
    },
    [],
  )

  const updateTemplate = useCallback(
    async (id: number, payload: ChecklistItemTemplateUpdateRequest) => {
      setSubmitting(true)
      setUpdateError(null)
      try {
        const updated = await updateAdminChecklistItemTemplate(id, payload)
        setTemplates((current) =>
          current.map((item) => (item.id === id ? updated : item)),
        )
        return updated
      } catch (err) {
        setUpdateErrorFromException(err, 'Failed to update checklist template')
        throw err
      } finally {
        setSubmitting(false)
      }
    },
    [],
  )

  const deleteTemplate = useCallback(async (id: number) => {
    setDeletingId(id)
    setDeleteError(null)
    try {
      await deleteAdminChecklistItemTemplate(id)
      setTemplates((current) => current.filter((item) => item.id !== id))
    } catch (err) {
      setDeleteErrorFromException(err, 'Failed to delete checklist template')
      throw err
    } finally {
      setDeletingId(null)
    }
  }, [])

  function clearErrors() {
    setCreateError(null)
    setUpdateError(null)
    setDeleteError(null)
  }

  return {
    templates,
    loading,
    error,
    createError,
    updateError,
    deleteError,
    submitting,
    deletingId,
    reload,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    clearErrors,
  }
}
