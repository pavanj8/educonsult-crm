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
   * select and on the error message. The shared default
   * ``'master-data-'`` keeps the select namespaced independently of any
   * specific consuming page; callers like the E16 self-registration
   * flow override this with ``'register-'`` and the E17 receptionist
   * intake form with ``'intake-'`` so test ids read in context.
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
  idPrefix = 'master-data-',
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
