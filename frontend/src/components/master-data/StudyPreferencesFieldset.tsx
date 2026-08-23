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
   * The shared default ``'master-data-'`` keeps the fieldset namespaced
   * independently of any specific consuming page; callers like the E16
   * self-registration flow override this with ``'register-'`` and the
   * E17 receptionist intake form with ``'intake-'`` so test ids read
   * in context.
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
  idPrefix = 'master-data-',
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
