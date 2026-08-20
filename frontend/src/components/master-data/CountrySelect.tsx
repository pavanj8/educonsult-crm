import { useId } from 'react'

import StructuredSelect from './StructuredSelect'
import { useCountries } from '../../hooks/useMasterData'

type CountrySelectProps = {
  tenantSlug: string
  value: number | ''
  onChange: (value: number | '') => void
  disabled?: boolean
  describedBy?: string
}

export default function CountrySelect({
  tenantSlug,
  value,
  onChange,
  disabled = false,
  describedBy,
}: CountrySelectProps) {
  const errorId = useId()
  const { items: countries, loading, error } = useCountries(tenantSlug, {
    enabled: !disabled,
  })
  const describedByIds = [describedBy, error ? errorId : undefined].filter(Boolean).join(' ') || undefined

  return (
    <>
      <StructuredSelect
        name="target_country_id"
        label="Target country"
        value={value}
        onChange={onChange}
        options={countries.map((country) => ({ id: country.id, label: country.name }))}
        loading={loading}
        disabled={disabled || tenantSlug.trim().length === 0}
        placeholder="Select a country"
        emptyMessage="No countries available"
        loadingMessage="Loading countries…"
        describedBy={describedByIds}
        errorId={error ? errorId : undefined}
        data-testid="register-target-country"
      />
      {error ? (
        <p
          className="login-form__error"
          role="alert"
          id={errorId}
          data-testid="register-countries-error"
        >
          {error}
        </p>
      ) : null}
    </>
  )
}
