import CountrySelect from './CountrySelect'
import ProgramSelect from './ProgramSelect'
import UniversitySelect from './UniversitySelect'

type StudyPreferencesFieldsetProps = {
  tenantSlug: string
  countryId: number | ''
  universityId: number | ''
  programId: number | ''
  onCountryChange: (value: number | '') => void
  onUniversityChange: (value: number | '') => void
  onProgramChange: (value: number | '') => void
  describedBy?: string
}

export default function StudyPreferencesFieldset({
  tenantSlug,
  countryId,
  universityId,
  programId,
  onCountryChange,
  onUniversityChange,
  onProgramChange,
  describedBy,
}: StudyPreferencesFieldsetProps) {
  return (
    <fieldset className="login-form__section">
      <legend>Study preferences</legend>
      <CountrySelect
        tenantSlug={tenantSlug}
        value={countryId}
        onChange={onCountryChange}
        describedBy={describedBy}
      />
      <UniversitySelect
        tenantSlug={tenantSlug}
        countryId={countryId}
        value={universityId}
        onChange={onUniversityChange}
        describedBy={describedBy}
      />
      <ProgramSelect
        tenantSlug={tenantSlug}
        universityId={universityId}
        value={programId}
        onChange={onProgramChange}
        describedBy={describedBy}
      />
    </fieldset>
  )
}
