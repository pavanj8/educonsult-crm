import { useId } from 'react'

import StructuredSelect from './StructuredSelect'
import { usePrograms } from '../../hooks/useMasterData'

type ProgramSelectProps = {
  tenantSlug: string
  universityId: number | ''
  value: number | ''
  onChange: (value: number | '') => void
  disabled?: boolean
  describedBy?: string
  /**
   * Prefix used to build the ``data-testid`` attributes on the underlying
   * select and on the error message. The default ``'register-'`` matches
   * the public E16 self-registration flow; alternative callers (e.g. the
   * E17 receptionist intake form) override this so each caller's test ids
   * read in context — without changing the shared fieldset's own
   * internal contract.
   */
  idPrefix?: string
}

export default function ProgramSelect({
  tenantSlug,
  universityId,
  value,
  onChange,
  disabled = false,
  describedBy,
  idPrefix = 'register-',
}: ProgramSelectProps) {
  const errorId = useId()
  const waitingForUniversity = typeof universityId !== 'number'
  const { items: programs, loading, error } = usePrograms(tenantSlug, universityId, {
    enabled: !disabled && !waitingForUniversity,
  })
  const describedByIds = [describedBy, error ? errorId : undefined].filter(Boolean).join(' ') || undefined

  return (
    <>
      <StructuredSelect
        name="target_program_id"
        label="Target program"
        value={value}
        onChange={onChange}
        options={programs.map((program) => ({ id: program.id, label: program.name }))}
        loading={loading}
        disabled={disabled}
        waitingForUpstream={waitingForUniversity}
        placeholder="Select a program"
        emptyMessage="No programs available"
        loadingMessage="Loading programs…"
        waitingMessage="Select a university first"
        describedBy={describedByIds}
        errorId={error ? errorId : undefined}
        data-testid={`${idPrefix}target-program`}
      />
      {error ? (
        <p
          className="login-form__error"
          role="alert"
          id={errorId}
          data-testid={`${idPrefix}programs-error`}
        >
          {error}
        </p>
      ) : null}
    </>
  )
}
