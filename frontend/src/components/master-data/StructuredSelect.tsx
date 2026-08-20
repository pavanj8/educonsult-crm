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
  placeholder: string
  emptyMessage: string
  loadingMessage?: string
  describedBy?: string
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
  placeholder,
  emptyMessage,
  loadingMessage = 'Loading…',
  describedBy,
  'data-testid': testId,
}: StructuredSelectProps) {
  const selectDisabled = disabled || loading

  return (
    <label className="login-form__field">
      {label}
      <select
        data-testid={testId}
        name={name}
        value={value}
        disabled={selectDisabled}
        aria-describedby={describedBy}
        onChange={(event) => {
          const nextValue = event.target.value
          onChange(nextValue === '' ? '' : Number.parseInt(nextValue, 10))
        }}
      >
        <option value="">{placeholder}</option>
        {loading ? (
          <option value="" disabled>
            {loadingMessage}
          </option>
        ) : options.length === 0 ? (
          <option value="" disabled>
            {emptyMessage}
          </option>
        ) : (
          options.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))
        )}
      </select>
    </label>
  )
}
