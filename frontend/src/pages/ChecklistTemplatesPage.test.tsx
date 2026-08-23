import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ChecklistTemplatesPage from './ChecklistTemplatesPage'

const mockTemplates = [
  {
    id: 1,
    tenant_id: 10,
    stage: 'registered',
    program_id: null,
    name: 'Passport',
    description: 'A clear scan of your passport biodata page.',
    required: true,
    order_index: 0,
  },
  {
    id: 2,
    tenant_id: 10,
    stage: 'registered',
    program_id: null,
    name: 'Transcript',
    description: null,
    required: false,
    order_index: 1,
  },
]

const mockOtherStageTemplate = {
  id: 3,
  tenant_id: 10,
  stage: 'document_verification',
  program_id: null,
  name: 'Offer letter',
  description: null,
  required: true,
  order_index: 0,
}

const mockPrograms = [
  { id: 100, tenant_id: 10, university_id: 10, name: 'Computer Science MSc' },
  { id: 101, tenant_id: 10, university_id: 11, name: 'Data Science MSc' },
]

const mockUniversities = [
  { id: 10, tenant_id: 10, country_id: 1, name: 'University of Toronto' },
  { id: 11, tenant_id: 10, country_id: 2, name: 'University of Manchester' },
]

const mockCountries = [
  { id: 1, tenant_id: 10, name: 'Canada', code: 'CA' },
  { id: 2, tenant_id: 10, name: 'United Kingdom', code: 'GB' },
]

type MockResponse = {
  ok: boolean
  status: number
  json: () => Promise<unknown>
}

function jsonResponse(body: unknown, status = 200): MockResponse {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }
}

interface FetchRouteOptions {
  templates?: unknown[]
  programs?: unknown[]
  universities?: unknown[]
  countries?: unknown[]
  handlers?: Array<{ method: string; path: RegExp; handler: () => MockResponse }>
}

function defaultHandlersFor(options: FetchRouteOptions): Array<{
  method: string
  path: RegExp
  handler: () => MockResponse
}> {
  const templates = options.templates ?? mockTemplates
  const programs = options.programs ?? mockPrograms
  const universities = options.universities ?? mockUniversities
  return [
    {
      method: 'GET',
      path: /\/checklist-templates(\?.*)?$/,
      handler: () => jsonResponse(templates),
    },
    {
      method: 'GET',
      path: /\/master-data\/admin\/programs$/,
      handler: () => jsonResponse(programs),
    },
    {
      method: 'GET',
      path: /\/master-data\/admin\/universities$/,
      handler: () => jsonResponse(universities),
    },
    {
      // useMasterDataAdmin always fetches countries too; mock it so the call
      // doesn't fall through to the 500 default and mask a real regression.
      method: 'GET',
      path: /\/master-data\/admin\/countries$/,
      handler: () => jsonResponse(options.countries ?? mockCountries),
    },
  ]
}

function setupFetchMock(options: FetchRouteOptions): ReturnType<typeof vi.fn> {
  const fetchSpy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = init?.method ?? 'GET'

    for (const entry of options.handlers ?? []) {
      if (entry.method === method && entry.path.test(url)) {
        return entry.handler()
      }
    }

    return jsonResponse({ detail: 'Unhandled fetch in test' }, 500)
  })

  globalThis.fetch = fetchSpy as unknown as typeof fetch
  return fetchSpy
}

function renderPage(options: FetchRouteOptions = {}): ReturnType<typeof vi.fn> {
  const fetchSpy = setupFetchMock({
    ...options,
    handlers: [...(options.handlers ?? []), ...defaultHandlersFor(options)],
  })
  render(<ChecklistTemplatesPage />)
  return fetchSpy
}

