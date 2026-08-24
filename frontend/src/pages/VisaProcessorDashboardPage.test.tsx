import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import VisaProcessorDashboardPage from './VisaProcessorDashboardPage'

const mockVisaProcessor = {
  id: 91,
  email: 'visa@demo.test',
  role: 'visa_processor' as const,
  tenant_id: 10,
  branch_id: null,
}

const mockApplication = {
  id: 101,
  tenant_id: 10,
  branch_id: 1,
  student_id: 42,
  assigned_counselor_id: 7,
  university_id: 5,
  program_id: 11,
  stage: 'visa_processing',
  created_at: '2026-02-01T10:00:00Z',
  updated_at: '2026-02-02T10:00:00Z',
}

interface Handlers {
  queueStatus?: number
  items?: unknown[]
  total?: number
  /**
   * ``fetchVisaDetail`` response when the toggle opens the editor:
   * ``null`` (default) means "no detail recorded yet — empty form",
   * any other value is returned as the detail body. Pass an
   * ``{ status }`` to simulate a non-404 load error.
   */
  detail?: unknown | null | { status: number; detail?: string }
  /** Per-application outcome persistence (E35; #196). */
  onOutcome?: (applicationId: number, body: unknown) => unknown | null
}

function createFetchMock(handlers: Handlers = {}) {
  return vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = String(url)
    if (path.includes('/auth/me')) {
      return { ok: true, status: 200, json: async () => mockVisaProcessor }
    }
    if (path.includes('/visa/applications/queue')) {
      if (handlers.queueStatus && handlers.queueStatus >= 400) {
        return { ok: false, status: handlers.queueStatus, json: async () => ({ detail: 'nope' }) }
      }
      const items = handlers.items ?? [mockApplication]
      return {
        ok: true,
        status: 200,
        json: async () => ({
          items,
          total: handlers.total ?? items.length,
          limit: 50,
          offset: 0,
        }),
      }
    }
    // The form's GET /visa/applications/{id}/details: default to
    // 404 -> null (i.e. "no detail recorded yet"), matching the
    // happy path the toggle tests assume (the form mounts in its
    // empty state). Callers can pass a real detail body to exercise
    // the edit path, or an error object to exercise the load-error
    // banner.
    if (/^\/?visa\/applications\/\d+\/details$/.test(path)) {
      const d = handlers.detail
      if (d && typeof d === 'object' && 'status' in d) {
        const status = (d as { status: number }).status
        const detail = (d as { detail?: string }).detail ?? 'detail error'
        return { ok: false, status, json: async () => ({ detail }) }
      }
      if (d === null || d === undefined) {
        return { ok: false, status: 404, json: async () => ({ detail: 'Not Found' }) }
      }
      return { ok: true, status: 200, json: async () => d }
    }
    const outcomeMatch = path.match(/\/visa\/applications\/(\d+)\/outcome$/)
    if (outcomeMatch && init?.method === 'PATCH') {
      const [, idStr] = outcomeMatch
      const applicationId = Number(idStr)
      const body = init.body ? JSON.parse(String(init.body)) : {}
      if (handlers.onOutcome) {
        const outcome = handlers.onOutcome(applicationId, body)
        if (outcome) {
          return { ok: true, status: 200, json: async () => outcome }
        }
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({
          id: 11,
          tenant_id: 10,
          application_id: applicationId,
          status: body.status ?? 'approved',
          outcome_date: body.outcome_date ?? null,
          notes: body.notes ?? null,
          created_at: '2026-02-03T10:00:00Z',
          updated_at: '2026-02-03T10:00:00Z',
        }),
      }
    }
    throw new Error(`Unhandled fetch: ${path}`)
  }) as unknown as typeof fetch
}

function renderPage() {
  return render(
    <AuthProvider>
      <VisaProcessorDashboardPage />
    </AuthProvider>,
  )
}

