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
  const { items: universities, loading, error } = useUniversities(tenantSlug, countryId, {
    enabled: !disabled && typeof countryId === 'number',
  })

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
      disabled={disabled || typeof countryId !== 'number'}
      placeholder="Select a university"
      emptyMessage="No universities available"
      loadingMessage="Loading universities…"
      describedBy={describedBy}
        data-testid="register-target-university"
      />
      {error ? (
        <p className="login-form__error" role="alert" data-testid="register-universities-error">
          {error}
        </p>
      ) : null}
    </>
  )
}
