/** Admin CRUD hook for master data (E14; Journey J7). */

import { useCallback, useEffect, useState } from 'react'

import { isApiError } from '../api/client'
import {
  createAdminCountry,
  createAdminProgram,
  createAdminUniversity,
  deleteAdminCountry,
  deleteAdminProgram,
  deleteAdminUniversity,
  fetchAdminCountries,
  fetchAdminPrograms,
  fetchAdminUniversities,
  updateAdminCountry,
  updateAdminProgram,
  updateAdminUniversity,
} from '../api/masterData'
import { hasAccessToken } from '../store/authStorage'
import type {
  Country,
  CountryCreateRequest,
  CountryUpdateRequest,
  Program,
  ProgramCreateRequest,
  ProgramUpdateRequest,
  University,
  UniversityCreateRequest,
  UniversityUpdateRequest,
} from '../types/masterData'

type LoadableListOptions = {
  enabled?: boolean
}

function useLoadableList<T>(
  load: () => Promise<T[]>,
  enabled: boolean,
  defaultErrorMessage: string,
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
    if (!enabled || !hasAccessToken()) {
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
      if (isApiError(err) && (err.status === 401 || err.status === 403)) {
        setError('You do not have permission to view master data')
      } else {
        setError(defaultErrorMessage)
      }
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [defaultErrorMessage, enabled, load])

  useEffect(() => {
    void reload()
  }, [reload])

  return { items, loading, error, reload }
}

export function useMasterDataAdmin(options: LoadableListOptions = {}) {
  const enabled = options.enabled ?? true

  const countriesState = useLoadableList<Country>(
    useCallback(() => fetchAdminCountries(), []),
    enabled,
    'Failed to load countries',
  )
  const universitiesState = useLoadableList<University>(
    useCallback(() => fetchAdminUniversities(), []),
    enabled,
    'Failed to load universities',
  )
  const programsState = useLoadableList<Program>(
    useCallback(() => fetchAdminPrograms(), []),
    enabled,
    'Failed to load programs',
  )

  const [createError, setCreateError] = useState<string | null>(null)
  const [updateError, setUpdateError] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)

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

  const createCountry = useCallback(async (payload: CountryCreateRequest) => {
    setSubmitting(true)
    setCreateError(null)
    try {
      const created = await createAdminCountry(payload)
      countriesState.reload()
      return created
    } catch (err) {
      setCreateErrorFromException(err, 'Failed to create country')
      throw err
    } finally {
      setSubmitting(false)
    }
    // countriesState.reload is stable enough across renders because
    // the linter is unaware that the inner hook re-creates it on
    // each render — disabling here keeps the dep list focused on the
    // actual API dependencies.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const updateCountry = useCallback(
    async (id: number, payload: CountryUpdateRequest) => {
      setSubmitting(true)
      setUpdateError(null)
      try {
        const updated = await updateAdminCountry(id, payload)
        countriesState.reload()
        return updated
      } catch (err) {
        setUpdateErrorFromException(err, 'Failed to update country')
        throw err
      } finally {
        setSubmitting(false)
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [],
  )

  const deleteCountry = useCallback(async (id: number) => {
    setDeletingId(id)
    setDeleteError(null)
    try {
      await deleteAdminCountry(id)
      countriesState.reload()
      universitiesState.reload()
      programsState.reload()
    } catch (err) {
      setDeleteErrorFromException(err, 'Failed to delete country')
      throw err
    } finally {
      setDeletingId(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const createUniversity = useCallback(async (payload: UniversityCreateRequest) => {
    setSubmitting(true)
    setCreateError(null)
    try {
      const created = await createAdminUniversity(payload)
      universitiesState.reload()
      return created
    } catch (err) {
      setCreateErrorFromException(err, 'Failed to create university')
      throw err
    } finally {
      setSubmitting(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const updateUniversity = useCallback(
    async (id: number, payload: UniversityUpdateRequest) => {
      setSubmitting(true)
      setUpdateError(null)
      try {
        const updated = await updateAdminUniversity(id, payload)
        universitiesState.reload()
        programsState.reload()
        return updated
      } catch (err) {
        setUpdateErrorFromException(err, 'Failed to update university')
        throw err
      } finally {
        setSubmitting(false)
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [],
  )

  const deleteUniversity = useCallback(async (id: number) => {
    setDeletingId(id)
    setDeleteError(null)
    try {
      await deleteAdminUniversity(id)
      universitiesState.reload()
      programsState.reload()
    } catch (err) {
      setDeleteErrorFromException(err, 'Failed to delete university')
      throw err
    } finally {
      setDeletingId(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const createProgram = useCallback(async (payload: ProgramCreateRequest) => {
    setSubmitting(true)
    setCreateError(null)
    try {
      const created = await createAdminProgram(payload)
      programsState.reload()
      return created
    } catch (err) {
      setCreateErrorFromException(err, 'Failed to create program')
      throw err
    } finally {
      setSubmitting(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const updateProgram = useCallback(async (id: number, payload: ProgramUpdateRequest) => {
    setSubmitting(true)
    setUpdateError(null)
    try {
      const updated = await updateAdminProgram(id, payload)
      programsState.reload()
      return updated
    } catch (err) {
      setUpdateErrorFromException(err, 'Failed to update program')
      throw err
    } finally {
      setSubmitting(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const deleteProgram = useCallback(async (id: number) => {
    setDeletingId(id)
    setDeleteError(null)
    try {
      await deleteAdminProgram(id)
      programsState.reload()
    } catch (err) {
      setDeleteErrorFromException(err, 'Failed to delete program')
      throw err
    } finally {
      setDeletingId(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function clearErrors() {
    setCreateError(null)
    setUpdateError(null)
    setDeleteError(null)
  }

  return {
    countries: countriesState.items,
    universities: universitiesState.items,
    programs: programsState.items,
    countriesLoading: countriesState.loading,
    universitiesLoading: universitiesState.loading,
    programsLoading: programsState.loading,
    countriesError: countriesState.error,
    universitiesError: universitiesState.error,
    programsError: programsState.error,
    createError,
    updateError,
    deleteError,
    submitting,
    deletingId,
    reload: () =>
      Promise.all([
        countriesState.reload(),
        universitiesState.reload(),
        programsState.reload(),
      ]).then(() => undefined),
    createCountry,
    updateCountry,
    deleteCountry,
    createUniversity,
    updateUniversity,
    deleteUniversity,
    createProgram,
    updateProgram,
    deleteProgram,
    clearErrors,
  }
}