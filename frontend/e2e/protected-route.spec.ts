import { expect, test } from './fixtures.js'
import { mockAuthMe } from './helpers/auth.js'
import { gotoHome, gotoPath, LOGIN_PATH } from './helpers/navigation.js'

test.describe('Protected routes', () => {
  test('unauthenticated visit to home redirects to login', async ({ page }) => {
    await gotoHome(page)

    await expect(page).toHaveURL(LOGIN_PATH)
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    await expect(page.getByTestId('login-email')).toBeVisible()
  })

  test('unauthenticated deep link redirects to login and preserves return path', async ({ page }) => {
    await gotoPath(page, '/students/42')

    await expect(page).toHaveURL(LOGIN_PATH)
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()

    const returnPath = await page.evaluate(() => {
      const state = (globalThis as unknown as { history?: { state?: unknown } }).history?.state as
        | { usr?: { from?: { pathname?: string } } }
        | null
        | undefined
      return state?.usr?.from?.pathname ?? null
    })
    expect(returnPath).toBe('/students/42')
  })

  test('authenticated visit to home loads the app shell', async ({ page }) => {
    await mockAuthMe(page)
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-counselor')
      localStorage.setItem('refresh_token', 'refresh-counselor')
    })

    await gotoHome(page)

    await expect(page).toHaveURL('/')
    await expect(page.getByRole('heading', { name: 'EduConsult CRM' })).toBeVisible()
    await expect(page.getByText('Welcome to EduConsult CRM')).toBeVisible()
  })
})
