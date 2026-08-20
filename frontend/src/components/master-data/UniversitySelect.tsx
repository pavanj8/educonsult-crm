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
}

export default function UniversitySelect({
  tenantSlug,
  countryId,
  value,
  onChange,
  disabled = false,
  describedBy,
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
        options={universities.map((university) => ({
          id: university.id,
          label: university.name,
        }))}
        loading={loading}
        disabled={disabled}
        waitingForUpstream={waitingForCountry}
        placeholder="Select a university"
        emptyMessage="No universities available"
        loadingMessage="Loading universities…"
        waitingMessage="Select a country first"
        describedBy={describedByIds}
        errorId={error ? errorId : undefined}
        data-testid="register-target-university"
      />
      {error ? (
        <p
          className="login-form__error"
          role="alert"
          id={errorId}
          data-testid="register-universities-error"
        >
          {error}
        </p>
      ) : null}
    </>
  )
}
