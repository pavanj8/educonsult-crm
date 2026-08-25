import { test, expect } from '@playwright/test'

/**
 * E2E tests for the marketing landing page (E53; Requirements §10).
 * Tests that CTA buttons correctly navigate to login and signup pages.
 */

test.describe('Landing Page CTA Buttons', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/landing')
  })

  test('hero section CTA buttons navigate to correct routes', async ({ page }) => {
    // "Start Free Trial" button should navigate to /register
    await page.getByRole('link', { name: 'Start Free Trial' }).click()
    await expect(page).toHaveURL('/register')
    await expect(page.getByRole('heading', { name: /create student account/i })).toBeVisible()

    // Go back to landing page
    await page.goto('/landing')

    // "Log In" button should navigate to /login
    await page.getByRole('link', { name: 'Log In' }).click()
    await expect(page).toHaveURL('/login')
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()
  })

  test('bottom CTA section buttons navigate to correct routes', async ({ page }) => {
    // Scroll to CTA section
    await page.getByRole('heading', { name: 'Ready to Transform Your Consultancy?' }).scrollIntoViewIfNeeded()

    // "Get Started Free" button should navigate to /register
    await page.getByRole('link', { name: 'Get Started Free' }).click()
    await expect(page).toHaveURL('/register')
    await expect(page.getByRole('heading', { name: /create student account/i })).toBeVisible()

    // Go back to landing page
    await page.goto('/landing')

    // Scroll to CTA section again
    await page.getByRole('heading', { name: 'Ready to Transform Your Consultancy?' }).scrollIntoViewIfNeeded()

    // "Request Demo" button should navigate to /login
    await page.getByRole('link', { name: 'Request Demo' }).click()
    await expect(page).toHaveURL('/login')
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()
  })

  test('all CTA links are accessible and have proper href attributes', async ({ page }) => {
    // Check hero CTAs
    const startTrialLink = page.getByRole('link', { name: 'Start Free Trial' })
    await expect(startTrialLink).toHaveAttribute('href', '/register')
    await expect(startTrialLink).toBeVisible()

    const loginLink = page.getByRole('link', { name: 'Log In' })
    await expect(loginLink).toHaveAttribute('href', '/login')
    await expect(loginLink).toBeVisible()

    // Scroll to bottom CTA section
    await page.getByRole('heading', { name: 'Ready to Transform Your Consultancy?' }).scrollIntoViewIfNeeded()

    // Check bottom CTAs
    const getStartedLink = page.getByRole('link', { name: 'Get Started Free' })
    await expect(getStartedLink).toHaveAttribute('href', '/register')
    await expect(getStartedLink).toBeVisible()

    const requestDemoLink = page.getByRole('link', { name: 'Request Demo' })
    await expect(requestDemoLink).toHaveAttribute('href', '/login')
    await expect(requestDemoLink).toBeVisible()
  })
})

test.describe('Landing Page Accessibility', () => {
  test('has proper heading structure and aria labels', async ({ page }) => {
    await page.goto('/landing')

    // Hero section has proper aria-labelledby
    const heroSection = page.locator('[aria-labelledby="hero-heading"]')
    await expect(heroSection).toBeVisible()

    // Hero heading exists with matching ID
    const heroHeading = page.locator('#hero-heading')
    await expect(heroHeading).toBeVisible()
    await expect(heroHeading).toHaveText(/streamline your education consultancy/i)

    // Features section has proper aria-labelledby
    const featuresSection = page.locator('[aria-labelledby="features-heading"]')
    await expect(featuresSection).toBeVisible()

    // CTA section has proper aria-labelledby
    const ctaSection = page.locator('[aria-labelledby="cta-heading"]')
    await expect(ctaSection).toBeVisible()
  })
})
