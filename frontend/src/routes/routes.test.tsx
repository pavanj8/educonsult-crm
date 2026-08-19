import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import AppLayout from '../layouts/AppLayout'
import HomePage from '../pages/HomePage'
import NotFoundPage from '../pages/NotFoundPage'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('routing shell', () => {
  it('renders the app layout and home page at /', () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], unread_count: 0 }),
    }) as typeof fetch

    renderAt('/')

    expect(screen.getByRole('heading', { name: 'EduConsult CRM' })).toBeInTheDocument()
    expect(screen.getByText('Welcome to EduConsult CRM')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
  })

  it('renders the not found page for unknown routes', () => {
    renderAt('/unknown-route')

    expect(screen.getByText('Page not found')).toBeInTheDocument()
  })
})
