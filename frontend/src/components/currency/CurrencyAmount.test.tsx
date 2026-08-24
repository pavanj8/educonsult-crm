import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import CurrencyAmount from './CurrencyAmount'

describe('CurrencyAmount', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the formatted amount with the supplied currency code', () => {
    render(<CurrencyAmount amount={1234.56} currencyCode="USD" testId="amount" />)
    const node = screen.getByTestId('amount')
    expect(node.textContent).toMatch(/1,234\.56/)
    expect(node.textContent).toContain('USD')
    expect(node.dataset.currencyCode).toBe('USD')
  })

  it('uses the default testid when none is supplied', () => {
    render(<CurrencyAmount amount={100} currencyCode="EUR" />)
    expect(screen.getByTestId('currency-amount')).toBeInTheDocument()
  })

  it('passes the className through to the rendered span', () => {
    const { container } = render(
      <CurrencyAmount
        amount={42}
        currencyCode="GBP"
        className="loan-amount"
      />,
    )
    const node = container.querySelector('.loan-amount')
    expect(node).not.toBeNull()
    expect(node?.textContent).toContain('GBP')
  })

  it('renders integer amounts without a forced fractional part', () => {
    render(<CurrencyAmount amount={1000} currencyCode="USD" testId="amount" />)
    const node = screen.getByTestId('amount')
    // The formatter strips trailing zeros; ``1000`` renders without
    // ``.00`` so the surface matches what the backend produces.
    expect(node.textContent).toMatch(/1,000(?!\.)/)
  })

  it('accepts a numeric string as the amount', () => {
    render(<CurrencyAmount amount="1234.56" currencyCode="USD" testId="amount" />)
    expect(screen.getByTestId('amount').textContent).toMatch(/1,234\.56/)
  })

  it('renders a placeholder instead of throwing on an invalid currency code', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    render(<CurrencyAmount amount={100} currencyCode="not-a-code" testId="amount" />)

    expect(screen.queryByTestId('amount')).toBeNull()
    const placeholder = screen.getByTestId('amount-placeholder')
    expect(placeholder.textContent).toBe('—')
    expect(placeholder.getAttribute('aria-label')).toBe('unavailable amount')
    expect(warn).toHaveBeenCalled()
  })

  it('renders a placeholder instead of throwing on a non-finite amount', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    render(<CurrencyAmount amount={NaN} currencyCode="USD" testId="amount" />)

    expect(screen.queryByTestId('amount')).toBeNull()
    const placeholder = screen.getByTestId('amount-placeholder')
    expect(placeholder).toBeInTheDocument()
    expect(placeholder.getAttribute('aria-label')).toBe('unavailable amount')
    expect(warn).toHaveBeenCalled()
  })

  it('still renders when amount is zero', () => {
    render(<CurrencyAmount amount={0} currencyCode="USD" testId="amount" />)
    const node = screen.getByTestId('amount')
    expect(node.textContent).toContain('0')
    expect(node.textContent).toContain('USD')
    // The code must appear exactly once: ``Intl.NumberFormat({ currencyDisplay: 'code' })``
    // already includes the code in the formatted string.
    expect(node.textContent?.match(/USD/g)).toHaveLength(1)
  })
})
