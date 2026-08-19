import { useId, useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import { isApiError } from '../api/client'
import { useBranches } from '../hooks/useBranches'
import { useStaff } from '../hooks/useStaff'
import { useAuth } from '../store/authStore'
import {
  STAFF_CREATABLE_ROLES,
  STAFF_ROLE_LABELS,
  type Staff,
  type StaffCreatableRole,
} from '../types/staff'

function getCreatableRoles(isBranchManager: boolean): StaffCreatableRole[] {
  if (isBranchManager) {
    return STAFF_CREATABLE_ROLES.filter((role) => role !== 'branch_manager')
  }
  return [...STAFF_CREATABLE_ROLES]
}

function getBranchLabel(
  branchId: number | null | undefined,
  branches: { id: number; name: string; city: string }[],
): string | null {
  if (branchId == null) {
    return null
  }
  const branch = branches.find((item) => item.id === branchId)
  if (branch) {
    return `${branch.name} (${branch.city})`
  }
  return null
}

export default function StaffPage() {
  const { user } = useAuth()
  const isOwner = user?.role === 'consultancy_owner'
  const isBranchManager = user?.role === 'branch_manager'
  const managerBranchMissing = isBranchManager && (user?.branch_id == null || user.branch_id < 1)
  const { branches, loading: branchesLoading, error: branchesError } = useBranches({
    enabled: isOwner,
  })
  const {
    staff,
    loading: staffLoading,
    error: staffError,
    createError,
    updateError,
    submitting,
    createStaff,
    updateStaff,
    loadStaffMember,
  } = useStaff()
  const [createSuccessMessage, setCreateSuccessMessage] = useState<string | null>(null)
  const [updateSuccessMessage, setUpdateSuccessMessage] = useState<string | null>(null)
  const [createValidationError, setCreateValidationError] = useState<string | null>(null)
  const [editingStaff, setEditingStaff] = useState<Staff | null>(null)
  const createErrorId = useId()
  const createSuccessId = useId()
  const updateErrorId = useId()
  const updateSuccessId = useId()

  const creatableRoles = useMemo(
    () => getCreatableRoles(isBranchManager),
    [isBranchManager],
  )

  const editCreatableRoles = useMemo(() => {
    if (!editingStaff) {
      return creatableRoles
    }
    if (isBranchManager) {
      return creatableRoles
    }
    if (editingStaff.role === 'branch_manager') {
      return ['branch_manager' as const, ...creatableRoles.filter((role) => role !== 'branch_manager')]
    }
    return creatableRoles
  }, [creatableRoles, editingStaff, isBranchManager])

  const branchSelectDisabled = isOwner && (branchesLoading || branches.length === 0)
  const createSubmitDisabled = submitting || branchSelectDisabled || managerBranchMissing

  const managerBranchLabel =
    getBranchLabel(user?.branch_id, branches) ??
    (user?.branch_id != null ? 'your branch' : null)

  async function handleCreateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setCreateSuccessMessage(null)
    setCreateValidationError(null)

    const formData = new FormData(event.currentTarget)
    const email = typeof formData.get('email') === 'string' ? formData.get('email')!.trim() : ''
    const password =
      typeof formData.get('password') === 'string' ? formData.get('password')! : ''
    const role = formData.get('role')
    const branchIdValue = isBranchManager
      ? user?.branch_id
      : Number(formData.get('branch_id'))

    if (managerBranchMissing) {
      setCreateValidationError(
        'Your account is not assigned to a branch. Contact your consultancy owner before creating staff.',
      )
      return
    }

    if (
      typeof role !== 'string' ||
      !creatableRoles.includes(role as StaffCreatableRole) ||
      typeof branchIdValue !== 'number' ||
      !Number.isFinite(branchIdValue) ||
      branchIdValue < 1
    ) {
      setCreateValidationError('Select a valid role and branch before creating staff.')
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
      setCreateSuccessMessage(`Staff account for ${created.email} (${roleLabel}) created.`)
      event.currentTarget.reset()
    } catch (err) {
      if (!isApiError(err)) {
        // createError is set by the hook
      }
    }
  }

  async function handleEditSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editingStaff) {
      return
    }

    setUpdateSuccessMessage(null)

    const formData = new FormData(event.currentTarget)
    const role = formData.get('role')
    const branchIdValue = isBranchManager
      ? editingStaff.branch_id
      : Number(formData.get('branch_id'))

    if (
      typeof role !== 'string' ||
      !editCreatableRoles.includes(role as StaffCreatableRole) ||
      typeof branchIdValue !== 'number' ||
      !Number.isFinite(branchIdValue) ||
      branchIdValue < 1
    ) {
      return
    }

    try {
      const updated = await updateStaff(editingStaff.id, {
        role: role as StaffCreatableRole,
        branch_id: branchIdValue,
      })
      const roleLabel = STAFF_ROLE_LABELS[updated.role]
      setUpdateSuccessMessage(`Staff account for ${updated.email} (${roleLabel}) updated.`)
      setEditingStaff(null)
    } catch (err) {
      if (!isApiError(err)) {
        // updateError is set by the hook
      }
    }
  }

  async function handleEditClick(member: Staff) {
    setUpdateSuccessMessage(null)
    try {
      const loaded = await loadStaffMember(member.id)
      setEditingStaff(loaded)
    } catch {
      setEditingStaff(member)
    }
  }

  function handleEditCancel() {
    setEditingStaff(null)
    setUpdateSuccessMessage(null)
  }

  function branchNameForStaff(branchId: number): string {
    return getBranchLabel(branchId, branches) ?? `Branch ${branchId}`
  }

  return (
    <div className="staff-page" data-testid="staff-page">
      <header className="staff-page__header">
        <h2>Staff</h2>
        <p className="staff-page__subtitle">
          Create and edit staff accounts with role and branch assignment.
        </p>
      </header>

      <section className="staff-page__section" aria-labelledby="create-staff-heading">
        <h3 id="create-staff-heading">Create staff account</h3>
        <form className="staff-form" method="post" onSubmit={handleCreateSubmit}>
          <label className="staff-form__field">
            Email
            <input
              data-testid="staff-email"
              name="email"
              type="email"
              required
              maxLength={255}
              autoComplete="off"
              aria-describedby={
                createError || createValidationError
                  ? createErrorId
                  : createSuccessMessage
                    ? createSuccessId
                    : undefined
              }
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
              aria-describedby={
                createError || createValidationError
                  ? createErrorId
                  : createSuccessMessage
                    ? createSuccessId
                    : undefined
              }
            />
          </label>
          <label className="staff-form__field">
            Role
            <select
              data-testid="staff-role"
              name="role"
              required
              defaultValue={creatableRoles[0]}
              aria-describedby={
                createError || createValidationError
                  ? createErrorId
                  : createSuccessMessage
                    ? createSuccessId
                    : undefined
              }
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
                defaultValue=""
                aria-describedby={
                  createError || createValidationError
                    ? createErrorId
                    : createSuccessMessage
                      ? createSuccessId
                      : undefined
                }
              >
                <option value="" disabled>
                  Select a branch
                </option>
                {branchesLoading ? (
                  <option value="" disabled>
                    Loading branches…
                  </option>
                ) : branches.length === 0 ? (
                  <option value="" disabled>
                    No branches available
                  </option>
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
              {managerBranchMissing
                ? 'Your account is not assigned to a branch. Contact your consultancy owner before creating staff.'
                : `Staff will be assigned to ${managerBranchLabel ?? 'your branch'}.`}
            </p>
          ) : null}
          {isOwner && branchesError ? (
            <p className="staff-form__error" role="alert">
              {branchesError}
            </p>
          ) : null}
          {createValidationError ? (
            <p
              className="staff-form__error"
              data-testid="staff-create-validation-error"
              id={createErrorId}
              role="alert"
            >
              {createValidationError}
            </p>
          ) : null}
          {createError ? (
            <p
              className="staff-form__error"
              data-testid="staff-create-error"
              id={createErrorId}
              role="alert"
            >
              {createError}
            </p>
          ) : null}
          {createSuccessMessage ? (
            <p
              className="staff-form__success"
              data-testid="staff-create-success"
              id={createSuccessId}
              role="status"
            >
              {createSuccessMessage}
            </p>
          ) : null}
          <button
            className="staff-form__submit"
            data-testid="staff-create-submit"
            type="submit"
            disabled={createSubmitDisabled}
            aria-busy={submitting && !editingStaff}
          >
            {submitting && !editingStaff ? 'Creating…' : 'Create staff account'}
          </button>
        </form>
      </section>

      {editingStaff ? (
        <section className="staff-page__section" aria-labelledby="edit-staff-heading">
          <h3 id="edit-staff-heading">Edit staff account</h3>
          <form
            key={editingStaff.id}
            className="staff-form"
            method="post"
            onSubmit={handleEditSubmit}
          >
            <label className="staff-form__field">
              Email
              <input
                data-testid="staff-edit-email"
                name="email"
                type="email"
                readOnly
                value={editingStaff.email}
                aria-describedby={
                  updateError ? updateErrorId : updateSuccessMessage ? updateSuccessId : undefined
                }
              />
            </label>
            <label className="staff-form__field">
              Role
              <select
                data-testid="staff-edit-role"
                name="role"
                required
                defaultValue={editingStaff.role}
                aria-describedby={
                  updateError ? updateErrorId : updateSuccessMessage ? updateSuccessId : undefined
                }
              >
                {editCreatableRoles.map((role) => (
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
                  data-testid="staff-edit-branch"
                  name="branch_id"
                  required
                  disabled={branchSelectDisabled}
                  defaultValue={editingStaff.branch_id}
                  aria-describedby={
                    updateError ? updateErrorId : updateSuccessMessage ? updateSuccessId : undefined
                  }
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
              <p className="staff-form__branch-note" data-testid="staff-edit-branch-readonly">
                Staff is assigned to your branch.
              </p>
            ) : null}
            {updateError ? (
              <p
                className="staff-form__error"
                data-testid="staff-edit-error"
                id={updateErrorId}
                role="alert"
              >
                {updateError}
              </p>
            ) : null}
            {updateSuccessMessage ? (
              <p
                className="staff-form__success"
                data-testid="staff-edit-success"
                id={updateSuccessId}
                role="status"
              >
                {updateSuccessMessage}
              </p>
            ) : null}
            <div className="staff-form__actions">
              <button
                className="staff-form__submit"
                data-testid="staff-edit-submit"
                type="submit"
                disabled={submitting}
                aria-busy={submitting}
              >
                {submitting ? 'Saving…' : 'Save changes'}
              </button>
              <button
                className="staff-form__cancel"
                data-testid="staff-edit-cancel"
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

      <section className="staff-page__section" aria-labelledby="staff-list-heading">
        <h3 id="staff-list-heading">All staff</h3>
        {staffLoading && <p className="staff-page__status">Loading staff…</p>}
        {staffError && (
          <p className="staff-page__status staff-page__status--error" role="alert">
            {staffError}
          </p>
        )}
        {!staffLoading && !staffError && staff.length === 0 && (
          <p className="staff-page__status">No staff accounts yet.</p>
        )}
        {!staffLoading && !staffError && staff.length > 0 && (
          <div className="staff-table-wrapper">
            <table className="staff-table" data-testid="staff-table">
              <thead>
                <tr>
                  <th scope="col">Email</th>
                  <th scope="col">Role</th>
                  <th scope="col">Branch</th>
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {staff.map((member) => (
                  <tr key={member.id} data-testid={`staff-row-${member.id}`}>
                    <td>{member.email}</td>
                    <td>{STAFF_ROLE_LABELS[member.role]}</td>
                    <td>{branchNameForStaff(member.branch_id)}</td>
                    <td>
                      <button
                        className="staff-table__edit"
                        data-testid={`staff-edit-${member.id}`}
                        type="button"
                        onClick={() => void handleEditClick(member)}
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