describe('VisaProcessorDashboardPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
  })

  afterEach(() => {
    // Drain any pending "saved" indicator timers from the previous
    // test so they don't leak into the next one (the dashboard
    // schedules a window.setTimeout when onSaved fires).
    vi.useRealTimers()
  })

  it('renders the visa-stage applications queue with a row per application', async () => {
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    expect(await screen.findByTestId('visa-queue-table')).toBeInTheDocument()
    expect(screen.getByTestId('visa-queue-row-101')).toBeInTheDocument()
    expect(screen.getByTestId('visa-queue-count')).toHaveTextContent(
      '1 application at the visa stage',
    )
  })

  it('shows the singular form when total is 1', async () => {
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    expect(await screen.findByTestId('visa-queue-count')).toHaveTextContent('application')
  })

  it('shows the plural form when total is greater than 1', async () => {
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 3 })
    renderPage()

    expect(await screen.findByTestId('visa-queue-count')).toHaveTextContent(
      '3 applications at the visa stage',
    )
  })

  it('shows an empty state when there are no applications at the visa stage', async () => {
    globalThis.fetch = createFetchMock({ items: [], total: 0 })
    renderPage()

    expect(await screen.findByTestId('visa-queue-empty')).toBeInTheDocument()
    expect(screen.queryByTestId('visa-queue-table')).not.toBeInTheDocument()
  })

  it('shows a permission error when the API returns 403', async () => {
    globalThis.fetch = createFetchMock({ queueStatus: 403 })
    renderPage()

    const alert = await screen.findByTestId('visa-queue-error')
    expect(alert).toHaveAttribute('role', 'alert')
    expect(alert).toHaveTextContent(/permission/i)
  })

  it('shows the backend detail when the API fails with 500', async () => {
    // The visa queue router (#191) translates a database outage into
    // a 503 with a specific detail string. For non-auth failures the
    // hook surfaces whatever the backend's ``detail`` was so the
    // operator can distinguish a transient backend issue from a
    // generic client-side failure.
    globalThis.fetch = createFetchMock({ queueStatus: 500 })
    renderPage()

    const alert = await screen.findByTestId('visa-queue-error')
    expect(alert).toHaveTextContent(/nope/)
  })

  it('triggers a refetch when the Refresh button is clicked', async () => {
    const user = userEvent.setup()
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    await screen.findByTestId('visa-queue-table')

    const refresh = screen.getByRole('button', { name: /refresh/i })
    await user.click(refresh)

    await waitFor(() => {
      const queueCalls = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.filter(
        ([url]) => String(url).includes('/visa/applications/queue'),
      )
      expect(queueCalls.length).toBeGreaterThanOrEqual(2)
    })
  })

  it('renders the unauthenticated state without calling the API', async () => {
    localStorage.removeItem('access_token')
    const fetchMock = createFetchMock()
    globalThis.fetch = fetchMock
    renderPage()

    // The dashboard should not crash; without an access token the
    // hook short-circuits and the dashboard renders its empty
    // loading-resolved state (loading false, no error, no rows).
    await waitFor(() => {
      expect(screen.getByTestId('visa-queue-empty')).toBeInTheDocument()
    })
    expect(
      (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls.filter(([url]) =>
        String(url).includes('/visa/applications/queue'),
      ),
    ).toHaveLength(0)
  })

  it('renders a Record outcome action on every visa-queue row by default', async () => {
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    await screen.findByTestId('visa-queue-row-101')

    // The dashboard embeds the E35 VisaOutcomeAction control on
    // every row (frontend ticket #196). Before any outcome is
    // recorded in this session it MUST show the create-mode label.
    expect(screen.getByTestId('visa-queue-row-101')).toHaveTextContent(
      /record outcome/i,
    )
  })

  it('drives the PATCH and switches the row button to Update outcome on success', async () => {
    const user = userEvent.setup()
    const seenBodies: unknown[] = []
    globalThis.fetch = createFetchMock({
      items: [mockApplication],
      total: 1,
      onOutcome: (applicationId, body) => {
        seenBodies.push(body)
        return {
          id: 11,
          tenant_id: 10,
          application_id: applicationId,
          status: 'approved',
          outcome_date: null,
          notes: 'OK',
          created_at: '2026-02-03T10:00:00Z',
          updated_at: '2026-02-03T10:00:00Z',
        }
      },
    })
    renderPage()
    const row = await screen.findByTestId('visa-queue-row-101')
    expect(row).toHaveTextContent(/record outcome/i)

    await user.click(screen.getByTestId('visa-outcome-open-101'))
    await user.type(screen.getByTestId('visa-outcome-status-101'), 'Approved')
    await user.type(screen.getByTestId('visa-outcome-notes-101'), 'OK')
    await user.click(screen.getByTestId('visa-outcome-submit-101'))

    // Success state appears in place of the form. The row mirrors
    // ``VisaOutcomeAction``'s mode (create vs update) -- on first
    // record the message is "Outcome recorded."
    expect(await screen.findByTestId('visa-outcome-success-101')).toBeInTheDocument()

    // Exactly one PATCH went out, with the user-entered payload.
    const outcomeCalls = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.filter(
      ([url]) => String(url).includes('/visa/applications/101/outcome'),
    )
    expect(outcomeCalls).toHaveLength(1)
    const [, init] = outcomeCalls[0] as [string, RequestInit]
    expect(init.method).toBe('PATCH')
    const body = JSON.parse(String(init.body))
    expect(body.status).toBe('Approved')
    expect(body.notes).toBe('OK')
    expect(seenBodies).toHaveLength(1)
  })

  it('keeps the outcome form open and surfaces a 422 detail inside the row', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const path = String(url)
      if (path.includes('/auth/me')) {
        return { ok: true, status: 200, json: async () => mockVisaProcessor }
      }
      if (path.includes('/visa/applications/queue')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ items: [mockApplication], total: 1, limit: 50, offset: 0 }),
        }
      }
      const outcomeMatch = path.match(/\/visa\/applications\/(\d+)\/outcome$/)
      if (outcomeMatch && init?.method === 'PATCH') {
        return {
          ok: false,
          status: 422,
          json: async () => ({
            detail:
              "Application in stage 'enrolled' cannot have its visa outcome updated. The application must be in the 'visa_processing' stage.",
          }),
        }
      }
      throw new Error(`Unhandled fetch: ${path}`)
    }) as unknown as typeof fetch

    renderPage()
    await screen.findByTestId('visa-queue-row-101')

    await user.click(screen.getByTestId('visa-outcome-open-101'))
    await user.type(screen.getByTestId('visa-outcome-status-101'), 'Approved')
    await user.click(screen.getByTestId('visa-outcome-submit-101'))

    expect(await screen.findByTestId('visa-outcome-error-101')).toHaveTextContent(
      /visa_processing/i,
    )
    expect(screen.getByTestId('visa-outcome-form-101')).toBeInTheDocument()
  })

  // ----------------------------------------------------------------
  // E34 visa detail toggle + form integration (frontend #194).
  // ----------------------------------------------------------------

  it('renders an "Update visa detail" toggle on every row, initially collapsed', async () => {
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    const toggle = await screen.findByTestId('visa-queue-edit-toggle-101')
    expect(toggle).toHaveTextContent(/update visa detail/i)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByTestId('visa-detail-panel-101')).not.toBeInTheDocument()
  })

  it('opens the visa detail update form when the per-row toggle is clicked', async () => {
    const user = userEvent.setup()
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    const toggle = await screen.findByTestId('visa-queue-edit-toggle-101')
    await user.click(toggle)

    const panel = await screen.findByTestId('visa-detail-panel-101')
    expect(panel).toBeInTheDocument()
    // The form mounts and goes through its loading -> empty state
    // (no detail recorded yet -> 404 from fetchVisaDetail). The
    // dashboard wires the form's `onSaved` to close the panel.
    expect(await screen.findByTestId('visa-detail-form-101')).toBeInTheDocument()
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(toggle).toHaveTextContent(/close/i)
  })

  it('closes the visa detail update form when the toggle is clicked a second time', async () => {
    const user = userEvent.setup()
    globalThis.fetch = createFetchMock({ items: [mockApplication], total: 1 })
    renderPage()

    const toggle = await screen.findByTestId('visa-queue-edit-toggle-101')
    await user.click(toggle)
    await screen.findByTestId('visa-detail-form-101')

    await user.click(toggle)

    await waitFor(() => {
      expect(screen.queryByTestId('visa-detail-panel-101')).not.toBeInTheDocument()
    })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
  })

  it('shows a "Saved" indicator next to the row after a successful visa detail save', async () => {
    const user = userEvent.setup()
    // Pretend the detail already exists (visa processor is editing)
    // so the form PUTs an update rather than creating fresh.
    globalThis.fetch = createFetchMock({
      items: [mockApplication],
      total: 1,
      detail: {
        id: 1,
        tenant_id: 10,
        application_id: 101,
        visa_type: 'F-1 Student',
        interview_date: null,
        created_at: '2026-02-01T10:00:00Z',
        updated_at: '2026-02-02T10:00:00Z',
      },
    })
    renderPage()

    const toggle = await screen.findByTestId('visa-queue-edit-toggle-101')
    await user.click(toggle)

    const form = await screen.findByTestId('visa-detail-form-101')
    // The form prefilled from the seeded detail -- its current value
    // is already a valid visa type so the submit just succeeds.
    expect(form).toBeInTheDocument()

    await user.click(screen.getByTestId('visa-detail-submit-101'))

    // The form's onSaved closes the panel; the dashboard should
    // surface a "Saved" indicator next to the toggle so the visa
    // processor has positive feedback that the write succeeded.
    await waitFor(() => {
      expect(screen.getByTestId('visa-detail-saved-101')).toBeInTheDocument()
    })
    expect(screen.getByTestId('visa-detail-saved-101')).toHaveTextContent(/saved/i)
    // And the panel should be closed.
    expect(screen.queryByTestId('visa-detail-panel-101')).not.toBeInTheDocument()
  })

  it('does not render the visa detail form when the queue is empty', async () => {
    globalThis.fetch = createFetchMock({ items: [], total: 0 })
    renderPage()

    expect(await screen.findByTestId('visa-queue-empty')).toBeInTheDocument()
    expect(screen.queryByTestId('visa-detail-panel-101')).not.toBeInTheDocument()
  })
})
