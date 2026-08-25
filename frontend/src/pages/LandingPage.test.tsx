import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import LandingPage from './LandingPage'
import { LANDING_PATH } from '../routes/paths'

// Mock i18n
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue: string) => defaultValue || key,
  }),
}))

function renderWithRouter(component: React.ReactElement) {
  return render(<BrowserRouter>{component}</BrowserRouter>)
}

describe('LandingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })
  it('renders hero section with title and CTA buttons', () => {
    renderWithRouter(<LandingPage />)

    // Hero heading
    expect(
      screen.getByRole('heading', {
        name: /streamline your education consultancy/i,
        level: 1,
      })
    ).toBeInTheDocument()

    // CTA buttons
    expect(
      screen.getByRole('link', { name: /start free trial/i })
    ).toHaveAttribute('href', '/register')
    expect(screen.getByRole('link', { name: /log in/i })).toHaveAttribute(
      'href',
      '/login'
    )
  })

  it('renders features section with six feature cards', () => {
    renderWithRouter(<LandingPage />)

    // Features section heading
    expect(
      screen.getByRole('heading', {
        name: /everything you need to succeed/i,
      })
    ).toBeInTheDocument()

    // Feature headings
    expect(
      screen.getByRole('heading', { name: /student management/i })
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /application pipeline/i })
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /document management/i })
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /team collaboration/i })
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /analytics & reporting/i })
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /multi-branch support/i })
    ).toBeInTheDocument()
  })

  it('renders CTA section with action buttons', () => {
    renderWithRouter(<LandingPage />)

    // CTA heading
    expect(
      screen.getByRole('heading', {
        name: /ready to transform your consultancy\?/i,
      })
    ).toBeInTheDocument()

    // CTA buttons
    expect(
      screen.getByRole('link', { name: /get started free/i })
    ).toHaveAttribute('href', '/register')
    expect(
      screen.getByRole('link', { name: /request demo/i })
    ).toHaveAttribute('href', '/login')
  })

  it('renders footer with copyright text', () => {
    renderWithRouter(<LandingPage />)

    expect(
      screen.getByText(/© 2024 educonsult crm\. all rights reserved\./i)
    ).toBeInTheDocument()
  })

  it('has proper accessibility attributes', () => {
    const { container } = renderWithRouter(<LandingPage />)

    // Hero section has aria-labelledby
    const heroSection = container.querySelector('[aria-labelledby="hero-heading"]')
    expect(heroSection).toBeInTheDocument()
    // Verify the heading with that ID exists
    const heroHeading = container.querySelector('#hero-heading')
    expect(heroHeading).toBeInTheDocument()

    // Features section has aria-labelledby
    const featuresSection = container.querySelector(
      '[aria-labelledby="features-heading"]'
    )
    expect(featuresSection).toBeInTheDocument()

    // CTA section has aria-labelledby
    const ctaSection = container.querySelector('[aria-labelledby="cta-heading"]')
    expect(ctaSection).toBeInTheDocument()

    // Hero visual is hidden from screen readers
    const heroVisual = container.querySelector('[aria-hidden="true"]')
    expect(heroVisual).toBeInTheDocument()
  })

  it('renders all sections in correct order', () => {
    const { container } = renderWithRouter(<LandingPage />)

    const sections = container.querySelectorAll('section, footer')
    expect(sections).toHaveLength(4) // hero, features, CTA, footer

    // First section should be hero
    expect(sections[0]).toHaveAttribute('aria-labelledby', 'hero-heading')

    // Second section should be features
    expect(sections[1]).toHaveAttribute('aria-labelledby', 'features-heading')

    // Third section should be CTA
    expect(sections[2]).toHaveAttribute('aria-labelledby', 'cta-heading')

    // Fourth element should be footer
    expect(sections[3].tagName.toLowerCase()).toBe('footer')
  })

  it('LANDING_PATH is exported correctly', () => {
    expect(LANDING_PATH).toBe('/landing')
  })
})
