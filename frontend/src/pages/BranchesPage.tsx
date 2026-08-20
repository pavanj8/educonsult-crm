import { useId, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../api/client'
import { useBranches } from '../hooks/useBranches'
import type { Branch } from '../types/branch'

function formatDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return iso
  }
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export default function BranchesPage() {
  const {
    branches,
    loading,
    error,
    createError,
    updateError,
    submitting,
    createBranch,
    updateBranch,
  } = useBranches()
  const [createSuccessMessage, setCreateSuccessMessage] = useState<string | null>(null)
  const [updateSuccessMessage, setUpdateSuccessMessage] = useState<string | null>(null)
  const [editingBranch, setEditingBranch] = useState<Branch | null>(null)
  const createErrorId = useId()
  const createSuccessId = useId()
  const updateErrorId = useId()
  const updateSuccessId = useId()

  async function handleCreateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setCreateSuccessMessage(null)

    const formData = new FormData(event.currentTarget)
    const rawName = formData.get('name')
    const rawCity = formData.get('city')
    const name = typeof rawName === 'string' ? rawName.trim() : ''
    const city = typeof rawCity === 'string' ? rawCity.trim() : ''

    try {
      const created = await createBranch({ name, city })
      setCreateSuccessMessage(`Branch "${created.name}" created.`)
      event.currentTarget.reset()
    } catch (err) {
      if (!isApiError(err)) {
        // createError is set by the hook
      }
    }
  }

  async function handleEditSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editingBranch) {
      return
    }

    setUpdateSuccessMessage(null)

    const formData = new FormData(event.currentTarget)
    const rawName = formData.get('name')
    const rawCity = formData.get('city')
    const name = typeof rawName === 'string' ? rawName.trim() : ''
    const city = typeof rawCity === 'string' ? rawCity.trim() : ''

    try {
      const updated = await updateBranch(editingBranch.id, { name, city })
      setUpdateSuccessMessage(`Branch "${updated.name}" updated.`)
      setEditingBranch(null)
    } catch (err) {
      if (!isApiError(err)) {
        // updateError is set by the hook
      }
    }
  }

  function handleEditClick(branch: Branch) {
    setEditingBranch(branch)
    setUpdateSuccessMessage(null)
  }

  function handleEditCancel() {
    setEditingBranch(null)
    setUpdateSuccessMessage(null)
  }

  return (
    <div className="branches-page" data-testid="branches-page">
      <header className="branches-page__header">
        <h2>Branches</h2>
        <p className="branches-page__subtitle">Manage branches across your consultancy.</p>
      </header>

      <section className="branches-page__section" aria-labelledby="create-branch-heading">
        <h3 id="create-branch-heading">Create branch</h3>
        <form className="branch-form" method="post" onSubmit={handleCreateSubmit}>
          <label className="branch-form__field">
            Branch name
            <input
              data-testid="branch-name"
              name="name"
              type="text"
              required
              maxLength={255}
              aria-describedby={
                createError ? createErrorId : createSuccessMessage ? createSuccessId : undefined
              }
            />
          </label>
          <label className="branch-form__field">
            City
            <input
              data-testid="branch-city"
              name="city"
              type="text"
              required
              maxLength={100}
              aria-describedby={
                createError ? createErrorId : createSuccessMessage ? createSuccessId : undefined
              }
            />
          </label>
          {createError ? (
            <p
              className="branch-form__error"
              data-testid="branch-create-error"
              id={createErrorId}
              role="alert"
            >
              {createError}
            </p>
          ) : null}
          {createSuccessMessage ? (
            <p
              className="branch-form__success"
              data-testid="branch-create-success"
              id={createSuccessId}
              role="status"
            >
              {createSuccessMessage}
            </p>
          ) : null}
          <button
            className="branch-form__submit"
            data-testid="branch-create-submit"
            type="submit"
            disabled={submitting}
            aria-busy={submitting}
          >
            {submitting && !editingBranch ? 'Creating…' : 'Create branch'}
          </button>
        </form>
      </section>

      {editingBranch ? (
        <section className="branches-page__section" aria-labelledby="edit-branch-heading">
          <h3 id="edit-branch-heading">Edit branch</h3>
          <form
            key={editingBranch.id}
            className="branch-form"
            method="post"
            onSubmit={handleEditSubmit}
          >
            <label className="branch-form__field">
              Branch name
              <input
                data-testid="branch-edit-name"
                name="name"
                type="text"
                required
                maxLength={255}
                defaultValue={editingBranch.name}
                aria-describedby={
                  updateError ? updateErrorId : updateSuccessMessage ? updateSuccessId : undefined
                }
              />
            </label>
            <label className="branch-form__field">
              City
              <input
                data-testid="branch-edit-city"
                name="city"
                type="text"
                required
                maxLength={100}
                defaultValue={editingBranch.city}
                aria-describedby={
                  updateError ? updateErrorId : updateSuccessMessage ? updateSuccessId : undefined
                }
              />
            </label>
            {updateError ? (
              <p
                className="branch-form__error"
                data-testid="branch-edit-error"
                id={updateErrorId}
                role="alert"
              >
                {updateError}
              </p>
            ) : null}
            {updateSuccessMessage ? (
              <p
                className="branch-form__success"
                data-testid="branch-edit-success"
                id={updateSuccessId}
                role="status"
              >
                {updateSuccessMessage}
              </p>
            ) : null}
            <div className="branch-form__actions">
              <button
                className="branch-form__submit"
                data-testid="branch-edit-submit"
                type="submit"
                disabled={submitting}
                aria-busy={submitting}
              >
                {submitting ? 'Saving…' : 'Save changes'}
              </button>
              <button
                className="branch-form__cancel"
                data-testid="branch-edit-cancel"
                type="button"
                disabled={submitting}
                onClick={handleEditCancel}
              >
                Cancel
              </button>
            </div>
          </form>
        </section>
      ) : null}

      <section className="branches-page__section" aria-labelledby="branch-list-heading">
        <h3 id="branch-list-heading">All branches</h3>
        {loading && <p className="branches-page__status">Loading branches…</p>}
        {error && (
          <p className="branches-page__status branches-page__status--error" role="alert">
            {error}
          </p>
        )}
        {!loading && !error && branches.length === 0 && (
          <p className="branches-page__status">No branches yet.</p>
        )}
        {!loading && !error && branches.length > 0 && (
          <div className="branch-table-wrapper">
            <table className="branch-table" data-testid="branch-table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">City</th>
                  <th scope="col">Created</th>
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {branches.map((branch) => (
                  <tr key={branch.id} data-testid={`branch-row-${branch.id}`}>
                    <td>{branch.name}</td>
                    <td>{branch.city}</td>
                    <td>{formatDate(branch.created_at)}</td>
                    <td>
                      <button
                        className="branch-table__edit"
                        data-testid={`branch-edit-${branch.id}`}
                        type="button"
                        onClick={() => handleEditClick(branch)}
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