describe('ChecklistTemplatesPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
  })

  it('short-circuits to a "please log in" hint when mounted without a token', async () => {
    const fetchSpy = vi.fn()
    globalThis.fetch = fetchSpy as unknown as typeof fetch
    localStorage.removeItem('access_token')

    render(<ChecklistTemplatesPage />)

    await waitFor(() => {
      expect(
        screen.getByTestId('checklist-templates-unauthenticated'),
      ).toBeInTheDocument()
    })
    expect(
      screen.getByTestId('checklist-templates-unauthenticated'),
    ).toHaveTextContent(/log in/i)
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('renders the templates table for the default stage filter', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('checklist-templates-page')).toBeInTheDocument()
    })

    expect(screen.getByTestId('checklist-templates-stage-tab-registered')).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByTestId('checklist-template-table')).toBeInTheDocument()
    expect(screen.getByTestId('checklist-template-row-1')).toBeInTheDocument()
    expect(screen.getByText('Passport')).toBeInTheDocument()
    expect(screen.getByText('Transcript')).toBeInTheDocument()
    expect(screen.getByTestId('checklist-template-required-1')).toHaveTextContent('Required')
    expect(screen.getByTestId('checklist-template-required-2')).toHaveTextContent('Optional')
  })

  it('does not show templates from other stages in the default tab', async () => {
    renderPage({ templates: [...mockTemplates, mockOtherStageTemplate] })

    await waitFor(() => {
      expect(screen.getByTestId('checklist-template-row-1')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('checklist-template-row-3')).not.toBeInTheDocument()
  })

  it('switches stage tabs and updates the visible templates', async () => {
    const user = userEvent.setup()
    renderPage({ templates: [...mockTemplates, mockOtherStageTemplate] })

    await waitFor(() => {
      expect(screen.getByTestId('checklist-templates-stage-tab-document_verification')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('checklist-templates-stage-tab-document_verification'))

    await waitFor(() => {
      expect(screen.getByTestId('checklist-templates-stage-tab-document_verification')).toHaveAttribute(
        'aria-selected',
        'true',
      )
    })

    expect(screen.getByTestId('checklist-template-row-3')).toBeInTheDocument()
    expect(screen.queryByTestId('checklist-template-row-1')).not.toBeInTheDocument()
  })

  it('shows an empty state when no templates exist for the selected stage', async () => {
    // Templates list contains a single row that belongs to
    // ``document_verification``; with the default 'registered' tab
    // active, the page must show the empty state for that stage.
    renderPage({ templates: [mockOtherStageTemplate] })

    await waitFor(() => {
      expect(screen.getByTestId('checklist-templates-page')).toBeInTheDocument()
    })

    expect(
      screen.getByTestId('checklist-templates-stage-tab-registered'),
    ).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('checklist-templates-empty')).toBeInTheDocument()
    expect(
      screen.queryByTestId('checklist-template-row-3'),
    ).not.toBeInTheDocument()
  })

  it('shows the empty state when the stage tab has no matching templates', async () => {
    // Switch tabs and assert the empty state on the tab that has no
    // rows (registered), confirming the empty state renders for any
    // stage with no rows — not just the default tab.
    const user = userEvent.setup()
    renderPage({ templates: mockTemplates })

    await waitFor(() => {
      expect(screen.getByTestId('checklist-template-row-1')).toBeInTheDocument()
    })

    // Switch to document_verification, which has no rows.
    await user.click(
      screen.getByTestId('checklist-templates-stage-tab-document_verification'),
    )

    await waitFor(() => {
      expect(
        screen.getByTestId('checklist-templates-stage-tab-document_verification'),
      ).toHaveAttribute('aria-selected', 'true')
      expect(screen.getByTestId('checklist-templates-empty')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('checklist-template-row-1')).not.toBeInTheDocument()
    expect(screen.queryByTestId('checklist-template-row-2')).not.toBeInTheDocument()
  })

  it('shows an error message when the templates API returns 403', async () => {
    renderPage({
      handlers: [
        {
          method: 'GET',
          path: /\/checklist-templates(\?.*)?$/,
          handler: () =>
            jsonResponse({ detail: 'Insufficient permissions' }, 403),
        },
        {
          method: 'GET',
          path: /\/master-data\/admin\/programs$/,
          handler: () => jsonResponse(mockPrograms),
        },
        {
          method: 'GET',
          path: /\/master-data\/admin\/universities$/,
          handler: () => jsonResponse(mockUniversities),
        },
      ],
    })

    await waitFor(() => {
      expect(screen.getByTestId('checklist-templates-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('checklist-templates-error')).toHaveTextContent(
      'permission',
    )
  })

  it('creates a template and shows a success message', async () => {
    const user = userEvent.setup()
    const createdTemplate = {
      id: 4,
      tenant_id: 10,
      stage: 'registered',
      program_id: null,
      name: 'Birth certificate',
      description: null,
      required: true,
      order_index: 2,
    }
    const fetchSpy = setupFetchMock({
      handlers: [
        ...defaultHandlersFor({}),
        {
          method: 'POST',
          path: /\/checklist-templates$/,
          handler: () => jsonResponse(createdTemplate, 201),
        },
      ],
    })
    render(<ChecklistTemplatesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('checklist-template-create-form')).toBeInTheDocument()
    })

    await user.selectOptions(
      screen.getByTestId('checklist-template-create-stage'),
      'registered',
    )
    await user.type(screen.getByTestId('checklist-template-create-name'), 'Birth certificate')
    await user.click(screen.getByTestId('checklist-template-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('checklist-templates-success')).toBeInTheDocument()
    })
    expect(screen.getByTestId('checklist-templates-success')).toHaveTextContent(
      'Birth certificate',
    )

    const postCalls = fetchSpy.mock.calls.filter((call) => {
      const [url, init] = call
      if (typeof url !== 'string') {
        return false
      }
      // Match the bare ``/checklist-templates`` POST endpoint, not the
      // ``/checklist-templates/{id}`` PATCH/DELETE endpoint.
      const pathOnly = url.split('?')[0] ?? url
      if (pathOnly !== '/checklist-templates') {
        return false
      }
      const method = (init as RequestInit | undefined)?.method ?? 'GET'
      return method === 'POST'
    })
    expect(postCalls).toHaveLength(1)
    const body = JSON.parse(String((postCalls[0]![1] as RequestInit).body))
    expect(body).toEqual({
      stage: 'registered',
      program_id: null,
      name: 'Birth certificate',
      description: null,
      required: true,
      order_index: null,
    })
  })

  it('surfaces the API error when creating a template fails', async () => {
    const user = userEvent.setup()
    setupFetchMock({
      handlers: [
        ...defaultHandlersFor({}),
        {
          method: 'POST',
          path: /\/checklist-templates$/,
          handler: () => jsonResponse({ detail: 'name is required' }, 422),
        },
      ],
    })
    render(<ChecklistTemplatesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('checklist-template-create-form')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('checklist-template-create-name'), 'X')
    await user.click(screen.getByTestId('checklist-template-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('checklist-templates-create-error')).toHaveTextContent(
        'name is required',
      )
    })
  })

  it('opens the edit form, updates a template, and shows success', async () => {
    const user = userEvent.setup()
    const updatedTemplate = { ...mockTemplates[0], name: 'Passport (renamed)' }
    const fetchSpy = setupFetchMock({
      handlers: [
        ...defaultHandlersFor({}),
        {
          method: 'PATCH',
          path: /\/checklist-templates\/\d+$/,
          handler: () => jsonResponse(updatedTemplate),
        },
      ],
    })
    render(<ChecklistTemplatesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('checklist-template-edit-1')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('checklist-template-edit-1'))

    await waitFor(() => {
      expect(screen.getByTestId('checklist-template-edit-name')).toHaveValue('Passport')
    })

    await user.clear(screen.getByTestId('checklist-template-edit-name'))
    await user.type(screen.getByTestId('checklist-template-edit-name'), 'Passport (renamed)')
    await user.click(screen.getByTestId('checklist-template-edit-submit'))

    await waitFor(() => {
      expect(screen.queryByTestId('checklist-template-edit-name')).not.toBeInTheDocument()
    })
    expect(screen.getByTestId('checklist-templates-success')).toHaveTextContent(
      'Passport (renamed)',
    )

    const patchCalls = fetchSpy.mock.calls.filter((call) => {
      const [url, init] = call
      if (typeof url !== 'string') {
        return false
      }
      const pathOnly = url.split('?')[0] ?? url
      if (!/^\/checklist-templates\/\d+$/.test(pathOnly)) {
        return false
      }
      const method = (init as RequestInit | undefined)?.method ?? 'GET'
      return method === 'PATCH'
    })
    expect(patchCalls).toHaveLength(1)
  })

  it('cancels an in-progress template edit', async () => {
    const user = userEvent.setup()
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('checklist-template-edit-1')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('checklist-template-edit-1'))
    expect(screen.getByTestId('checklist-template-edit-name')).toBeInTheDocument()
    await user.click(screen.getByTestId('checklist-template-edit-cancel'))
    expect(screen.queryByTestId('checklist-template-edit-name')).not.toBeInTheDocument()
  })

  it('deletes a template and shows a success message', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const fetchSpy = setupFetchMock({
      handlers: [
        ...defaultHandlersFor({}),
        {
          method: 'DELETE',
          path: /\/checklist-templates\/\d+$/,
          handler: () => jsonResponse(undefined, 204),
        },
      ],
    })
    render(<ChecklistTemplatesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('checklist-template-delete-1')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('checklist-template-delete-1'))

    await waitFor(() => {
      expect(screen.getByTestId('checklist-templates-success')).toHaveTextContent('deleted')
    })

    const deleteCalls = fetchSpy.mock.calls.filter((call) => {
      const [url, init] = call
      if (typeof url !== 'string') {
        return false
      }
      const pathOnly = url.split('?')[0] ?? url
      if (!/^\/checklist-templates\/\d+$/.test(pathOnly)) {
        return false
      }
      const method = (init as RequestInit | undefined)?.method ?? 'GET'
      return method === 'DELETE'
    })
    expect(deleteCalls).toHaveLength(1)
  })

  it('shows the API error when deleting a template fails', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    setupFetchMock({
      handlers: [
        ...defaultHandlersFor({}),
        {
          method: 'DELETE',
          path: /\/checklist-templates\/\d+$/,
          handler: () =>
            jsonResponse({ detail: 'Template is in use' }, 409),
        },
      ],
    })
    render(<ChecklistTemplatesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('checklist-template-delete-1')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('checklist-template-delete-1'))

    await waitFor(() => {
      expect(screen.getByTestId('checklist-templates-delete-error')).toHaveTextContent(
        'Template is in use',
      )
    })
  })

  it('does not delete when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const fetchSpy = setupFetchMock({
      handlers: [
        ...defaultHandlersFor({}),
        {
          method: 'DELETE',
          path: /\/checklist-templates\/\d+$/,
          handler: () => jsonResponse(undefined, 204),
        },
      ],
    })
    render(<ChecklistTemplatesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('checklist-template-delete-1')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('checklist-template-delete-1'))

    // The user cancelled, so no DELETE request is issued and no success shows.
    const deleteCalls = fetchSpy.mock.calls.filter((call) => {
      const init = call[1] as RequestInit | undefined
      return (init?.method ?? 'GET') === 'DELETE'
    })
    expect(deleteCalls).toHaveLength(0)
    expect(
      screen.queryByTestId('checklist-templates-success'),
    ).not.toBeInTheDocument()
  })
})
