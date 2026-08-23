import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * Mutable auth-state holder the auth mock reads from on every render.
 *
 * **Mutate before ``render``, not after.** Each ``render()`` call evaluates
 * the ``useAuth: () => ({...authState})`` factory fresh, so any test that
 * sets ``authState.tenant_id = null`` etc. before the initial render will
 * see the new value. Mutating ``authState`` mid-flow without a fresh
 * ``render()`` (or an explicit ``rerender()``) will silently leave the
 * previously-rendered component reading the OLD value, because the mock
 * factory does not subscribe to React's render lifecycle — it just reads
 * the mutable object each time ``useAuth`` is called.
 */
const authState: {
  id: number
  email: string
  tenant_id: number | null
} = {
  id: 50,
  email: 'owner@apex.test',
  tenant_id: 10,
}

vi.mock('../store/authStore', () => ({
  useAuth: () => ({
    user: {
      id: authState.id,
      email: authState.email,
      role: 'consultancy_owner',
      tenant_id: authState.tenant_id,
      branch_id: null,
    },
    isAuthenticated: true,
    isLoading: false,
    error: null,
    login: vi.fn(),
    registerStudent: vi.fn(),
    logout: vi.fn(),
    refreshSession: vi.fn(),
    clearError: vi.fn(),
  }),
}))

// Imported after the mock so the page picks up the mocked auth store.
import TenantBrandingPage from './TenantBrandingPage'

const baseTenant = {
  id: 10,
  name: 'Apex EduConsult',
  slug: 'apex',
  logo_url: null,
  brand_color: '#1f6feb',
  currency: 'USD',
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
}

const brandedTenant = {
  ...baseTenant,
  logo_url: 'https://cdn.example.test/tenants/10/logo.png',
  brand_color: '#ff8800',
  currency: 'EUR',
  updated_at: '2026-01-20T10:00:00Z',
}

function mockFetchOnce(
  impl: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>,
) {
  globalThis.fetch = vi.fn(impl) as typeof fetch
}

function okJson(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  } as Response
}

function errorJson(status: number, detail: string): Response {
  return {
    ok: false,
    status,
    json: async () => ({ detail }),
  } as Response
}

