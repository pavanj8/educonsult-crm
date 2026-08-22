/** Master data admin UI with tabs (E14; Journey J7). */

import { useId, useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../api/client'
import { useMasterDataAdmin } from '../hooks/useMasterDataAdmin'
import type {
  Country,
  Program,
  University,
} from '../types/masterData'

type TabKey = 'countries' | 'universities' | 'programs'

const TAB_LABELS: Record<TabKey, string> = {
  countries: 'Countries',
  universities: 'Universities',
  programs: 'Programs',
}

const TAB_ORDER: TabKey[] = ['countries', 'universities', 'programs']

function countryNameFor(countries: Country[], countryId: number): string {
  const country = countries.find((item) => item.id === countryId)
  return country?.name ?? `Country #${countryId}`
}

function universityNameFor(universities: University[], universityId: number): string {
  const university = universities.find((item) => item.id === universityId)
  return university?.name ?? `University #${universityId}`
}

export default function MasterDataAdminPage() {
  const {
    countries,
    universities,
    programs,
    countriesLoading,
    universitiesLoading,
    programsLoading,
    countriesError,
    universitiesError,
    programsError,
    createError,
    updateError,
    deleteError,
    submitting,
    deletingId,
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
  } = useMasterDataAdmin()
  const [activeTab, setActiveTab] = useState<TabKey>('countries')
  const [editingCountry, setEditingCountry] = useState<Country | null>(null)
  const [editingUniversity, setEditingUniversity] = useState<University | null>(null)
  const [editingProgram, setEditingProgram] = useState<Program | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const tabListId = useId()
  const createErrorId = useId()
  const updateErrorId = useId()
  const deleteErrorId = useId()
  const successId = useId()

  const countriesById = useMemo(() => new Map(countries.map((item) => [item.id, item])), [countries])
  const universitiesById = useMemo(
    () => new Map(universities.map((item) => [item.id, item])),
    [universities],
  )

  function switchTab(next: TabKey) {
    setActiveTab(next)
    setEditingCountry(null)
    setEditingUniversity(null)
    setEditingProgram(null)
    setSuccessMessage(null)
    clearErrors()
  }

  async function handleCreateCountry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSuccessMessage(null)
    clearErrors()
    const formData = new FormData(event.currentTarget)
    const name = String(formData.get('name') ?? '').trim()
    const code = String(formData.get('code') ?? '').trim()
    try {
      const created = await createCountry({ name, code })
      setSuccessMessage(`Country "${created.name}" created.`)
      event.currentTarget.reset()
    } catch (err) {
      if (!isApiError(err)) {
        // createError is set by the hook
      }
    }
  }

  async function handleUpdateCountry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editingCountry) {
      return
    }
    setSuccessMessage(null)
    clearErrors()
    const formData = new FormData(event.currentTarget)
    const nameRaw = formData.get('name')
    const codeRaw = formData.get('code')
    const payload: { name?: string; code?: string } = {}
    if (typeof nameRaw === 'string' && nameRaw.trim().length > 0) {
      payload.name = nameRaw.trim()
    }
    if (typeof codeRaw === 'string' && codeRaw.trim().length > 0) {
      payload.code = codeRaw.trim()
    }
    if (Object.keys(payload).length === 0) {
      return
    }
    try {
      const updated = await updateCountry(editingCountry.id, payload)
      setSuccessMessage(`Country "${updated.name}" updated.`)
      setEditingCountry(null)
    } catch (err) {
      if (!isApiError(err)) {
        // updateError is set by the hook
      }
    }
  }

  async function handleCreateUniversity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSuccessMessage(null)
    clearErrors()
    const formData = new FormData(event.currentTarget)
    const countryIdValue = Number(formData.get('country_id'))
    const name = String(formData.get('name') ?? '').trim()
    if (!Number.isFinite(countryIdValue) || countryIdValue < 1) {
      return
    }
    try {
      const created = await createUniversity({ country_id: countryIdValue, name })
      setSuccessMessage(`University "${created.name}" created.`)
      event.currentTarget.reset()
    } catch (err) {
      if (!isApiError(err)) {
        // createError is set by the hook
      }
    }
  }

  async function handleUpdateUniversity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editingUniversity) {
      return
    }
    setSuccessMessage(null)
    clearErrors()
    const formData = new FormData(event.currentTarget)
    const nameRaw = formData.get('name')
    const countryIdRaw = formData.get('country_id')
    const payload: { name?: string; country_id?: number } = {}
    if (typeof nameRaw === 'string' && nameRaw.trim().length > 0) {
      payload.name = nameRaw.trim()
    }
    if (typeof countryIdRaw === 'string' && countryIdRaw.length > 0) {
      const countryIdValue = Number(countryIdRaw)
      if (Number.isFinite(countryIdValue) && countryIdValue >= 1) {
        payload.country_id = countryIdValue
      }
    }
    if (Object.keys(payload).length === 0) {
      return
    }
    try {
      const updated = await updateUniversity(editingUniversity.id, payload)
      setSuccessMessage(`University "${updated.name}" updated.`)
      setEditingUniversity(null)
    } catch (err) {
      if (!isApiError(err)) {
        // updateError is set by the hook
      }
    }
  }

  async function handleCreateProgram(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSuccessMessage(null)
    clearErrors()
    const formData = new FormData(event.currentTarget)
    const universityIdValue = Number(formData.get('university_id'))
    const name = String(formData.get('name') ?? '').trim()
    if (!Number.isFinite(universityIdValue) || universityIdValue < 1) {
      return
    }
    try {
      const created = await createProgram({ university_id: universityIdValue, name })
      setSuccessMessage(`Program "${created.name}" created.`)
      event.currentTarget.reset()
    } catch (err) {
      if (!isApiError(err)) {
        // createError is set by the hook
      }
    }
  }

  async function handleUpdateProgram(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editingProgram) {
      return
    }
    setSuccessMessage(null)
    clearErrors()
    const formData = new FormData(event.currentTarget)
    const nameRaw = formData.get('name')
    const universityIdRaw = formData.get('university_id')
    const payload: { name?: string; university_id?: number } = {}
    if (typeof nameRaw === 'string' && nameRaw.trim().length > 0) {
      payload.name = nameRaw.trim()
    }
    if (typeof universityIdRaw === 'string' && universityIdRaw.length > 0) {
      const universityIdValue = Number(universityIdRaw)
      if (Number.isFinite(universityIdValue) && universityIdValue >= 1) {
        payload.university_id = universityIdValue
      }
    }
    if (Object.keys(payload).length === 0) {
      return
    }
    try {
      const updated = await updateProgram(editingProgram.id, payload)
      setSuccessMessage(`Program "${updated.name}" updated.`)
      setEditingProgram(null)
    } catch (err) {
      if (!isApiError(err)) {
        // updateError is set by the hook
      }
    }
  }

  async function handleDeleteCountry(country: Country) {
    setSuccessMessage(null)
    clearErrors()
    try {
      await deleteCountry(country.id)
      if (editingCountry?.id === country.id) {
        setEditingCountry(null)
      }
      setSuccessMessage(`Country "${country.name}" deleted.`)
    } catch (err) {
      if (!isApiError(err)) {
        // deleteError is set by the hook
      }
    }
  }

  async function handleDeleteUniversity(university: University) {
    setSuccessMessage(null)
    clearErrors()
    try {
      await deleteUniversity(university.id)
      if (editingUniversity?.id === university.id) {
        setEditingUniversity(null)
      }
      setSuccessMessage(`University "${university.name}" deleted.`)
    } catch (err) {
      if (!isApiError(err)) {
        // deleteError is set by the hook
      }
    }
  }

  async function handleDeleteProgram(program: Program) {
    setSuccessMessage(null)
    clearErrors()
    try {
      await deleteProgram(program.id)
      if (editingProgram?.id === program.id) {
        setEditingProgram(null)
      }
      setSuccessMessage(`Program "${program.name}" deleted.`)
    } catch (err) {
      if (!isApiError(err)) {
        // deleteError is set by the hook
      }
    }
  }

  function renderCountriesTab() {
    const loading = countriesLoading
    const error = countriesError
    return (
      <section
        className="master-data-admin-page__panel"
        role="tabpanel"
        id={`${tabListId}-panel-countries`}
        aria-labelledby={`${tabListId}-tab-countries`}
        data-testid="master-data-countries-panel"
      >
        <form
          className="master-data-form"
          method="post"
          onSubmit={handleCreateCountry}
          data-testid="master-data-country-create-form"
        >
          <label className="master-data-form__field">
            Name
            <input
              data-testid="master-data-country-name"
              name="name"
              type="text"
              required
              maxLength={255}
              aria-describedby={
                createError
                  ? createErrorId
                  : successMessage
                    ? successId
                    : undefined
              }
            />
          </label>
          <label className="master-data-form__field">
            Code
            <input
              data-testid="master-data-country-code"
              name="code"
              type="text"
              required
              maxLength={10}
              pattern="[A-Za-z]{2,10}"
              title="2-10 letter country code"
              aria-describedby={
                createError
                  ? createErrorId
                  : successMessage
                    ? successId
                    : undefined
              }
            />
          </label>
          <button
            type="submit"
            data-testid="master-data-country-create-submit"
            disabled={submitting}
            aria-busy={submitting}
          >
            {submitting ? 'Creating…' : 'Add country'}
          </button>
        </form>

        {editingCountry ? (
          <form
            key={editingCountry.id}
            className="master-data-form master-data-form--edit"
            method="post"
            onSubmit={handleUpdateCountry}
            data-testid="master-data-country-edit-form"
          >
            <h3 className="master-data-form__heading">Edit country</h3>
            <label className="master-data-form__field">
              Name
              <input
                data-testid="master-data-country-edit-name"
                name="name"
                type="text"
                maxLength={255}
                defaultValue={editingCountry.name}
                aria-describedby={
                  updateError
                    ? updateErrorId
                    : successMessage
                      ? successId
                      : undefined
                }
              />
            </label>
            <label className="master-data-form__field">
              Code
              <input
                data-testid="master-data-country-edit-code"
                name="code"
                type="text"
                maxLength={10}
                pattern="[A-Za-z]{2,10}"
                title="2-10 letter country code"
                defaultValue={editingCountry.code}
                aria-describedby={
                  updateError
                    ? updateErrorId
                    : successMessage
                      ? successId
                      : undefined
                }
              />
            </label>
            <div className="master-data-form__actions">
              <button
                type="submit"
                data-testid="master-data-country-edit-submit"
                disabled={submitting}
                aria-busy={submitting}
              >
                {submitting ? 'Saving…' : 'Save changes'}
              </button>
              <button
                type="button"
                data-testid="master-data-country-edit-cancel"
                disabled={submitting}
                onClick={() => setEditingCountry(null)}
              >
                Cancel
              </button>
            </div>
          </form>
        ) : null}

        {loading ? <p role="status">Loading countries…</p> : null}
        {error ? (
          <p
            className="master-data-admin-page__error"
            role="alert"
            data-testid="master-data-countries-error"
          >
            {error}
          </p>
        ) : null}
        {!loading && !error && countries.length === 0 ? (
          <p data-testid="master-data-countries-empty">No countries yet.</p>
        ) : null}
        {!loading && !error && countries.length > 0 ? (
          <table className="master-data-table" data-testid="master-data-country-table">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Code</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {countries.map((country) => (
                <tr key={country.id} data-testid={`master-data-country-row-${country.id}`}>
                  <td>{country.name}</td>
                  <td>{country.code}</td>
                  <td>
                    <div className="master-data-table__actions">
                      <button
                        type="button"
                        data-testid={`master-data-country-edit-${country.id}`}
                        onClick={() => {
                          setEditingUniversity(null)
                          setEditingProgram(null)
                          setEditingCountry(country)
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        data-testid={`master-data-country-delete-${country.id}`}
                        disabled={deletingId === country.id}
                        aria-busy={deletingId === country.id}
                        onClick={() => void handleDeleteCountry(country)}
                      >
                        {deletingId === country.id ? 'Deleting…' : 'Delete'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>
    )
  }

  function renderUniversitiesTab() {
    const loading = universitiesLoading
    const error = universitiesError
    return (
      <section
        className="master-data-admin-page__panel"
        role="tabpanel"
        id={`${tabListId}-panel-universities`}
        aria-labelledby={`${tabListId}-tab-universities`}
        data-testid="master-data-universities-panel"
      >
        <form
          className="master-data-form"
          method="post"
          onSubmit={handleCreateUniversity}
          data-testid="master-data-university-create-form"
        >
          <label className="master-data-form__field">
            Country
            <select
              data-testid="master-data-university-country"
              name="country_id"
              required
              defaultValue=""
              disabled={countriesLoading || countries.length === 0}
              aria-describedby={
                createError
                  ? createErrorId
                  : successMessage
                    ? successId
                    : undefined
              }
            >
              <option value="" disabled>
                {countriesLoading
                  ? 'Loading countries…'
                  : countries.length === 0
                    ? 'No countries available'
                    : 'Select a country'}
              </option>
              {countries.map((country) => (
                <option key={country.id} value={country.id}>
                  {country.name} ({country.code})
                </option>
              ))}
            </select>
          </label>
          <label className="master-data-form__field">
            Name
            <input
              data-testid="master-data-university-name"
              name="name"
              type="text"
              required
              maxLength={255}
              aria-describedby={
                createError
                  ? createErrorId
                  : successMessage
                    ? successId
                    : undefined
              }
            />
          </label>
          <button
            type="submit"
            data-testid="master-data-university-create-submit"
            disabled={submitting || countriesLoading || countries.length === 0}
            aria-busy={submitting}
          >
            {submitting ? 'Creating…' : 'Add university'}
          </button>
        </form>

        {editingUniversity ? (
          <form
            key={editingUniversity.id}
            className="master-data-form master-data-form--edit"
            method="post"
            onSubmit={handleUpdateUniversity}
            data-testid="master-data-university-edit-form"
          >
            <h3 className="master-data-form__heading">Edit university</h3>
            <label className="master-data-form__field">
              Country
              <select
                data-testid="master-data-university-edit-country"
                name="country_id"
                defaultValue={editingUniversity.country_id}
                disabled={countriesLoading || countries.length === 0}
                aria-describedby={
                  updateError
                    ? updateErrorId
                    : successMessage
                      ? successId
                      : undefined
                }
              >
                <option value="">— Keep current country —</option>
                {countries.map((country) => (
                  <option key={country.id} value={country.id}>
                    {country.name} ({country.code})
                  </option>
                ))}
              </select>
            </label>
            <label className="master-data-form__field">
              Name
              <input
                data-testid="master-data-university-edit-name"
                name="name"
                type="text"
                maxLength={255}
                defaultValue={editingUniversity.name}
                aria-describedby={
                  updateError
                    ? updateErrorId
                    : successMessage
                      ? successId
                      : undefined
                }
              />
            </label>
            <div className="master-data-form__actions">
              <button
                type="submit"
                data-testid="master-data-university-edit-submit"
                disabled={submitting}
                aria-busy={submitting}
              >
                {submitting ? 'Saving…' : 'Save changes'}
              </button>
              <button
                type="button"
                data-testid="master-data-university-edit-cancel"
                disabled={submitting}
                onClick={() => setEditingUniversity(null)}
              >
                Cancel
              </button>
            </div>
          </form>
        ) : null}

        {loading ? <p role="status">Loading universities…</p> : null}
        {error ? (
          <p
            className="master-data-admin-page__error"
            role="alert"
            data-testid="master-data-universities-error"
          >
            {error}
          </p>
        ) : null}
        {!loading && !error && universities.length === 0 ? (
          <p data-testid="master-data-universities-empty">No universities yet.</p>
        ) : null}
        {!loading && !error && universities.length > 0 ? (
          <table className="master-data-table" data-testid="master-data-university-table">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Country</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {universities.map((university) => (
                <tr
                  key={university.id}
                  data-testid={`master-data-university-row-${university.id}`}
                >
                  <td>{university.name}</td>
                  <td>{countryNameFor(countries, university.country_id)}</td>
                  <td>
                    <div className="master-data-table__actions">
                      <button
                        type="button"
                        data-testid={`master-data-university-edit-${university.id}`}
                        onClick={() => {
                          setEditingCountry(null)
                          setEditingProgram(null)
                          setEditingUniversity(university)
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        data-testid={`master-data-university-delete-${university.id}`}
                        disabled={deletingId === university.id}
                        aria-busy={deletingId === university.id}
                        onClick={() => void handleDeleteUniversity(university)}
                      >
                        {deletingId === university.id ? 'Deleting…' : 'Delete'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>
    )
  }

  function renderProgramsTab() {
    const loading = programsLoading
    const error = programsError
    return (
      <section
        className="master-data-admin-page__panel"
        role="tabpanel"
        id={`${tabListId}-panel-programs`}
        aria-labelledby={`${tabListId}-tab-programs`}
        data-testid="master-data-programs-panel"
      >
        <form
          className="master-data-form"
          method="post"
          onSubmit={handleCreateProgram}
          data-testid="master-data-program-create-form"
        >
          <label className="master-data-form__field">
            University
            <select
              data-testid="master-data-program-university"
              name="university_id"
              required
              defaultValue=""
              disabled={universitiesLoading || universities.length === 0}
              aria-describedby={
                createError
                  ? createErrorId
                  : successMessage
                    ? successId
                    : undefined
              }
            >
              <option value="" disabled>
                {universitiesLoading
                  ? 'Loading universities…'
                  : universities.length === 0
                    ? 'No universities available'
                    : 'Select a university'}
              </option>
              {universities.map((university) => (
                <option key={university.id} value={university.id}>
                  {university.name} ({countryNameFor(countries, university.country_id)})
                </option>
              ))}
            </select>
          </label>
          <label className="master-data-form__field">
            Name
            <input
              data-testid="master-data-program-name"
              name="name"
              type="text"
              required
              maxLength={255}
              aria-describedby={
                createError
                  ? createErrorId
                  : successMessage
                    ? successId
                    : undefined
              }
            />
          </label>
          <button
            type="submit"
            data-testid="master-data-program-create-submit"
            disabled={submitting || universitiesLoading || universities.length === 0}
            aria-busy={submitting}
          >
            {submitting ? 'Creating…' : 'Add program'}
          </button>
        </form>

        {editingProgram ? (
          <form
            key={editingProgram.id}
            className="master-data-form master-data-form--edit"
            method="post"
            onSubmit={handleUpdateProgram}
            data-testid="master-data-program-edit-form"
          >
            <h3 className="master-data-form__heading">Edit program</h3>
            <label className="master-data-form__field">
              University
              <select
                data-testid="master-data-program-edit-university"
                name="university_id"
                defaultValue={editingProgram.university_id}
                disabled={universitiesLoading || universities.length === 0}
                aria-describedby={
                  updateError
                    ? updateErrorId
                    : successMessage
                      ? successId
                      : undefined
                }
              >
                <option value="">— Keep current university —</option>
                {universities.map((university) => (
                  <option key={university.id} value={university.id}>
                    {university.name} ({countryNameFor(countries, university.country_id)})
                  </option>
                ))}
              </select>
            </label>
            <label className="master-data-form__field">
              Name
              <input
                data-testid="master-data-program-edit-name"
                name="name"
                type="text"
                maxLength={255}
                defaultValue={editingProgram.name}
                aria-describedby={
                  updateError
                    ? updateErrorId
                    : successMessage
                      ? successId
                      : undefined
                }
              />
            </label>
            <div className="master-data-form__actions">
              <button
                type="submit"
                data-testid="master-data-program-edit-submit"
                disabled={submitting}
                aria-busy={submitting}
              >
                {submitting ? 'Saving…' : 'Save changes'}
              </button>
              <button
                type="button"
                data-testid="master-data-program-edit-cancel"
                disabled={submitting}
                onClick={() => setEditingProgram(null)}
              >
                Cancel
              </button>
            </div>
          </form>
        ) : null}

        {loading ? <p role="status">Loading programs…</p> : null}
        {error ? (
          <p
            className="master-data-admin-page__error"
            role="alert"
            data-testid="master-data-programs-error"
          >
            {error}
          </p>
        ) : null}
        {!loading && !error && programs.length === 0 ? (
          <p data-testid="master-data-programs-empty">No programs yet.</p>
        ) : null}
        {!loading && !error && programs.length > 0 ? (
          <table className="master-data-table" data-testid="master-data-program-table">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">University</th>
                <th scope="col">Country</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {programs.map((program) => {
                const university = universitiesById.get(program.university_id)
                const country = university
                  ? countriesById.get(university.country_id)
                  : undefined
                return (
                  <tr
                    key={program.id}
                    data-testid={`master-data-program-row-${program.id}`}
                  >
                    <td>{program.name}</td>
                    <td>{universityNameFor(universities, program.university_id)}</td>
                    <td>{country ? country.name : `Country #${university?.country_id ?? ''}`}</td>
                    <td>
                      <div className="master-data-table__actions">
                        <button
                          type="button"
                          data-testid={`master-data-program-edit-${program.id}`}
                          onClick={() => {
                            setEditingCountry(null)
                            setEditingUniversity(null)
                            setEditingProgram(program)
                          }}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          data-testid={`master-data-program-delete-${program.id}`}
                          disabled={deletingId === program.id}
                          aria-busy={deletingId === program.id}
                          onClick={() => void handleDeleteProgram(program)}
                        >
                          {deletingId === program.id ? 'Deleting…' : 'Delete'}
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        ) : null}
      </section>
    )
  }

  return (
    <div className="master-data-admin-page" data-testid="master-data-admin-page">
      <header className="master-data-admin-page__header">
        <h2>Master data</h2>
        <p className="master-data-admin-page__subtitle">
          Manage the structured target-country, university, and program lists used across
          your consultancy.
        </p>
      </header>

      {createError ? (
        <p
          className="master-data-admin-page__error"
          role="alert"
          id={createErrorId}
          data-testid="master-data-create-error"
        >
          {createError}
        </p>
      ) : null}
      {updateError ? (
        <p
          className="master-data-admin-page__error"
          role="alert"
          id={updateErrorId}
          data-testid="master-data-update-error"
        >
          {updateError}
        </p>
      ) : null}
      {deleteError ? (
        <p
          className="master-data-admin-page__error"
          role="alert"
          id={deleteErrorId}
          data-testid="master-data-delete-error"
        >
          {deleteError}
        </p>
      ) : null}
      {successMessage ? (
        <p
          className="master-data-admin-page__success"
          role="status"
          id={successId}
          data-testid="master-data-success"
        >
          {successMessage}
        </p>
      ) : null}

      <div
        className="master-data-admin-page__tabs"
        role="tablist"
        aria-label="Master data sections"
        data-testid="master-data-tabs"
      >
        {TAB_ORDER.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            id={`${tabListId}-tab-${tab}`}
            aria-selected={activeTab === tab}
            aria-controls={`${tabListId}-panel-${tab}`}
            tabIndex={activeTab === tab ? 0 : -1}
            data-testid={`master-data-tab-${tab}`}
            className={
              activeTab === tab
                ? 'master-data-admin-page__tab master-data-admin-page__tab--active'
                : 'master-data-admin-page__tab'
            }
            onClick={() => switchTab(tab)}
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </div>

      {activeTab === 'countries' ? renderCountriesTab() : null}
      {activeTab === 'universities' ? renderUniversitiesTab() : null}
      {activeTab === 'programs' ? renderProgramsTab() : null}
    </div>
  )
}