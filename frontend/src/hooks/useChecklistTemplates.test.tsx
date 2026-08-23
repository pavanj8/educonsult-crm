import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useChecklistTemplates } from './useChecklistTemplates'

const mockTemplateList = [
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

type QueueEntry = {
  ok: boolean
  status: number
  body: unknown
}

function okJson(body: unknown, status = 200): QueueEntry {
  return { ok: status >= 200 && status < 300, status, body }
}

/**
 * URL-aware fetch mock. The hook issues ``GET`` followed by mutation
 * requests; routing by ``method + path`` keeps the test stable
 * regardless of the order of subsequent assertions.
 */
function setupFetchMock(
  routes: Record<string, QueueEntry | (() => QueueEntry)>,
): ReturnType<typeof vi.fn> {
  const fetchSpy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = (init?.method ?? 'GET').toUpperCase()
    const pathOnly = url.split('?')[0] ?? url

    for (const [pattern, value] of Object.entries(routes)) {
      // Patterns look like ``"GET /checklist-templates"`` or
      // ``"PATCH /checklist-templates/\\d+"``. Match both the method
      // and the regex-shaped path.
      const [patternMethod, patternPath] = pattern.split(' ')
      if (patternMethod && patternMethod !== method) {
        continue
      }
      const regex = new RegExp(patternPath ?? pattern)
      if (regex.test(pathOnly)) {
        const entry = typeof value === 'function' ? value() : value
        return {
          ok: entry.ok,
          status: entry.status,
          json: async () => entry.body,
        } as Response
      }
    }

    throw new Error(`Unhandled fetch in test: ${method} ${url}`)
  })
  globalThis.fetch = fetchSpy as unknown as typeof fetch
  return fetchSpy
}