describe('TenantBrandingPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
    // Reset auth state to the happy path before every test.
    authState.id = 50
    authState.email = 'owner@apex.test'
    authState.tenant_id = 10
  })

  it('renders the branding form for an authenticated consultancy owner (hydrated)', async () => {
    mockFetchOnce(async () => okJson(baseTenant))
    render(<TenantBrandingPage />)

    // Inputs must reflect what the GET returned, not the empty default.
    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-color')).toHaveValue('#1f6feb')
    })
    expect(screen.getByTestId('tenant-branding-currency')).toHaveValue('USD')
    expect(screen.getByTestId('tenant-branding-page')).toBeInTheDocument()
    expect(screen.getByTestId('tenant-branding-submit')).toBeInTheDocument()
    expect(screen.getByTestId('tenant-branding-logo-submit')).toBeInTheDocument()
    expect(screen.getByTestId('tenant-branding-logo-empty')).toBeInTheDocument()
  })

  it('hydrates the form from existing branded tenant values (regression: first-save data loss)', async () => {
    mockFetchOnce(async () => okJson(brandedTenant))
    render(<TenantBrandingPage />)

    // Critical regression test: a consultancy owner who has already saved
    // a logo + brand color + non-default currency must see those values in
    // the form before they touch anything. Without the initial GET this
    // assertion would fail (form would still show the empty defaults), and
    // a submit would silently wipe the saved values.
    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-color')).toHaveValue('#ff8800')
    })
    expect(screen.getByTestId('tenant-branding-currency')).toHaveValue('EUR')
    expect(screen.getByTestId('tenant-branding-logo-image')).toBeInTheDocument()
    expect(screen.getByTestId('tenant-branding-logo-image')).toHaveAttribute(
      'src',
      'https://cdn.example.test/tenants/10/logo.png',
    )
  })

  it('disables submit until the initial GET resolves, so a save cannot clobber existing settings', async () => {
    let resolveFetch: (value: Response) => void = () => {
      /* noop */
    }
    globalThis.fetch = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve
        }),
    ) as typeof fetch

    render(<TenantBrandingPage />)

    // While the GET is pending the real form must NOT be mounted — we
    // render an aria-busy skeleton instead so the user cannot mistake
    // the prefilled empty inputs for "you need to type a color here".
    // The submit button only exists once the real form has mounted.
    expect(screen.queryByTestId('tenant-branding-submit')).not.toBeInTheDocument()
    expect(screen.getByTestId('tenant-branding-form-skeleton')).toBeInTheDocument()
    expect(screen.getByTestId('tenant-branding-form-skeleton')).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(screen.getByTestId('tenant-branding-color-skeleton')).toHaveAttribute(
      'aria-busy',
      'true',
    )
    // The logo upload submit also lives behind the hydration gate.
    expect(screen.getByTestId('tenant-branding-logo-submit')).toBeDisabled()

    // Resolve the GET; the skeleton unmounts and the real form mounts
    // with hydrated values.
    resolveFetch(okJson(brandedTenant))

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-submit')).not.toBeDisabled()
    })
    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-color')).toHaveValue('#ff8800')
    })
    // The skeleton is gone.
    expect(screen.queryByTestId('tenant-branding-form-skeleton')).not.toBeInTheDocument()
  })

  it('patches branding settings and shows the server-normalised response', async () => {
    const user = userEvent.setup()
    const updated = {
      ...baseTenant,
      brand_color: '#FF8800',
      currency: 'EUR',
      updated_at: '2026-02-01T10:00:00Z',
    }
    const fetchMock = vi.fn().mockImplementation(async (_input, init) => {
      // The first call must be the initial GET; the second is the PATCH.
      if (init?.method === 'PATCH') {
        const body = JSON.parse(String(init.body))
        expect(body).toEqual({
          logo_url: null,
          brand_color: '#FF8800',
          currency: 'EUR',
        })
        return okJson(updated)
      }
      return okJson(baseTenant)
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(<TenantBrandingPage />)

    // Wait for hydration from baseTenant (color #1f6feb, currency USD).
    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-color')).toHaveValue('#1f6feb')
    })

    await user.clear(screen.getByTestId('tenant-branding-color'))
    await user.type(screen.getByTestId('tenant-branding-color'), '#FF8800')
    await user.selectOptions(screen.getByTestId('tenant-branding-currency'), 'EUR')
    await user.click(screen.getByTestId('tenant-branding-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-success')).toBeInTheDocument()
    })

    expect(screen.getByTestId('tenant-branding-success')).toHaveTextContent(
      'Branding settings saved',
    )
    expect(screen.getByTestId('tenant-branding-currency')).toHaveValue('EUR')
    expect(screen.getByTestId('tenant-branding-updated-at')).toHaveTextContent(/Last saved:/)
  })

  it('surfaces backend errors from the branding PATCH', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockImplementation(async (_input, init) => {
      if (init?.method === 'PATCH') {
        return errorJson(422, 'Brand color must be a #RRGGBB hex value')
      }
      return okJson(baseTenant)
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(<TenantBrandingPage />)

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-color')).toHaveValue('#1f6feb')
    })

    await user.clear(screen.getByTestId('tenant-branding-color'))
    await user.type(screen.getByTestId('tenant-branding-color'), 'not-a-color')
    // ``fireEvent.submit`` skips the HTML5 pattern validation so we can
    // exercise the hook's error path (a real user with a misspelled value
    // would see the browser's "please match the requested format" tooltip
    // instead, but our hook-side error is what we want to cover).
    fireEvent.submit(screen.getByTestId('tenant-branding-submit').closest('form')!)

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('tenant-branding-error')).toHaveTextContent(
      'Brand color must be a #RRGGBB hex value',
    )
  })

  it('rejects malformed hex colors before hitting the network', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(okJson(baseTenant))
    globalThis.fetch = fetchMock as typeof fetch

    render(<TenantBrandingPage />)

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-color')).toHaveValue('#1f6feb')
    })

    await user.clear(screen.getByTestId('tenant-branding-color'))
    await user.type(screen.getByTestId('tenant-branding-color'), 'zzz')
    fireEvent.submit(screen.getByTestId('tenant-branding-submit').closest('form')!)

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('tenant-branding-error')).toHaveTextContent(
      'Brand color must be a #RRGGBB hex value',
    )
    // The initial GET is the only network call we expect; the malformed
    // color must short-circuit before any PATCH is sent.
    await waitFor(() => {
      const patchCalls = fetchMock.mock.calls.filter(
        ([, init]) => (init as RequestInit | undefined)?.method === 'PATCH',
      )
      expect(patchCalls).toHaveLength(0)
    })
  })

  it('uploads a logo via multipart and updates the preview', async () => {
    const user = userEvent.setup()
    const updated = {
      ...baseTenant,
      logo_url: 'https://cdn.example.test/tenants/10/logo.png',
      updated_at: '2026-02-02T10:00:00Z',
    }
    const fetchMock = vi.fn().mockImplementation(async (_input, init) => {
      if (init?.method === 'POST' && init.body instanceof FormData) {
        expect(init.body.get('file')).toBeInstanceOf(File)
        return okJson(updated)
      }
      return okJson(baseTenant)
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(<TenantBrandingPage />)

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-color')).toHaveValue('#1f6feb')
    })

    const file = new File(['logo-bytes'], 'logo.png', { type: 'image/png' })
    await user.upload(screen.getByTestId('tenant-branding-logo-file'), file)
    // Wait for the file-selected state to enable the upload button before
    // clicking (avoids userEvent racing the React state update).
    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-logo-submit')).not.toBeDisabled()
    })
    await user.click(screen.getByTestId('tenant-branding-logo-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-logo-image')).toBeInTheDocument()
    })

    expect(screen.getByTestId('tenant-branding-logo-image')).toHaveAttribute(
      'src',
      'https://cdn.example.test/tenants/10/logo.png',
    )
    expect(screen.getByTestId('tenant-branding-logo-success')).toHaveTextContent(
      'Logo uploaded',
    )
  })

  it('surfaces backend errors from the logo upload', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockImplementation(async (_input, init) => {
      if (init?.method === 'POST' && init.body instanceof FormData) {
        return errorJson(415, 'Unsupported logo extension')
      }
      return okJson(baseTenant)
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(<TenantBrandingPage />)

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-color')).toHaveValue('#1f6feb')
    })

    const file = new File(['logo-bytes'], 'logo.png', { type: 'image/png' })
    await user.upload(screen.getByTestId('tenant-branding-logo-file'), file)
    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-logo-submit')).not.toBeDisabled()
    })
    await user.click(screen.getByTestId('tenant-branding-logo-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-logo-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('tenant-branding-logo-error')).toHaveTextContent(
      'Unsupported logo extension',
    )
  })

  it('rejects oversized logo files before hitting the network', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(okJson(baseTenant))
    globalThis.fetch = fetchMock as typeof fetch

    render(<TenantBrandingPage />)

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-color')).toHaveValue('#1f6feb')
    })

    // 3 MB file; backend cap is 2 MB.
    const bigBytes = new Uint8Array(3 * 1024 * 1024)
    const file = new File([bigBytes], 'logo.png', { type: 'image/png' })
    await user.upload(screen.getByTestId('tenant-branding-logo-file'), file)
    fireEvent.submit(
      screen.getByTestId('tenant-branding-logo-submit').closest('form')!,
    )

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-logo-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('tenant-branding-logo-error')).toHaveTextContent(
      'Logo must be 2 MB or smaller',
    )
  })

  it('rejects unsupported logo mime types before hitting the network', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okJson(baseTenant))
    globalThis.fetch = fetchMock as typeof fetch

    render(<TenantBrandingPage />)

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-color')).toHaveValue('#1f6feb')
    })

    // ``userEvent.upload`` respects the ``accept`` attribute on file
    // inputs and would refuse to dispatch a change event for an
    // unsupported MIME type. ``fireEvent.change`` lets the test simulate
    // the user picking an SVG file directly, which is the case the
    // client-side guard must catch.
    const file = new File(['<svg/>'], 'logo.svg', { type: 'image/svg+xml' })
    const input = screen.getByTestId('tenant-branding-logo-file') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-logo-submit')).not.toBeDisabled()
    })
    await userEvent
      .setup()
      .click(screen.getByTestId('tenant-branding-logo-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-logo-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('tenant-branding-logo-error')).toHaveTextContent(
      'Logo must be a PNG, JPG, or WebP image',
    )
  })

  it('shows the no-tenant message when the auth user has no tenant_id', async () => {
    authState.tenant_id = null
    render(<TenantBrandingPage />)

    expect(screen.getByTestId('tenant-branding-no-tenant')).toBeInTheDocument()
    expect(screen.queryByTestId('tenant-branding-submit')).not.toBeInTheDocument()
    expect(screen.queryByTestId('tenant-branding-logo-submit')).not.toBeInTheDocument()
  })

  it('surfaces initial-load errors so users do not overwrite data they cannot see', async () => {
    mockFetchOnce(async () => errorJson(403, 'Forbidden'))
    render(<TenantBrandingPage />)

    // While the GET is in flight we render the skeleton, NOT the real form
    // (so the user cannot submit values the server has never returned).
    expect(screen.getByTestId('tenant-branding-form-skeleton')).toBeInTheDocument()
    expect(screen.queryByTestId('tenant-branding-submit')).not.toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-load-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('tenant-branding-load-error')).toHaveTextContent('Forbidden')
    // Once the error resolves the real form is still NOT mounted (no
    // tenant to hydrate from) — submit must remain absent, not just
    // disabled.
    expect(screen.queryByTestId('tenant-branding-submit')).not.toBeInTheDocument()
    expect(screen.queryByTestId('tenant-branding-color')).not.toBeInTheDocument()
  })

  it('shows an unrecognised-currency warning and disables submit when the server returns a code the dropdown does not know', async () => {
    // JPY is a valid ISO 4217 code but NOT in the curated FE dropdown —
    // the BE may persist any ISO 4217 string, so we surface a warning
    // and refuse to submit until the user picks a supported code.
    mockFetchOnce(async () =>
      okJson({ ...baseTenant, currency: 'JPY' }),
    )
    render(<TenantBrandingPage />)

    await waitFor(() => {
      expect(screen.getByTestId('tenant-branding-currency-warning')).toBeInTheDocument()
    })
    expect(screen.getByTestId('tenant-branding-currency-warning')).toHaveTextContent(
      /Server returned an unrecognised currency: JPY/,
    )
    // Submit must stay disabled — a PATCH would clobber a value the FE
    // does not understand.
    expect(screen.getByTestId('tenant-branding-submit')).toBeDisabled()
  })
})
