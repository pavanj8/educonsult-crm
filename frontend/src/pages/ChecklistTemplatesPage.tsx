/** Checklist template builder UI (E15; Journey J8).

Renders the CRUD UI for :class:`ChecklistItemTemplate` rows. Operators
(consultancy owner / branch manager — both carry the
``checklist_template:manage`` permission) use this page to define the
required/optional document checklist that surfaces on the student's
J19 checklist view (E26) when an application reaches a given pipeline
stage (and optionally for a specific program).

The UI is intentionally single-list (no tabs):

* Every template row has the same shape (stage + optional program +
  name + optional description + required toggle + order index).
* The list is filtered by stage and ordered within each stage by
  ``(order_index NULLS LAST, id)`` so the UI matches the backend
  ordering used by the J19 read endpoint (ADR-0012).

A "Program" field is offered with an explicit "All programs" option
that sends ``program_id: null`` — the canonical "applies universally"
shape (Requirements §5; Journey J8). The page also keeps a stage
filter above the list so operators can focus on one stage at a time,
matching the J8 mental model of "per-stage checklist".

Traceability
------------
* Requirements §5 (per-stage/program checklist templates).
* Journey J8 (Owner/Branch Manager defines a document checklist
  template for a stage/program).
* Epic E15 (Document Checklist Template Management).
* Backend: :mod:`app.routers.checklist` (E26 read) + the E15 CRUD
  router mounted under ``/checklist-templates`` (sibling ticket #132).
* Frontend sibling: :mod:`useChecklistTemplates` (state hook).
*/

