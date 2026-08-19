import { useId, useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../api/client'
import { useBranches } from '../hooks/useBranches'
import { useStaff } from '../hooks/useStaff'
import { useAuth } from '../store/authStore'
import {
  STAFF_CREATABLE_ROLES,
  STAFF_ROLE_LABELS,
  type StaffCreatableRole,
} from '../types/staff'

function getCreatableRoles(isBranchManager: boolean): StaffCreatableRole[] {
  if (isBranchManager) {
    return STAFF_CREATABLE_ROLES.filter((role) => role !== 'branch_manager')
  }
  return [...STAFF_CREATABLE_ROLES]
}

export default function StaffPage() {
  const { user } = useAuth()
  const isOwner = user?.role === 'consultancy_owner'
  const isBranchManager = user?.role === 'branch_manager'
  const { branches, loading: branchesLoading, error: branchesError } = useBranches({
    enabled: isOwner,
  })
  const { createError, submitting, createStaff } = useStaff()
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const errorId = useId()
  const successId = useId()

  const creatableRoles = useMemo(
    () => getCreatableRoles(isBranchManager),
    [isBranchManager],
  )

  const branchSelectDisabled = isOwner && (branchesLoading || branches.length === 0)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSuccessMessage(null)

    const formData = new FormData(event.currentTarget)
    const email = typeof formData.get('email') === 'string' ? formData.get('email')!.trim() : ''
    const password =
      typeof formData.get('password') === 'string' ? formData.get('password')! : ''
    const role = formData.get('role')
    const branchIdValue = isBranchManager
      ? user?.branch_id
      : Number(formData.get('branch_id'))

    if (
      typeof role !== 'string' ||
      !creatableRoles.includes(role as StaffCreatableRole) ||
      typeof branchIdValue !== 'number' ||
      !Number.isFinite(branchIdValue) ||
      branchIdValue < 1
    ) {
      return
    }

    try {
      const created = await createStaff({
        email,
        password,
        role: role as StaffCreatableRole,
        branch_id: branchIdValue,
      })
      const roleLabel = STAFF_ROLE_LABELS[created.role]
      setSuccessMessage(`Staff account for ${created.email} (${roleLabel}) created.`)
      event.currentTarget.reset()
    } catch (err) {
      if (!isApiError(err)) {
        // createError is set by the hook
      }
    }
  }

  return (
    <div className="staff-page" data-testid="staff-page">
      <header className="staff-page__header">
        <h2>Staff</h2>
        <p className="staff-page__subtitle">Create staff accounts with role and branch assignment.</p>
      </header>

      <section className="staff-page__section" aria-labelledby="create-staff-heading">
        <h3 id="create-staff-heading">Create staff account</h3>
        <form className="staff-form" method="post" onSubmit={handleSubmit}>
          <label className="staff-form__field">
            Email
            <input
              data-testid="staff-email"
              name="email"
              type="email"
              required
              maxLength={255}
              autoComplete="off"
              aria-describedby={createError ? errorId : successMessage ? successId : undefined}
            />
          </label>
          <label className="staff-form__field">
            Password
            <input
              data-testid="staff-password"
              name="password"
              type="password"
              required
              autoComplete="new-password"
              aria-describedby={createError ? errorId : successMessage ? successId : undefined}
            />
          </label>
          <label className="staff-form__field">
            Role
            <select
              data-testid="staff-role"
              name="role"
              required
              defaultValue={creatableRoles[0]}
              aria-describedby={createError ? errorId : successMessage ? successId : undefined}
            >
              {creatableRoles.map((role) => (
                <option key={role} value={role}>
                  {STAFF_ROLE_LABELS[role]}
                </option>
              ))}
            </select>
          </label>
          {isOwner ? (
            <label className="staff-form__field">
              Branch
              <select
                data-testid="staff-branch"
                name="branch_id"
                required
                disabled={branchSelectDisabled}
                aria-describedby={createError ? errorId : successMessage ? successId : undefined}
              >
                {branchesLoading ? (
                  <option value="">Loading branches…</option>
                ) : branches.length === 0 ? (
                  <option value="">No branches available</option>
                ) : (
                  branches.map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      {branch.name} ({branch.city})
                    </option>
                  ))
                )}
              </select>
            </label>
          ) : null}
          {isBranchManager ? (
            <p className="staff-form__branch-note" data-testid="staff-branch-readonly">
              Staff will be assigned to your branch (ID: {user?.branch_id ?? 'unknown'}).
            </p>
          ) : null}
          {isOwner && branchesError ? (
            <p className="staff-form__error" role="alert">
              {branchesError}
            </p>
          ) : null}
          {createError ? (
            <p
              className="staff-form__error"
              data-testid="staff-create-error"
              id={errorId}
              role="alert"
            >
              {createError}
            </p>
          ) : null}
          {successMessage ? (
            <p
              className="staff-form__success"
              data-testid="staff-create-success"
              id={successId}
              role="status"
            >
              {successMessage}
            </p>
          ) : null}
          <button
            className="staff-form__submit"
            data-testid="staff-create-submit"
            type="submit"
            disabled={submitting || branchSelectDisabled}
            aria-busy={submitting}
          >
            {submitting ? 'Creating…' : 'Create staff account'}
          </button>
        </form>
      </section>
    </div>
  )
}
