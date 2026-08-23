import { useId } from 'react'

import StructuredSelect from './StructuredSelect'
import { useCountries } from '../../hooks/useMasterData'

type CountrySelectProps = {
  tenantSlug: string
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

export default function CountrySelect({
  tenantSlug,
  value,
  onChange,
  disabled = false,
  describedBy,
  idPrefix = 'master-data-',
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
        data-testid={`${idPrefix}target-country`}
      />
      {error ? (
        <p
          className="login-form__error"
          role="alert"
          id={errorId}
          data-testid={`${idPrefix}countries-error`}
        >
          {error}
        </p>
      ) : null}
    </>
  )
}
