import { useId } from 'react'

import StructuredSelect from './StructuredSelect'
import { useUniversities } from '../../hooks/useMasterData'

type UniversitySelectProps = {
  tenantSlug: string
  countryId: number | ''
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

export default function UniversitySelect({
  tenantSlug,
  countryId,
  value,
  onChange,
  disabled = false,
  describedBy,
  idPrefix = 'register-',
}: UniversitySelectProps) {
  const errorId = useId()
  const waitingForCountry = typeof countryId !== 'number'
  const { items: universities, loading, error } = useUniversities(tenantSlug, countryId, {
    enabled: !disabled && !waitingForCountry,
  })
  const describedByIds = [describedBy, error ? errorId : undefined].filter(Boolean).join(' ') || undefined

  return (
    <>
      <StructuredSelect
        name="target_university_id"
        label="Target university"
        value={value}
        onChange={onChange}
        options={universities.map((university) => ({ id: university.id, label: university.name }))}
        loading={loading}
        disabled={disabled}
        waitingForUpstream={waitingForCountry}
        placeholder="Select a university"
        emptyMessage="No universities available"
        loadingMessage="Loading universities…"
        waitingMessage="Select a country first"
        describedBy={describedByIds}
        errorId={error ? errorId : undefined}
        data-testid={`${idPrefix}target-university`}
      />
      {error ? (
        <p
          className="login-form__error"
          role="alert"
          id={errorId}
          data-testid={`${idPrefix}universities-error`}
        >
          {error}
        </p>
      ) : null}
    </>
  )
}
