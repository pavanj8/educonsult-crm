import { useId } from 'react'

type StructuredSelectOption = {
  id: number
  label: string
}

type StructuredSelectProps = {
  name: string
  label: string
  value: number | ''
  onChange: (value: number | '') => void
  options: StructuredSelectOption[]
  loading: boolean
  disabled?: boolean
  waitingForUpstream?: boolean
  placeholder: string
  emptyMessage: string
  loadingMessage?: string
  waitingMessage?: string
  describedBy?: string
  errorId?: string
  'data-testid': string
}

export default function StructuredSelect({
  name,
  label,
  value,
  onChange,
  options,
  loading,
  disabled = false,
  waitingForUpstream = false,
  placeholder,
  emptyMessage,
  loadingMessage = 'Loading…',
  waitingMessage,
  describedBy,
  errorId,
  'data-testid': testId,
}: StructuredSelectProps) {
  const helperId = useId()
  const describedByIds = [describedBy, errorId, helperId].filter(Boolean).join(' ') || undefined
  const selectDisabled = disabled || loading || waitingForUpstream
  const helperText = waitingForUpstream
    ? (waitingMessage ?? placeholder)
    : loading
      ? loadingMessage
      : !selectDisabled && options.length === 0
        ? emptyMessage
        : null

  return (
    <label className="login-form__field">
      {label}
      <select
        data-testid={testId}
        name={name}
        value={value}
        disabled={selectDisabled}
        aria-busy={loading}
        aria-describedby={describedByIds}
        aria-errormessage={errorId}
        onChange={(event) => {
          const nextValue = event.target.value
          onChange(nextValue === '' ? '' : Number.parseInt(nextValue, 10))
        }}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
      {helperText ? (
        <span className="login-form__hint" id={helperId}>
          {helperText}
        </span>
      ) : null}
    </label>
  )
}
