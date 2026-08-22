import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MasterDataAdminPage from './MasterDataAdminPage'

const mockCountries = [
  { id: 1, tenant_id: 10, name: 'Canada', code: 'CA' },
  { id: 2, tenant_id: 10, name: 'United Kingdom', code: 'GB' },
]

const mockUniversities = [
  { id: 10, tenant_id: 10, country_id: 1, name: 'University of Toronto' },
  { id: 11, tenant_id: 10, country_id: 2, name: 'University of Manchester' },
]

const mockPrograms = [
  { id: 100, tenant_id: 10, university_id: 10, name: 'Computer Science MSc' },
  { id: 101, tenant_id: 10, university_id: 11, name: 'Data Science MSc' },
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

type MockHandler = (url: string, init?: RequestInit) => MockResponse

interface FetchRouteOptions {
  user: { id: number; role: string }
  countries?: unknown[]
  universities?: unknown[]
  programs?: unknown[]
  /**
   * Per-method path handlers. Each value is invoked with the request
   * URL + init and returns the mock response. Paths are matched by
   * ``startsWith`` against the request URL after stripping the API
   * base prefix (empty here) and the resource path tail that the
   * client appends for ID-scoped endpoints.
   */
  handlers?: Array<{ method: string; path: RegExp; handler: MockHandler }>
  /**
   * Default handler for any unmatched request, so the test can
   * record / assert calls without spamming real implementations.
   */
  fallback?: MockHandler
}

function setupFetchMock(options: FetchRouteOptions): ReturnType<typeof vi.fn> {
  const fetchSpy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = init?.method ?? 'GET'

    for (const entry of options.handlers ?? []) {
      if (entry.method === method && entry.path.test(url)) {
        return entry.handler(url, init)
      }
    }

    if (options.fallback) {
      return options.fallback(url, init)
    }

    return jsonResponse({ detail: 'Unhandled fetch in test' }, 500)
  })

  globalThis.fetch = fetchSpy as unknown as typeof fetch
  return fetchSpy
}

function defaultHandlersFor(
  options: FetchRouteOptions,
): Array<{ method: string; path: RegExp; handler: MockHandler }> {
  const countries = options.countries ?? mockCountries
  const universities = options.universities ?? mockUniversities
  const programs = options.programs ?? mockPrograms
  return [
    {
      method: 'GET',
      path: /\/master-data\/admin\/countries$/,
      handler: () => jsonResponse(countries),
    },
    {
      method: 'GET',
      path: /\/master-data\/admin\/universities$/,
      handler: () => jsonResponse(universities),
    },
    {
      method: 'GET',
      path: /\/master-data\/admin\/programs$/,
      handler: () => jsonResponse(programs),
    },
  ]
}

function renderPage(options: FetchRouteOptions): ReturnType<typeof vi.fn> {
  const fetchSpy = setupFetchMock({
    ...options,
    handlers: [...(options.handlers ?? []), ...defaultHandlersFor(options)],
  })
  render(<MasterDataAdminPage />)
  return fetchSpy
}

