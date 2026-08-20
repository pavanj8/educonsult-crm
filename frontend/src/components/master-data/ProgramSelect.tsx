import StructuredSelect from './StructuredSelect'
import { usePrograms } from '../../hooks/useMasterData'

type ProgramSelectProps = {
  tenantSlug: string
  universityId: number | ''
  value: number | ''
  onChange: (value: number | '') => void
  disabled?: boolean
  describedBy?: string
}

export default function ProgramSelect({
  tenantSlug,
  universityId,
  value,
  onChange,
  disabled = false,
  describedBy,
}: ProgramSelectProps) {
  const { items: programs, loading, error } = usePrograms(tenantSlug, universityId, {
    enabled: !disabled && typeof universityId === 'number',
  })

  return (
    <>
      <StructuredSelect
      name="target_program_id"
      label="Target program"
      value={value}
      onChange={onChange}
      options={programs.map((program) => ({ id: program.id, label: program.name }))}
      loading={loading}
      disabled={disabled || typeof universityId !== 'number'}
      placeholder="Select a program"
      emptyMessage="No programs available"
      loadingMessage="Loading programs…"
      describedBy={describedBy}
        data-testid="register-target-program"
      />
      {error ? (
        <p className="login-form__error" role="alert" data-testid="register-programs-error">
          {error}
        </p>
      ) : null}
    </>
  )
}