import { useId, useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import {
  NON_TERMINAL_PIPELINE_STAGES,
  PIPELINE_STAGE_LABELS,
  type PipelineStage,
} from '../types/application'
import { useChecklistTemplates } from '../hooks/useChecklistTemplates'
import { useMasterDataAdmin } from '../hooks/useMasterDataAdmin'
import { hasAccessToken } from '../store/authStorage'
import type { ChecklistItemTemplate } from '../types/checklist'
import type { Program } from '../types/masterData'

/**
 * Stages that can host a checklist template.
 *
 * Derived from :ts:type:`PipelineStage` minus the terminal stages
 * (``enrolled`` / ``rejected`` / ``withdrawn``) co-located with that
 * type in :mod:`frontend/src/types/application`. No documents are
 * collected once an application has reached its final state, so
 * those stages are excluded here. Deriving from a single source of
 * truth means adding a new non-terminal pipeline stage to
 * :ts:type:`PipelineStage` automatically surfaces it in this picker
 * (Software Architect review on issue #133).
 */
const STAGE_OPTIONS: readonly PipelineStage[] = NON_TERMINAL_PIPELINE_STAGES

const DEFAULT_STAGE: PipelineStage = 'registered'

function isStageOption(value: string): value is PipelineStage {
  return (STAGE_OPTIONS as string[]).includes(value)
}

function programLabelFor(programs: Program[], programId: number | null): string {
  if (programId === null) {
    return 'All programs'
  }
  const program = programs.find((item) => item.id === programId)
  return program ? program.name : `Program #${programId}`
}

export default function ChecklistTemplatesPage() {
  const {
    templates,
    loading,
    error,
    createError,
    updateError,
    deleteError,
    submitting,
    deletingId,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    clearErrors,
  } = useChecklistTemplates()

  // Reuse the admin master-data hook so the program picker shows the
  // same list the master-data admin UI exposes (E14 / Journey J7).
  // Universities are also loaded so program labels can disambiguate
  // two programs that happen to share a name across universities.
  const {
    programs,
    universities,
    programsLoading,
    programsError,
  } = useMasterDataAdmin()

  const universityNameById = useMemo(
    () => new Map(universities.map((item) => [item.id, item.name])),
    [universities],
  )

  // Stage filter above the table — purely client-side; the full list
  // is small enough that this is cheap and keeps the API call
  // contract minimal.
  const [stageFilter, setStageFilter] = useState<PipelineStage>(
    () => DEFAULT_STAGE,
  )
  const [editingTemplate, setEditingTemplate] =
    useState<ChecklistItemTemplate | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const createErrorId = useId()
  const updateErrorId = useId()
  const deleteErrorId = useId()
  const successId = useId()
  const stageFilterListId = useId()

  const visibleTemplates = useMemo(() => {
    const filtered = templates.filter((template) => template.stage === stageFilter)
    return [...filtered].sort((a, b) => {
      const aOrder = a.order_index ?? Number.POSITIVE_INFINITY
      const bOrder = b.order_index ?? Number.POSITIVE_INFINITY
      if (aOrder !== bOrder) {
        return aOrder - bOrder
      }
      return a.id - b.id
    })
  }, [templates, stageFilter])

  async function handleCreateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSuccessMessage(null)
    clearErrors()

    const formData = new FormData(event.currentTarget)
    const stageRaw = String(formData.get('stage') ?? '')
    const programIdRaw = String(formData.get('program_id') ?? '')
    const name = String(formData.get('name') ?? '').trim()
    const description = String(formData.get('description') ?? '').trim()
    const requiredRaw = formData.get('required')
    const orderIndexRaw = String(formData.get('order_index') ?? '').trim()

    if (!isStageOption(stageRaw)) {
      return
    }

    let programId: number | null = null
    if (programIdRaw.length > 0) {
      const parsed = Number(programIdRaw)
      if (Number.isFinite(parsed) && parsed > 0) {
        programId = parsed
      }
    }

    let orderIndex: number | null = null
    if (orderIndexRaw.length > 0) {
      const parsed = Number(orderIndexRaw)
      if (Number.isFinite(parsed) && parsed >= 0) {
        orderIndex = Math.trunc(parsed)
      }
    }

    try {
      const created = await createTemplate({
        stage: stageRaw,
        program_id: programId,
        name,
        description: description.length > 0 ? description : null,
        required: requiredRaw === 'on' || requiredRaw === 'true',
        order_index: orderIndex,
      })
      setSuccessMessage(`Template "${created.name}" created.`)
      setStageFilter(created.stage)
      event.currentTarget.reset()
    } catch {
      // createError is set by the hook
    }
  }

  async function handleEditSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editingTemplate) {
      return
    }
    setSuccessMessage(null)
    clearErrors()

    const formData = new FormData(event.currentTarget)
    const stageRaw = String(formData.get('stage') ?? '')
    const programIdRaw = String(formData.get('program_id') ?? '')
    const nameRaw = String(formData.get('name') ?? '').trim()
    const descriptionRaw = String(formData.get('description') ?? '').trim()
    const requiredRaw = formData.get('required')
    const orderIndexRaw = String(formData.get('order_index') ?? '').trim()

    const payload: Partial<{
      stage: PipelineStage
      program_id: number | null
      name: string
      description: string | null
      required: boolean
      order_index: number | null
    }> = {}

    if (isStageOption(stageRaw)) {
      payload.stage = stageRaw
    }

    if (programIdRaw.length === 0) {
      payload.program_id = null
    } else {
      const parsed = Number(programIdRaw)
      if (Number.isFinite(parsed) && parsed > 0) {
        payload.program_id = parsed
      }
    }

    if (nameRaw.length > 0) {
      payload.name = nameRaw
    }

    payload.description = descriptionRaw.length > 0 ? descriptionRaw : null
    payload.required = requiredRaw === 'on' || requiredRaw === 'true'

    if (orderIndexRaw.length === 0) {
      payload.order_index = null
    } else {
      const parsed = Number(orderIndexRaw)
      if (Number.isFinite(parsed) && parsed >= 0) {
        payload.order_index = Math.trunc(parsed)
      }
    }

    try {
      const updated = await updateTemplate(editingTemplate.id, payload)
      setSuccessMessage(`Template "${updated.name}" updated.`)
      setEditingTemplate(null)
      setStageFilter(updated.stage)
    } catch {
      // updateError is set by the hook
    }
  }

  async function handleDelete(template: ChecklistItemTemplate) {
    setSuccessMessage(null)
    clearErrors()
    try {
      await deleteTemplate(template.id)
      if (editingTemplate?.id === template.id) {
        setEditingTemplate(null)
      }
      setSuccessMessage(`Template "${template.name}" deleted.`)
    } catch {
      // deleteError is set by the hook
    }
  }

  function handleStageFilterChange(next: string) {
    if (isStageOption(next)) {
      setStageFilter(next)
      setEditingTemplate(null)
      setSuccessMessage(null)
      clearErrors()
    }
  }

  return (
    <div
      className="checklist-templates-page"
      data-testid="checklist-templates-page"
    >
      <header className="checklist-templates-page__header">
        <h2>Document checklist templates</h2>
        <p className="checklist-templates-page__subtitle">
          Define the documents your consultancy collects from students at each
          pipeline stage. Templates created here appear on the student
          checklist (Journey J19) once their application reaches the matching
          stage and program.
        </p>
      </header>

      {createError ? (
        <p
          className="checklist-templates-page__error"
          role="alert"
          id={createErrorId}
          data-testid="checklist-templates-create-error"
        >
          {createError}
        </p>
      ) : null}
      {updateError ? (
        <p
          className="checklist-templates-page__error"
          role="alert"
          id={updateErrorId}
          data-testid="checklist-templates-update-error"
        >
          {updateError}
        </p>
      ) : null}
      {deleteError ? (
        <p
          className="checklist-templates-page__error"
          role="alert"
          id={deleteErrorId}
          data-testid="checklist-templates-delete-error"
        >
          {deleteError}
        </p>
      ) : null}
      {successMessage ? (
        <p
          className="checklist-templates-page__success"
          role="status"
          id={successId}
          data-testid="checklist-templates-success"
        >
          {successMessage}
        </p>
      ) : null}

      <section
        className="checklist-templates-page__section"
        aria-labelledby="checklist-templates-create-heading"
      >
        <h3 id="checklist-templates-create-heading">Add checklist item</h3>
        <form
          className="checklist-template-form"
          method="post"
          onSubmit={handleCreateSubmit}
          data-testid="checklist-template-create-form"
        >
          <label className="checklist-template-form__field">
            Stage
            <select
              name="stage"
              required
              defaultValue={DEFAULT_STAGE}
              data-testid="checklist-template-create-stage"
            >
              {STAGE_OPTIONS.map((stage) => (
                <option key={stage} value={stage}>
                  {PIPELINE_STAGE_LABELS[stage]}
                </option>
              ))}
            </select>
          </label>
          <label className="checklist-template-form__field">
            Program
            <select
              name="program_id"
              defaultValue=""
              disabled={programsLoading && programs.length === 0}
              data-testid="checklist-template-create-program"
            >
              <option value="">All programs</option>
              {programs.map((program) => (
                <option key={program.id} value={program.id}>
                  {program.name} (
                  {universityNameById.get(program.university_id) ??
                    `University #${program.university_id}`}
                  )
                </option>
              ))}
            </select>
          </label>
          <label className="checklist-template-form__field">
            Document name
            <input
              name="name"
              type="text"
              required
              maxLength={255}
              data-testid="checklist-template-create-name"
            />
          </label>
          <label className="checklist-template-form__field">
            Description
            <textarea
              name="description"
              rows={2}
              maxLength={2000}
              data-testid="checklist-template-create-description"
            />
          </label>
          <label className="checklist-template-form__field checklist-template-form__field--inline">
            <input
              type="checkbox"
              name="required"
              defaultChecked
              data-testid="checklist-template-create-required"
            />
            Required
          </label>
          <label className="checklist-template-form__field">
            Order index
            <input
              name="order_index"
              type="number"
              min={0}
              step={1}
              placeholder="Append at end"
              data-testid="checklist-template-create-order"
            />
          </label>
          {programsError ? (
            <p
              className="checklist-template-form__warning"
              role="alert"
              data-testid="checklist-template-create-programs-warning"
            >
              {programsError}
            </p>
          ) : null}
          <button
            type="submit"
            className="checklist-template-form__submit"
            data-testid="checklist-template-create-submit"
            disabled={submitting}
            aria-busy={submitting}
          >
            {submitting ? 'Saving…' : 'Add template'}
          </button>
        </form>
      </section>

      {editingTemplate ? (
        <section
          className="checklist-templates-page__section"
          aria-labelledby="checklist-templates-edit-heading"
        >
          <h3 id="checklist-templates-edit-heading">Edit checklist item</h3>
          <form
            key={editingTemplate.id}
            className="checklist-template-form checklist-template-form--edit"
            method="post"
            onSubmit={handleEditSubmit}
            data-testid="checklist-template-edit-form"
          >
            <label className="checklist-template-form__field">
              Stage
              <select
                name="stage"
                defaultValue={editingTemplate.stage}
                data-testid="checklist-template-edit-stage"
              >
                {STAGE_OPTIONS.map((stage) => (
                  <option key={stage} value={stage}>
                    {PIPELINE_STAGE_LABELS[stage]}
                  </option>
                ))}
              </select>
            </label>
            <label className="checklist-template-form__field">
              Program
              <select
                name="program_id"
                defaultValue={
                  editingTemplate.program_id === null
                    ? ''
                    : String(editingTemplate.program_id)
                }
                data-testid="checklist-template-edit-program"
              >
                <option value="">All programs</option>
                {programs.map((program) => (
                  <option key={program.id} value={program.id}>
                    {program.name} (
                    {universityNameById.get(program.university_id) ??
                      `University #${program.university_id}`}
                    )
                  </option>
                ))}
              </select>
            </label>
            <label className="checklist-template-form__field">
              Document name
              <input
                name="name"
                type="text"
                required
                maxLength={255}
                defaultValue={editingTemplate.name}
                data-testid="checklist-template-edit-name"
              />
            </label>
            <label className="checklist-template-form__field">
              Description
              <textarea
                name="description"
                rows={2}
                maxLength={2000}
                defaultValue={editingTemplate.description ?? ''}
                data-testid="checklist-template-edit-description"
              />
            </label>
            <label className="checklist-template-form__field checklist-template-form__field--inline">
              <input
                type="checkbox"
                name="required"
                defaultChecked={editingTemplate.required}
                data-testid="checklist-template-edit-required"
              />
              Required
            </label>
            <label className="checklist-template-form__field">
              Order index
              <input
                name="order_index"
                type="number"
                min={0}
                step={1}
                defaultValue={
                  editingTemplate.order_index === null
                    ? ''
                    : String(editingTemplate.order_index)
                }
                placeholder="Append at end"
                data-testid="checklist-template-edit-order"
              />
            </label>
            <div className="checklist-template-form__actions">
              <button
                type="submit"
                data-testid="checklist-template-edit-submit"
                disabled={submitting}
                aria-busy={submitting}
              >
                {submitting ? 'Saving…' : 'Save changes'}
              </button>
              <button
                type="button"
                data-testid="checklist-template-edit-cancel"
                disabled={submitting}
                onClick={() => setEditingTemplate(null)}
              >
                Cancel
              </button>
            </div>
          </form>
        </section>
      ) : null}

      <section
        className="checklist-templates-page__section"
        aria-labelledby="checklist-templates-filter-heading"
      >
        <h3 id="checklist-templates-filter-heading">Templates by stage</h3>
        <div
          className="checklist-templates-page__filters"
          role="tablist"
          aria-label="Pipeline stage"
          id={stageFilterListId}
          data-testid="checklist-templates-stage-filter"
        >
          {STAGE_OPTIONS.map((stage) => (
            <button
              key={stage}
              type="button"
              role="tab"
              aria-selected={stageFilter === stage}
              tabIndex={stageFilter === stage ? 0 : -1}
              data-testid={`checklist-templates-stage-tab-${stage}`}
              className={
                stageFilter === stage
                  ? 'checklist-templates-page__tab checklist-templates-page__tab--active'
                  : 'checklist-templates-page__tab'
              }
              onClick={() => handleStageFilterChange(stage)}
            >
              {PIPELINE_STAGE_LABELS[stage]}
            </button>
          ))}
        </div>

        {loading ? (
          <p role="status" data-testid="checklist-templates-loading">
            Loading templates…
          </p>
        ) : null}
        {!loading && !hasAccessToken() ? (
          <p data-testid="checklist-templates-unauthenticated">
            Please log in to manage checklist templates.
          </p>
        ) : null}
        {error ? (
          <p
            className="checklist-templates-page__error"
            role="alert"
            data-testid="checklist-templates-error"
          >
            {error}
          </p>
        ) : null}
        {!loading && !error && visibleTemplates.length === 0 ? (
          <p data-testid="checklist-templates-empty">
            No templates configured for {PIPELINE_STAGE_LABELS[stageFilter]} yet.
          </p>
        ) : null}
        {!loading && !error && visibleTemplates.length > 0 ? (
          <div className="checklist-templates-page__table-wrapper">
            <table
              className="checklist-template-table"
              data-testid="checklist-template-table"
            >
              <thead>
                <tr>
                  <th scope="col">Document</th>
                  <th scope="col">Program</th>
                  <th scope="col">Required</th>
                  <th scope="col">Order</th>
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visibleTemplates.map((template) => (
                  <tr
                    key={template.id}
                    data-testid={`checklist-template-row-${template.id}`}
                  >
                    <td>
                      <div className="checklist-template-table__name">
                        {template.name}
                      </div>
                      {template.description ? (
                        <div className="checklist-template-table__description">
                          {template.description}
                        </div>
                      ) : null}
                    </td>
                    <td>{programLabelFor(programs, template.program_id)}</td>
                    <td>
                      <span
                        className={
                          template.required
                            ? 'checklist-template-table__required checklist-template-table__required--yes'
                            : 'checklist-template-table__required checklist-template-table__required--no'
                        }
                        data-testid={`checklist-template-required-${template.id}`}
                      >
                        {template.required ? 'Required' : 'Optional'}
                      </span>
                    </td>
                    <td>
                      {template.order_index === null ? '—' : template.order_index}
                    </td>
                    <td>
                      <div className="checklist-template-table__actions">
                        <button
                          type="button"
                          data-testid={`checklist-template-edit-${template.id}`}
                          onClick={() => {
                            setEditingTemplate(template)
                            setSuccessMessage(null)
                          }}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          data-testid={`checklist-template-delete-${template.id}`}
                          disabled={deletingId === template.id}
                          aria-busy={deletingId === template.id}
                          onClick={() => void handleDelete(template)}
                        >
                          {deletingId === template.id ? 'Deleting…' : 'Delete'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  )
}
