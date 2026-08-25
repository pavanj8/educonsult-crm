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

    // Set up mocks before rendering
    createElementSpy = vi.spyOn(document, 'createElement').mockReturnValue(mockLink as any)
    appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation((node) => node)
    removeChildSpy = vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node)
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

  it('shows error message on export failure', async () => {
    const user = userEvent.setup()

    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        headers: {
          get: () => null,
        },
        json: () => Promise.resolve({ detail: 'Export failed: insufficient permissions' }),
      } as unknown as Response),
    ) as any

    const createElementSpy2 = vi.spyOn(document, 'createElement').mockReturnValue(mockLink as any)
    const appendChildSpy2 = vi.spyOn(document.body, 'appendChild').mockImplementation(() => mockLink as any)
    const removeChildSpy2 = vi.spyOn(document.body, 'removeChild').mockImplementation(() => mockLink as any)

    render(<ExportButton endpoint="/analytics/export/students" format="csv" />)

    const button = screen.getByRole('button', { name: 'Export CSV' })
    await user.click(button)

    await waitFor(() => {
      expect(screen.getByText('Export failed: insufficient permissions')).toBeInTheDocument()
    })

    // Error should clear after 5 seconds (testing that it appears at least)
    expect(screen.getByRole('alert')).toBeInTheDocument()

    createElementSpy2.mockRestore()
    appendChildSpy2.mockRestore()
    removeChildSpy2.mockRestore()
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

    const createElementSpy2 = vi.spyOn(document, 'createElement').mockReturnValue(mockLink as any)
    const appendChildSpy2 = vi.spyOn(document.body, 'appendChild').mockImplementation(() => mockLink as any)
    const removeChildSpy2 = vi.spyOn(document.body, 'removeChild').mockImplementation(() => mockLink as any)

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

    createElementSpy2.mockRestore()
    appendChildSpy2.mockRestore()
    removeChildSpy2.mockRestore()
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

    const createElementSpy2 = vi.spyOn(document, 'createElement').mockReturnValue(mockLink as any)
    const appendChildSpy2 = vi.spyOn(document.body, 'appendChild').mockImplementation(() => mockLink as any)
    const removeChildSpy2 = vi.spyOn(document.body, 'removeChild').mockImplementation(() => mockLink as any)

    render(<ExportButton endpoint="/analytics/export/students" format="csv" />)

    const button = screen.getByRole('button', { name: 'Export CSV' })
    await user.click(button)

    await waitFor(() => {
      expect(mockLink.download).toBe('export.csv')
    })

    createElementSpy2.mockRestore()
    appendChildSpy2.mockRestore()
    removeChildSpy2.mockRestore()
  })
})