describe('useChecklistTemplates', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('fetches the templates on mount when authenticated', async () => {
    localStorage.setItem('access_token', 'test-token')
    const fetchSpy = setupFetchMock({
      'GET /checklist-templates$': okJson(mockTemplateList),
    })

    const { result } = renderHook(() => useChecklistTemplates())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.templates).toEqual(mockTemplateList)
    expect(result.current.error).toBeNull()
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('does not fetch when no access token is present and exposes an empty list', async () => {
    const fetchSpy = vi.fn()
    globalThis.fetch = fetchSpy as unknown as typeof fetch

    const { result } = renderHook(() => useChecklistTemplates())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.templates).toEqual([])
    expect(result.current.error).toBeNull()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('maps 403/401 responses to a permission-friendly error message', async () => {
    localStorage.setItem('access_token', 'test-token')
    setupFetchMock({
      'GET /checklist-templates$': okJson({ detail: 'Forbidden' }, 403),
    })

    const { result } = renderHook(() => useChecklistTemplates())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.templates).toEqual([])
    expect(result.current.error).toMatch(/permission/i)
  })

  it('falls back to a generic error message for non-401/403 load failures', async () => {
    localStorage.setItem('access_token', 'test-token')
    setupFetchMock({
      'GET /checklist-templates$': okJson({ detail: 'Server exploded' }, 500),
    })

    const { result } = renderHook(() => useChecklistTemplates())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.templates).toEqual([])
    expect(result.current.error).toBe('Failed to load checklist templates')
  })

  it('creates a template, appends it to the list, and exposes it via the return value', async () => {
    localStorage.setItem('access_token', 'test-token')
    const created = {
      id: 3,
      tenant_id: 10,
      stage: 'registered' as const,
      program_id: null,
      name: 'Birth certificate',
      description: null,
      required: true,
      order_index: 2,
    }
    setupFetchMock({
      'GET /checklist-templates$': okJson(mockTemplateList),
      'POST /checklist-templates$': okJson(created, 201),
    })

    const { result } = renderHook(() => useChecklistTemplates())
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    let returned: typeof created | null = null
    await act(async () => {
      returned = await result.current.createTemplate({
        stage: 'registered',
        program_id: null,
        name: 'Birth certificate',
        description: null,
        required: true,
        order_index: 2,
      })
    })

    expect(returned).toEqual(created)
    expect(result.current.templates).toEqual([...mockTemplateList, created])
    expect(result.current.createError).toBeNull()
  })

  it('surfaces the API error message on create and keeps the list unchanged', async () => {
    localStorage.setItem('access_token', 'test-token')
    setupFetchMock({
      'GET /checklist-templates$': okJson(mockTemplateList),
      'POST /checklist-templates$': okJson({ detail: 'name is required' }, 422),
    })

    const { result } = renderHook(() => useChecklistTemplates())
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await expect(
        result.current.createTemplate({
          stage: 'registered',
          program_id: null,
          name: '',
          description: null,
          required: true,
          order_index: null,
        }),
      ).rejects.toMatchObject({ status: 422 })
    })

    await waitFor(() => {
      expect(result.current.createError).toBe('name is required')
    })
    expect(result.current.templates).toEqual(mockTemplateList)
  })

  it('updates a template in place and returns the updated row', async () => {
    localStorage.setItem('access_token', 'test-token')
    const updated = { ...mockTemplateList[0], name: 'Passport (renamed)' }
    setupFetchMock({
      'GET /checklist-templates$': okJson(mockTemplateList),
      'PATCH /checklist-templates/\\d+$': okJson(updated),
    })

    const { result } = renderHook(() => useChecklistTemplates())
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    let returned: typeof updated | null = null
    await act(async () => {
      returned = await result.current.updateTemplate(1, { name: 'Passport (renamed)' })
    })

    expect(returned).toEqual(updated)
    expect(result.current.templates[0]).toEqual(updated)
    expect(result.current.updateError).toBeNull()
  })

  it('surfaces the API error message on update and preserves the original row', async () => {
    localStorage.setItem('access_token', 'test-token')
    setupFetchMock({
      'GET /checklist-templates$': okJson(mockTemplateList),
      'PATCH /checklist-templates/\\d+$': okJson({ detail: 'Template not found' }, 404),
    })

    const { result } = renderHook(() => useChecklistTemplates())
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await expect(
        result.current.updateTemplate(1, { name: 'ignored' }),
      ).rejects.toMatchObject({ status: 404 })
    })

    await waitFor(() => {
      expect(result.current.updateError).toBe('Template not found')
    })
    expect(result.current.templates).toEqual(mockTemplateList)
  })

  it('deletes a template and removes it from the list', async () => {
    localStorage.setItem('access_token', 'test-token')
    setupFetchMock({
      'GET /checklist-templates$': okJson(mockTemplateList),
      'DELETE /checklist-templates/\\d+$': okJson(undefined, 204),
    })

    const { result } = renderHook(() => useChecklistTemplates())
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.deleteTemplate(2)
    })

    expect(result.current.templates).toEqual([mockTemplateList[0]])
    expect(result.current.deleteError).toBeNull()
    expect(result.current.deletingId).toBeNull()
  })

  it('surfaces the API error message on delete and keeps the row in the list', async () => {
    localStorage.setItem('access_token', 'test-token')
    setupFetchMock({
      'GET /checklist-templates$': okJson(mockTemplateList),
      'DELETE /checklist-templates/\\d+$': okJson({ detail: 'Template is in use' }, 409),
    })

    const { result } = renderHook(() => useChecklistTemplates())
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await expect(result.current.deleteTemplate(1)).rejects.toMatchObject({
        status: 409,
      })
    })

    await waitFor(() => {
      expect(result.current.deleteError).toBe('Template is in use')
    })
    expect(result.current.templates).toEqual(mockTemplateList)
    expect(result.current.deletingId).toBeNull()
  })

  it('clearErrors() resets every error slot to null', async () => {
    localStorage.setItem('access_token', 'test-token')
    setupFetchMock({
      'GET /checklist-templates$': okJson(mockTemplateList),
      'POST /checklist-templates$': okJson({ detail: 'create failed' }, 422),
      'PATCH /checklist-templates/\\d+$': okJson({ detail: 'update failed' }, 422),
      'DELETE /checklist-templates/\\d+$': okJson({ detail: 'delete failed' }, 422),
    })

    const { result } = renderHook(() => useChecklistTemplates())
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await expect(
        result.current.createTemplate({
          stage: 'registered',
          program_id: null,
          name: 'x',
          description: null,
          required: true,
          order_index: null,
        }),
      ).rejects.toBeDefined()
      await expect(
        result.current.updateTemplate(1, { name: 'x' }),
      ).rejects.toBeDefined()
      await expect(result.current.deleteTemplate(1)).rejects.toBeDefined()
    })

    await waitFor(() => {
      expect(result.current.createError).toBe('create failed')
      expect(result.current.updateError).toBe('update failed')
      expect(result.current.deleteError).toBe('delete failed')
    })

    act(() => {
      result.current.clearErrors()
    })

    expect(result.current.createError).toBeNull()
    expect(result.current.updateError).toBeNull()
    expect(result.current.deleteError).toBeNull()
  })
})