describe('MasterDataAdminPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
  })

  it('renders the three tabs and defaults to the countries tab', async () => {
    renderPage({
      user: { id: 50, role: 'consultancy_owner' },
    })

    await waitFor(() => {
      expect(screen.getByTestId('master-data-admin-page')).toBeInTheDocument()
    })

    expect(screen.getByTestId('master-data-tab-countries')).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByTestId('master-data-tab-universities')).toHaveAttribute(
      'aria-selected',
      'false',
    )
    expect(screen.getByTestId('master-data-tab-programs')).toHaveAttribute(
      'aria-selected',
      'false',
    )

    expect(screen.getByTestId('master-data-country-table')).toBeInTheDocument()
    expect(screen.getByText('Canada')).toBeInTheDocument()
    expect(screen.getByText('CA')).toBeInTheDocument()
  })

  it('switches tabs and loads the universities panel', async () => {
    const user = userEvent.setup()
    renderPage({
      user: { id: 50, role: 'consultancy_owner' },
    })

    await waitFor(() => {
      expect(screen.getByTestId('master-data-tab-universities')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-tab-universities'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-tab-universities')).toHaveAttribute(
        'aria-selected',
        'true',
      )
    })

    expect(screen.getByTestId('master-data-university-table')).toBeInTheDocument()
    expect(screen.getByText('University of Toronto')).toBeInTheDocument()
    expect(screen.getByText('Canada')).toBeInTheDocument()
  })

  it('switches tabs and loads the programs panel', async () => {
    const user = userEvent.setup()
    renderPage({
      user: { id: 50, role: 'consultancy_owner' },
    })

    await waitFor(() => {
      expect(screen.getByTestId('master-data-tab-programs')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-tab-programs'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-tab-programs')).toHaveAttribute(
        'aria-selected',
        'true',
      )
    })

    expect(screen.getByTestId('master-data-program-table')).toBeInTheDocument()
    expect(screen.getByText('Computer Science MSc')).toBeInTheDocument()
    expect(screen.getByText('University of Toronto')).toBeInTheDocument()
  })

  it('shows an empty state when there are no countries', async () => {
    renderPage({
      user: { id: 50, role: 'consultancy_owner' },
      countries: [],
    })

    await waitFor(() => {
      expect(screen.getByTestId('master-data-countries-empty')).toBeInTheDocument()
    })
  })

  it('shows error when countries API returns 403', async () => {
    renderPage({
      user: { id: 50, role: 'consultancy_owner' },
      handlers: [
        {
          method: 'GET',
          path: /\/master-data\/admin\/countries$/,
          handler: () => jsonResponse({ detail: 'Insufficient permissions' }, 403),
        },
        {
          method: 'GET',
          path: /\/master-data\/admin\/universities$/,
          handler: () => jsonResponse(mockUniversities),
        },
        {
          method: 'GET',
          path: /\/master-data\/admin\/programs$/,
          handler: () => jsonResponse(mockPrograms),
        },
      ],
    })

    await waitFor(() => {
      expect(screen.getByTestId('master-data-countries-error')).toHaveTextContent(
        'You do not have permission to view master data',
      )
    })
  })

  it('creates a country and shows a success message', async () => {
    const user = userEvent.setup()
    const createdCountry = {
      id: 3,
      tenant_id: 10,
      name: 'Australia',
      code: 'AU',
    }
    const fetchSpy = setupFetchMock({
      user: { id: 50, role: 'consultancy_owner' },
      handlers: [
        ...defaultHandlersFor({ user: { id: 50, role: 'consultancy_owner' } }),
        {
          method: 'POST',
          path: /\/master-data\/admin\/countries$/,
          handler: () => jsonResponse(createdCountry, 201),
        },
        {
          method: 'GET',
          path: /\/master-data\/admin\/countries$/,
          handler: (_url, init) => {
            // The hook refetches on success; return the list with
            // the new country so the table reflects the change.
            if (init?.method === 'GET') {
              return jsonResponse([...mockCountries, createdCountry])
            }
            return jsonResponse(mockCountries)
          },
        },
      ],
    })
    render(<MasterDataAdminPage />)

    await waitFor(() => {
      expect(screen.getByTestId('master-data-country-create-form')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('master-data-country-name'), 'Australia')
    await user.type(screen.getByTestId('master-data-country-code'), 'AU')
    await user.click(screen.getByTestId('master-data-country-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-success')).toBeInTheDocument()
    })
    expect(screen.getByTestId('master-data-success')).toHaveTextContent('Australia')

    const postCalls = fetchSpy.mock.calls.filter((call) => {
      const [url, init] = call
      if (typeof url !== 'string' || !url.endsWith('/master-data/admin/countries')) {
        return false
      }
      const method = (init as RequestInit | undefined)?.method ?? 'GET'
      return method === 'POST'
    })
    expect(postCalls).toHaveLength(1)
    const body = JSON.parse(String(postCalls[0]![1] as RequestInit).body)
    expect(body).toEqual({ name: 'Australia', code: 'AU' })
  })

  it('shows the API error message when creating a country fails', async () => {
    const user = userEvent.setup()
    setupFetchMock({
      user: { id: 50, role: 'consultancy_owner' },
      handlers: [
        ...defaultHandlersFor({ user: { id: 50, role: 'consultancy_owner' } }),
        {
          method: 'POST',
          path: /\/master-data\/admin\/countries$/,
          handler: () => jsonResponse({ detail: 'Country name is required' }, 422),
        },
      ],
    })
    render(<MasterDataAdminPage />)

    await waitFor(() => {
      expect(screen.getByTestId('master-data-country-create-form')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('master-data-country-name'), 'X')
    await user.type(screen.getByTestId('master-data-country-code'), 'XX')
    await user.click(screen.getByTestId('master-data-country-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-create-error')).toHaveTextContent(
        'Country name is required',
      )
    })
  })

  it('opens the country edit form, updates, and shows success', async () => {
    const user = userEvent.setup()
    const updatedCountry = { ...mockCountries[0], name: 'Canada Renamed' }
    setupFetchMock({
      user: { id: 50, role: 'consultancy_owner' },
      handlers: [
        ...defaultHandlersFor({ user: { id: 50, role: 'consultancy_owner' } }),
        {
          method: 'PATCH',
          path: /\/master-data\/admin\/countries\/\d+$/,
          handler: () => jsonResponse(updatedCountry),
        },
      ],
    })
    render(<MasterDataAdminPage />)

    await waitFor(() => {
      expect(screen.getByTestId('master-data-country-edit-1')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-country-edit-1'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-country-edit-name')).toHaveValue('Canada')
    })

    await user.clear(screen.getByTestId('master-data-country-edit-name'))
    await user.type(screen.getByTestId('master-data-country-edit-name'), 'Canada Renamed')
    await user.click(screen.getByTestId('master-data-country-edit-submit'))

    await waitFor(() => {
      expect(screen.queryByTestId('master-data-country-edit-name')).not.toBeInTheDocument()
    })
    expect(screen.getByTestId('master-data-success')).toHaveTextContent('Canada Renamed')
  })

  it('cancels an in-progress country edit', async () => {
    const user = userEvent.setup()
    renderPage({
      user: { id: 50, role: 'consultancy_owner' },
    })

    await waitFor(() => {
      expect(screen.getByTestId('master-data-country-edit-1')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-country-edit-1'))
    expect(screen.getByTestId('master-data-country-edit-name')).toBeInTheDocument()
    await user.click(screen.getByTestId('master-data-country-edit-cancel'))
    expect(screen.queryByTestId('master-data-country-edit-name')).not.toBeInTheDocument()
  })

  it('deletes a country and shows a success message', async () => {
    const user = userEvent.setup()
    const fetchSpy = setupFetchMock({
      user: { id: 50, role: 'consultancy_owner' },
      handlers: [
        ...defaultHandlersFor({ user: { id: 50, role: 'consultancy_owner' } }),
        {
          method: 'DELETE',
          path: /\/master-data\/admin\/countries\/\d+$/,
          handler: () => jsonResponse(undefined, 204),
        },
      ],
    })
    render(<MasterDataAdminPage />)

    await waitFor(() => {
      expect(screen.getByTestId('master-data-country-delete-1')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-country-delete-1'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-success')).toHaveTextContent('deleted')
    })

    const deleteCalls = fetchSpy.mock.calls.filter((call) => {
      const [url, init] = call
      return (
        typeof url === 'string' &&
        /\/master-data\/admin\/countries\/\d+$/.test(url) &&
        ((init as RequestInit | undefined)?.method ?? 'GET') === 'DELETE'
      )
    })
    expect(deleteCalls).toHaveLength(1)
  })

  it('shows delete error from API', async () => {
    const user = userEvent.setup()
    setupFetchMock({
      user: { id: 50, role: 'consultancy_owner' },
      handlers: [
        ...defaultHandlersFor({ user: { id: 50, role: 'consultancy_owner' } }),
        {
          method: 'DELETE',
          path: /\/master-data\/admin\/countries\/\d+$/,
          handler: () => jsonResponse({ detail: 'Country is in use' }, 409),
        },
      ],
    })
    render(<MasterDataAdminPage />)

    await waitFor(() => {
      expect(screen.getByTestId('master-data-country-delete-1')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-country-delete-1'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-delete-error')).toHaveTextContent(
        'Country is in use',
      )
    })
  })

  it('creates a university referencing an existing country', async () => {
    const user = userEvent.setup()
    const createdUniversity = {
      id: 99,
      tenant_id: 10,
      country_id: 1,
      name: 'University of British Columbia',
    }
    const fetchSpy = setupFetchMock({
      user: { id: 50, role: 'consultancy_owner' },
      handlers: [
        ...defaultHandlersFor({ user: { id: 50, role: 'consultancy_owner' } }),
        {
          method: 'POST',
          path: /\/master-data\/admin\/universities$/,
          handler: () => jsonResponse(createdUniversity, 201),
        },
      ],
    })
    render(<MasterDataAdminPage />)

    await waitFor(() => {
      expect(screen.getByTestId('master-data-tab-universities')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-tab-universities'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-university-create-form')).toBeInTheDocument()
    })

    await user.selectOptions(screen.getByTestId('master-data-university-country'), '1')
    await user.type(screen.getByTestId('master-data-university-name'), 'University of British Columbia')
    await user.click(screen.getByTestId('master-data-university-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-success')).toHaveTextContent(
        'University "University of British Columbia" created.',
      )
    })

    const postCalls = fetchSpy.mock.calls.filter((call) => {
      const [url, init] = call
      if (typeof url !== 'string' || !url.endsWith('/master-data/admin/universities')) {
        return false
      }
      const method = (init as RequestInit | undefined)?.method ?? 'GET'
      return method === 'POST'
    })
    expect(postCalls).toHaveLength(1)
    const body = JSON.parse(String(postCalls[0]![1] as RequestInit).body)
    expect(body).toEqual({ country_id: 1, name: 'University of British Columbia' })
  })

  it('disables the university create submit when there are no countries', async () => {
    const user = userEvent.setup()
    renderPage({
      user: { id: 50, role: 'consultancy_owner' },
      countries: [],
    })

    await waitFor(() => {
      expect(screen.getByTestId('master-data-tab-universities')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-tab-universities'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-university-create-submit')).toBeDisabled()
    })
  })

  it('creates a program referencing an existing university', async () => {
    const user = userEvent.setup()
    const createdProgram = {
      id: 200,
      tenant_id: 10,
      university_id: 10,
      name: 'Master of Data Science',
    }
    const fetchSpy = setupFetchMock({
      user: { id: 50, role: 'consultancy_owner' },
      handlers: [
        ...defaultHandlersFor({ user: { id: 50, role: 'consultancy_owner' } }),
        {
          method: 'POST',
          path: /\/master-data\/admin\/programs$/,
          handler: () => jsonResponse(createdProgram, 201),
        },
      ],
    })
    render(<MasterDataAdminPage />)

    await waitFor(() => {
      expect(screen.getByTestId('master-data-tab-programs')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-tab-programs'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-program-create-form')).toBeInTheDocument()
    })

    await user.selectOptions(screen.getByTestId('master-data-program-university'), '10')
    await user.type(screen.getByTestId('master-data-program-name'), 'Master of Data Science')
    await user.click(screen.getByTestId('master-data-program-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-success')).toHaveTextContent(
        'Program "Master of Data Science" created.',
      )
    })

    const postCalls = fetchSpy.mock.calls.filter((call) => {
      const [url, init] = call
      if (typeof url !== 'string' || !url.endsWith('/master-data/admin/programs')) {
        return false
      }
      const method = (init as RequestInit | undefined)?.method ?? 'GET'
      return method === 'POST'
    })
    expect(postCalls).toHaveLength(1)
    const body = JSON.parse(String(postCalls[0]![1] as RequestInit).body)
    expect(body).toEqual({ university_id: 10, name: 'Master of Data Science' })
  })

  it('updates a program and removes the edit form on success', async () => {
    const user = userEvent.setup()
    const updatedProgram = { ...mockPrograms[0], name: 'CS MSc (renamed)' }
    setupFetchMock({
      user: { id: 50, role: 'consultancy_owner' },
      handlers: [
        ...defaultHandlersFor({ user: { id: 50, role: 'consultancy_owner' } }),
        {
          method: 'PATCH',
          path: /\/master-data\/admin\/programs\/\d+$/,
          handler: () => jsonResponse(updatedProgram),
        },
      ],
    })
    render(<MasterDataAdminPage />)

    await waitFor(() => {
      expect(screen.getByTestId('master-data-tab-programs')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-tab-programs'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-program-edit-100')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-program-edit-100'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-program-edit-name')).toHaveValue(
        'Computer Science MSc',
      )
    })

    await user.clear(screen.getByTestId('master-data-program-edit-name'))
    await user.type(screen.getByTestId('master-data-program-edit-name'), 'CS MSc (renamed)')
    await user.click(screen.getByTestId('master-data-program-edit-submit'))

    await waitFor(() => {
      expect(screen.queryByTestId('master-data-program-edit-name')).not.toBeInTheDocument()
    })
    expect(screen.getByTestId('master-data-success')).toHaveTextContent('CS MSc (renamed)')
  })

  it('deletes a program', async () => {
    const user = userEvent.setup()
    const fetchSpy = setupFetchMock({
      user: { id: 50, role: 'consultancy_owner' },
      handlers: [
        ...defaultHandlersFor({ user: { id: 50, role: 'consultancy_owner' } }),
        {
          method: 'DELETE',
          path: /\/master-data\/admin\/programs\/\d+$/,
          handler: () => jsonResponse(undefined, 204),
        },
      ],
    })
    render(<MasterDataAdminPage />)

    await waitFor(() => {
      expect(screen.getByTestId('master-data-tab-programs')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-tab-programs'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-program-delete-100')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-program-delete-100'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-success')).toHaveTextContent('deleted')
    })

    const deleteCalls = fetchSpy.mock.calls.filter((call) => {
      const [url, init] = call
      return (
        typeof url === 'string' &&
        /\/master-data\/admin\/programs\/\d+$/.test(url) &&
        ((init as RequestInit | undefined)?.method ?? 'GET') === 'DELETE'
      )
    })
    expect(deleteCalls).toHaveLength(1)
  })

  it('clears errors when switching tabs', async () => {
    const user = userEvent.setup()
    renderPage({
      user: { id: 50, role: 'consultancy_owner' },
      handlers: [
        {
          method: 'POST',
          path: /\/master-data\/admin\/countries$/,
          handler: () => jsonResponse({ detail: 'Name too long' }, 422),
        },
        {
          method: 'GET',
          path: /\/master-data\/admin\/countries$/,
          handler: () => jsonResponse(mockCountries),
        },
        {
          method: 'GET',
          path: /\/master-data\/admin\/universities$/,
          handler: () => jsonResponse(mockUniversities),
        },
        {
          method: 'GET',
          path: /\/master-data\/admin\/programs$/,
          handler: () => jsonResponse(mockPrograms),
        },
      ],
    })

    await waitFor(() => {
      expect(screen.getByTestId('master-data-country-create-form')).toBeInTheDocument()
    })

    await user.type(screen.getByTestId('master-data-country-name'), 'X')
    await user.type(screen.getByTestId('master-data-country-code'), 'XX')
    await user.click(screen.getByTestId('master-data-country-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('master-data-create-error')).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('master-data-tab-universities'))

    await waitFor(() => {
      expect(screen.queryByTestId('master-data-create-error')).not.toBeInTheDocument()
    })
  })
})