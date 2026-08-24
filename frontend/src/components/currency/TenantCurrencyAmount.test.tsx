import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

import TenantCurrencyAmount from './TenantCurrencyAmount'
import { AuthProvider } from '../../store/authStore'
import { DEFAULT_CURRENCY_CODE } from './formatCurrencyAmount'

const mockUserWithTenant = {
  id: 1,
  email: 'admin@demo.test',
  role: 'super_admin' as const,
  tenant_id: 7,
  branch_id: null,
}

function makeTenant(currency: string | null) {
  return {
    id: 7,
    name: 'Apex EduConsult',
    slug: 'apex',
    logo_url: 'https://cdn.example.test/apex/logo.png',
    brand_color: '#1A2B3C',
    currency,
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  }
}

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}

function installAuthAndTenant(
  fetchSpy: ReturnType<typeof vi.spyOn>,
  tenant: ReturnType<typeof makeTenant>,
) {
  fetchSpy
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockUserWithTenant,
    } as unknown as Response)
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => tenant,
    } as unknown as Response)
}

describe('TenantCurrencyAmount', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    fetchSpy = vi.spyOn(globalThis, 'fetch')
  })

  afterEach(() => {
    fetchSpy.mockRestore()
  })

  it('renders the default currency before the tenant branding loads', () => {
    // No authenticated user, no fetch will fire: the hook falls back to
    // the curated default immediately and the rendered amount uses
    // that code's locale formatting.
    render(
      <TenantCurrencyAmount amount={1234.56} testId="amount" />,
      { wrapper },
    )

    const node = screen.getByTestId('amount')
    expect(node.dataset.currencyCode).toBe(DEFAULT_CURRENCY_CODE)
    expect(node.textContent).toContain(DEFAULT_CURRENCY_CODE)
    expect(node.textContent).toMatch(/1,234\.56/)
  })

  it('renders the tenant currency once the branding record resolves', async () => {
    localStorage.setItem('access_token', 'test-token')
    installAuthAndTenant(fetchSpy, makeTenant('USD'))

    render(
      <TenantCurrencyAmount amount={1234.56} testId="amount" />,
      { wrapper },
    )

    await waitFor(() => {
      const node = screen.getByTestId('amount')
      expect(node.dataset.currencyCode).toBe('USD')
    })

    const node = screen.getByTestId('amount')
    expect(node.textContent).toContain('USD')
    expect(node.textContent).toMatch(/1,234\.56/)
  })

  it('honours an explicit currencyCode prop without consulting the tenant', async () => {
    localStorage.setItem('access_token', 'test-token')
    // Server-side currency is EUR, but the caller explicitly asks for
    // GBP -- the explicit prop must win, so the rendered code is GBP
    // and no double rendering of EUR occurs.
    installAuthAndTenant(fetchSpy, makeTenant('EUR'))

    render(
      <TenantCurrencyAmount
        amount={500}
        currencyCode="GBP"
        testId="amount"
      />,
      { wrapper },
    )

    const node = screen.getByTestId('amount')
    expect(node.dataset.currencyCode).toBe('GBP')
    expect(node.textContent).toContain('GBP')
    expect(node.textContent).not.toContain('EUR')
  })

  it('renders a placeholder instead of throwing when the resolved code is invalid', async () => {
    localStorage.setItem('access_token', 'test-token')
    installAuthAndTenant(fetchSpy, makeTenant('not-a-code'))

    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    render(
      <TenantCurrencyAmount amount={100} testId="amount" />,
      { wrapper },
    )

    // The hook rejects unsupported / invalid codes by falling back to
    // the default, so the rendered span must carry the default code
    // rather than crashing.
    await waitFor(() => {
      const node = screen.getByTestId('amount')
      expect(node.dataset.currencyCode).toBe(DEFAULT_CURRENCY_CODE)
    })

    expect(warn).not.toHaveBeenCalled()
  })
})