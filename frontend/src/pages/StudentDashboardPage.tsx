import { useId, useMemo, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'

import {
  DEMO_UNIVERSITIES,
  programName,
  programsForUniversity,
  universityName,
} from '../data/demoMasterData'
import { useApplications } from '../hooks/useApplications'
import { useCreateApplication } from '../hooks/useCreateApplication'
import ApplicationRow from '../components/documents/ApplicationRow'
import UpcomingMeetings from '../components/meetings/UpcomingMeetings'

function formatStageLabel(stage: string): string {
  return stage
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export default function StudentDashboardPage() {
  const { applications, loading, error, reload } = useApplications()
  const { submitting, createError, createApplication } = useCreateApplication()
  const [selectedUniversityId, setSelectedUniversityId] = useState<number | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [applicationLoanOptIn, setApplicationLoanOptIn] = useState<Record<number, boolean>>({})
  const errorId = useId()
  const successId = useId()

  const availablePrograms = useMemo(() => {
    if (selectedUniversityId == null) {
      return []
    }
    return programsForUniversity(selectedUniversityId)
  }, [selectedUniversityId])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSuccessMessage(null)
    setValidationError(null)

    const formData = new FormData(event.currentTarget)
    const universityIdValue = Number(formData.get('university_id'))
    const programIdValue = Number(formData.get('program_id'))

    if (
      !Number.isFinite(universityIdValue) ||
      universityIdValue < 1 ||
      !Number.isFinite(programIdValue) ||
      programIdValue < 1
    ) {
      setValidationError('Select a university and program to continue.')
      return
    }

    try {
      const created = await createApplication({
        university_id: universityIdValue,
        program_id: programIdValue,
      })
      const universityLabel = universityName(created.university_id)
      const programLabel =
        programName(created.university_id, created.program_id) ??
        `Program #${created.program_id}`
      setSuccessMessage(
        `Application created for ${programLabel} at ${universityLabel}. Current stage: ${formatStageLabel(created.stage)}.`,
      )
      event.currentTarget.reset()
      setSelectedUniversityId(null)
      await reload()
    } catch {
      // createError is set by the hook
    }
  }

  function handleUniversityChange(event: ChangeEvent<HTMLSelectElement>) {
    const value = Number(event.target.value)
    setSelectedUniversityId(Number.isFinite(value) && value >= 1 ? value : null)
    setSuccessMessage(null)
    setValidationError(null)
  }

  function handleLoanOptInChange(applicationId: number, loanOptIn: boolean) {
    setApplicationLoanOptIn((prev) => ({ ...prev, [applicationId]: loanOptIn }))
  }

  const errorMessage = validationError ?? createError
  const statusMessage = errorMessage ? errorId : successMessage ? successId : undefined

  return (
    <div className="student-dashboard" data-testid="student-dashboard-page">
      <header className="student-dashboard__header">
        <h2>Student dashboard</h2>
        <p className="student-dashboard__subtitle">
          Start a new university application or track your study abroad journey.
        </p>
      </header>

      <section
        className="student-dashboard__section"
        aria-labelledby="applications-list-heading"
      >
        <h3 id="applications-list-heading">My applications</h3>
        {loading && <p className="student-dashboard__status">Loading applications…</p>}
        {error && (
          <p
            className="student-dashboard__status student-dashboard__status--error"
            role="alert"
          >
            {error}
          </p>
        )}
        {!loading && !error && applications.length === 0 && (
          <p className="student-dashboard__status">No applications yet.</p>
        )}
        {!loading && !error && applications.length > 0 && (
          <div className="application-table-wrapper">
            <table className="application-table" data-testid="application-table">
              <thead>
                <tr>
                  <th scope="col">University</th>
                  <th scope="col">Program</th>
                  <th scope="col">Stage</th>
                  <th scope="col">Created</th>
                  <th scope="col">Loan tracking</th>
                  <th scope="col">Documents</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((application) => (
                  <ApplicationRow
                    key={application.id}
                    application={{
                      ...application,
                      loan_opt_in:
                        applicationLoanOptIn[application.id] ?? application.loan_opt_in,
                    }}
                    universityName={universityName(application.university_id)}
                    programName={
                      programName(application.university_id, application.program_id) ??
                      `Program #${application.program_id}`
                    }
                    createdAt={application.created_at}
                    onLoanOptInChanged={handleLoanOptInChange}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/*
        The UpcomingMeetings widget renders its own <section> with an
        internally-generated heading id (via useId()) so the section
        landmark + accessible name are owned by the widget itself.
        Wrapping it in another labelled section here would reference a
        phantom id and leave the section unlabeled for screen readers.
      */}
      <div className="student-dashboard__section">
        <UpcomingMeetings />
      </div>

      <section
        className="student-dashboard__section"
        aria-labelledby="new-application-heading"
      >
        <h3 id="new-application-heading">New application</h3>
        <p className="student-dashboard__hint">
          Choose the university and program you want to apply for. You can create multiple
          applications in parallel.
        </p>
        <form
          className="application-form"
          method="post"
          onSubmit={handleSubmit}
          aria-describedby={statusMessage}
        >
          <label className="application-form__field">
            University
            <select
              data-testid="application-university"
              name="university_id"
              required
              defaultValue=""
              onChange={handleUniversityChange}
            >
              <option value="" disabled>
                Select a university
              </option>
              {DEMO_UNIVERSITIES.map((university) => (
                <option key={university.id} value={university.id}>
                  {university.name} ({university.country})
                </option>
              ))}
            </select>
          </label>
          <label className="application-form__field">
            Program
            <select
              key={selectedUniversityId ?? 'none'}
              data-testid="application-program"
              name="program_id"
              required
              defaultValue=""
              disabled={selectedUniversityId == null || availablePrograms.length === 0}
            >
              <option value="" disabled>
                {selectedUniversityId == null
                  ? 'Select a university first'
                  : availablePrograms.length === 0
                    ? 'No programs available'
                    : 'Select a program'}
              </option>
              {availablePrograms.map((program) => (
                <option key={program.id} value={program.id}>
                  {program.name}
                </option>
              ))}
            </select>
          </label>
          {validationError ? (
            <p
              className="application-form__error"
              data-testid="application-validation-error"
              id={errorId}
              role="alert"
            >
              {validationError}
            </p>
          ) : null}
          {createError ? (
            <p
              className="application-form__error"
              data-testid="application-error"
              id={validationError ? undefined : errorId}
              role="alert"
            >
              {createError}
            </p>
          ) : null}
          {successMessage ? (
            <p
              className="application-form__success"
              data-testid="application-success"
              id={successId}
              role="status"
            >
              {successMessage}
            </p>
          ) : null}
          <button
            className="application-form__submit"
            data-testid="application-submit"
            type="submit"
            disabled={submitting}
            aria-busy={submitting}
          >
            {submitting ? 'Creating application…' : 'Create application'}
          </button>
        </form>
      </section>
    </div>
  )
}
