/**
 * Tests for ExportButton component (E44; Journey J37).
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ExportButton } from './ExportButton'

// Mock fetch
globalThis.fetch = vi.fn()

// Mock document methods for link creation
const mockLink = {
  href: '',
  download: '',
  click: vi.fn(),
}

describe('ExportButton', () => {
  let createElementSpy: any
  let appendChildSpy: any
  let removeChildSpy: any

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    // Reset mock link
    mockLink.href = ''
    mockLink.download = ''
    mockLink.click.mockClear()

    // Intercept only the anchor the component creates to trigger the download.
    // Every other element -- notably React Testing Library's own container --
    // must still be a real DOM node, so delegate to the originals.
    const realCreateElement = document.createElement.bind(document)
    createElementSpy = vi
      .spyOn(document, 'createElement')
      .mockImplementation((tagName: any, options?: any) =>
        tagName === 'a' ? (mockLink as any) : realCreateElement(tagName, options),
      )

    const realAppendChild = document.body.appendChild.bind(document.body)
    appendChildSpy = vi
      .spyOn(document.body, 'appendChild')
      .mockImplementation((node: any) => (node === mockLink ? node : realAppendChild(node)))

    const realRemoveChild = document.body.removeChild.bind(document.body)
    removeChildSpy = vi
      .spyOn(document.body, 'removeChild')
      .mockImplementation((node: any) => (node === mockLink ? node : realRemoveChild(node)))
  })

  afterEach(() => {
    // Clean up mocks
    createElementSpy?.mockRestore()
    appendChildSpy?.mockRestore()
    removeChildSpy?.mockRestore()
  })

  it('renders button with default label', () => {
    render(<ExportButton endpoint="/analytics/export/students" format="csv" />)
    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeInTheDocument()
  })

  it('renders button with custom label', () => {
    render(
      <ExportButton
        endpoint="/analytics/export/students"
        format="csv"
        label="Download Data"
      />,
    )
    expect(screen.getByRole('button', { name: 'Download Data' })).toBeInTheDocument()
  })

  it('renders Excel button with correct label', () => {
    render(<ExportButton endpoint="/analytics/export/students" format="xlsx" />)
    expect(screen.getByRole('button', { name: 'Export Excel' })).toBeInTheDocument()
  })

  it('disables button when loading', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as any // Never resolves

    render(<ExportButton endpoint="/analytics/export/students" format="csv" />)

    const button = screen.getByRole('button', { name: 'Export CSV' })
    await user.click(button)

    expect(screen.getByRole('button', { name: 'Exporting...' })).toBeDisabled()
  })

  it('disables button when disabled prop is true', () => {
    render(
      <ExportButton endpoint="/analytics/export/students" format="csv" disabled />,
    )
    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeDisabled()
  })

  it('triggers download on successful export', async () => {
    const user = userEvent.setup()
    const mockBlob = new Blob(['test,data'], { type: 'text/csv' })

    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        headers: {
          get: (name: string) => {
            if (name === 'Content-Disposition') {
              return 'attachment; filename="students-20240101_120000.csv"'
            }
            return null
          },
        },
        blob: () => Promise.resolve(mockBlob),
      } as unknown as Response),
    ) as any

    // Mock URL methods
    const mockCreateObjectUrl = vi.fn(() => 'blob:url')
    const mockRevokeObjectUrl = vi.fn()
    globalThis.URL.createObjectURL = mockCreateObjectUrl as any
    globalThis.URL.revokeObjectURL = mockRevokeObjectUrl as any

    render(<ExportButton endpoint="/analytics/export/students" format="csv" />)

    const button = screen.getByRole('button', { name: 'Export CSV' })
    await user.click(button)

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/analytics/export/students'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Accept: 'text/csv',
          }),
        }),
      )
      expect(mockCreateObjectUrl).toHaveBeenCalledWith(mockBlob)
      expect(mockLink.click).toHaveBeenCalled()
      expect(appendChildSpy).toHaveBeenCalledWith(mockLink)
      expect(removeChildSpy).toHaveBeenCalledWith(mockLink)
      expect(mockRevokeObjectUrl).toHaveBeenCalledWith('blob:url')
    })
  })

  it('includes query parameters in request', async () => {
    const user = userEvent.setup()
    const mockBlob = new Blob(['test,data'], { type: 'text/csv' })

    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        headers: {
          get: () => null,
        },
        blob: () => Promise.resolve(mockBlob),
      } as unknown as Response),
    ) as any

    globalThis.URL.createObjectURL = vi.fn(() => 'blob:url') as any
    globalThis.URL.revokeObjectURL = vi.fn() as any

    render(
      <ExportButton
        endpoint="/analytics/export/students"
        format="csv"
        queryParams={{ start_date: '2024-01-01', end_date: '2024-12-31' }}
      />,
    )

    const button = screen.getByRole('button', { name: 'Export CSV' })
    await user.click(button)

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('start_date=2024-01-01'),
        expect.anything(),
      )
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('end_date=2024-12-31'),
        expect.anything(),
      )
    })
  })

  it('shows user-friendly error message on 404 export failure', async () => {
    const user = userEvent.setup()

    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        headers: {
          get: () => null,
        },
        json: () => Promise.resolve({ detail: 'Not Found' }),
      } as unknown as Response),
    ) as any

    render(<ExportButton endpoint="/analytics/export/students" format="csv" />)

    const button = screen.getByRole('button', { name: 'Export CSV' })
    await user.click(button)

    await waitFor(() => {
      expect(screen.getByText('Export is temporarily unavailable. Please contact support if the problem persists.')).toBeInTheDocument()
    })

    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('shows user-friendly error message on 403 permission denied', async () => {
    const user = userEvent.setup()

    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
        headers: {
          get: () => null,
        },
        json: () => Promise.resolve({ detail: 'Forbidden' }),
      } as unknown as Response),
    ) as any

    render(<ExportButton endpoint="/analytics/export/students" format="csv" />)

    const button = screen.getByRole('button', { name: 'Export CSV' })
    await user.click(button)

    await waitFor(() => {
      expect(screen.getByText('You do not have permission to export this data.')).toBeInTheDocument()
    })

    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('uses Excel media type for xlsx format', async () => {
    const user = userEvent.setup()
    const mockBlob = new Blob(['excel,data'], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })

    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        headers: { get: () => null },
        blob: () => Promise.resolve(mockBlob),
      } as unknown as Response),
    ) as any

    globalThis.URL.createObjectURL = vi.fn(() => 'blob:url') as any
    globalThis.URL.revokeObjectURL = vi.fn() as any

    render(<ExportButton endpoint="/analytics/export/students" format="xlsx" />)

    const button = screen.getByRole('button', { name: 'Export Excel' })
    await user.click(button)

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/analytics/export/students'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Accept: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          }),
        }),
      )
    })
  })

  it('generates default filename when Content-Disposition is missing', async () => {
    const user = userEvent.setup()
    const mockBlob = new Blob(['test,data'], { type: 'text/csv' })

    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        headers: {
          get: () => null, // No Content-Disposition header
        },
        blob: () => Promise.resolve(mockBlob),
      } as unknown as Response),
    ) as any

    globalThis.URL.createObjectURL = vi.fn(() => 'blob:url') as any
    globalThis.URL.revokeObjectURL = vi.fn() as any

    render(<ExportButton endpoint="/analytics/export/students" format="csv" />)

    const button = screen.getByRole('button', { name: 'Export CSV' })
    await user.click(button)

    await waitFor(() => {
      expect(mockLink.download).toBe('export.csv')
    })
  })
})
