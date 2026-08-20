import { useId, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../api/client'
import { useTenants } from '../hooks/useTenants'

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

export default function TenantsPage() {
  const { tenants, loading, error, createError, submitting, createTenant } = useTenants()
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const errorId = useId()
  const successId = useId()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSuccessMessage(null)

    const formData = new FormData(event.currentTarget)
    const rawName = formData.get('name')
    const rawSlug = formData.get('slug')
    const rawOwnerEmail = formData.get('owner_email')
    const name = typeof rawName === 'string' ? rawName.trim() : ''
    const slug = typeof rawSlug === 'string' ? rawSlug.trim() : ''
    const ownerEmail = typeof rawOwnerEmail === 'string' ? rawOwnerEmail.trim() : ''

    try {
      const created = await createTenant({
        name,
        slug,
        owner_email: ownerEmail,
      })
      setSuccessMessage(`Tenant "${created.name}" created. Owner invite sent to ${ownerEmail}.`)
      event.currentTarget.reset()
    } catch (err) {
      if (!isApiError(err)) {
        // createError is set by the hook
      }
    }
  }

  return (
    <div className="tenants-page" data-testid="tenants-page">
      <header className="tenants-page__header">
        <h2>Tenants</h2>
        <p className="tenants-page__subtitle">Manage consultancy tenants on the platform.</p>
      </header>

      <section className="tenants-page__section" aria-labelledby="create-tenant-heading">
        <h3 id="create-tenant-heading">Create tenant</h3>
        <form className="tenant-form" method="post" onSubmit={handleSubmit}>
          <label className="tenant-form__field">
            Tenant name
            <input
              data-testid="tenant-name"
              name="name"
              type="text"
              required
              maxLength={255}
              aria-describedby={createError ? errorId : successMessage ? successId : undefined}
            />
          </label>
          <label className="tenant-form__field">
            Slug
            <input
              data-testid="tenant-slug"
              name="slug"
              type="text"
              required
              maxLength={100}
              pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
              title="Lowercase letters, numbers, and hyphens only"
              aria-describedby={createError ? errorId : successMessage ? successId : undefined}
            />
          </label>
          <label className="tenant-form__field">
            Owner email
            <input
              data-testid="tenant-owner-email"
              name="owner_email"
              type="email"
              required
              maxLength={255}
              aria-describedby={createError ? errorId : successMessage ? successId : undefined}
            />
          </label>
          {createError ? (
            <p
              className="tenant-form__error"
              data-testid="tenant-create-error"
              id={errorId}
              role="alert"
            >
              {createError}
            </p>
          ) : null}
          {successMessage ? (
            <p
              className="tenant-form__success"
              data-testid="tenant-create-success"
              id={successId}
              role="status"
            >
              {successMessage}
            </p>
          ) : null}
          <button
            className="tenant-form__submit"
            data-testid="tenant-create-submit"
            type="submit"
            disabled={submitting}
            aria-busy={submitting}
          >
            {submitting ? 'Creating…' : 'Create tenant'}
          </button>
        </form>
      </section>

      <section className="tenants-page__section" aria-labelledby="tenant-list-heading">
        <h3 id="tenant-list-heading">All tenants</h3>
        {loading && <p className="tenants-page__status">Loading tenants…</p>}
        {error && (
          <p className="tenants-page__status tenants-page__status--error" role="alert">
            {error}
          </p>
        )}
        {!loading && !error && tenants.length === 0 && (
          <p className="tenants-page__status">No tenants yet.</p>
        )}
        {!loading && !error && tenants.length > 0 && (
          <div className="tenant-table-wrapper">
            <table className="tenant-table" data-testid="tenant-table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Slug</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                {tenants.map((tenant) => (
                  <tr key={tenant.id} data-testid={`tenant-row-${tenant.id}`}>
                    <td>{tenant.name}</td>
                    <td>{tenant.slug}</td>
                    <td>{formatDate(tenant.created_at)}</td>
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
