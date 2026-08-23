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
  /**
   * Prefix used to build the ``data-testid`` attributes on each select.
   * The default ``'register-'`` matches the public E16 self-registration
   * flow; alternative callers (e.g. the E17 receptionist intake form)
   * override this so each caller's test ids read in context — without
   * changing the shared fieldset's own internal contract.
   */
  idPrefix?: string
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
  idPrefix = 'register-',
}: StudyPreferencesFieldsetProps) {
  return (
    <fieldset className="login-form__section">
      <legend>Study preferences</legend>
      <CountrySelect
        tenantSlug={tenantSlug}
        value={countryId}
        onChange={onCountryChange}
        describedBy={describedBy}
        idPrefix={idPrefix}
      />
      <UniversitySelect
        tenantSlug={tenantSlug}
        countryId={countryId}
        value={universityId}
        onChange={onUniversityChange}
        describedBy={describedBy}
        idPrefix={idPrefix}
      />
      <ProgramSelect
        tenantSlug={tenantSlug}
        universityId={universityId}
        value={programId}
        onChange={onProgramChange}
        describedBy={describedBy}
        idPrefix={idPrefix}
      />
    </fieldset>
  )
}
