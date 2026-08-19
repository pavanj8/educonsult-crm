import {
  accessTokenForRole,
  clearAuthSession,
  DEMO_LOGIN,
  loginThroughForm,
  loginTokensForRole,
  makeAuthHeaders,
  mockAuthMe,
  mockLoginFailure,
  setAuthSession,
} from './helpers/auth.js'
import { expect, test } from './fixtures.js'
import { gotoHome, gotoLoginForm, LOGIN_FORM_PATH } from './helpers/navigation.js'

test.describe('Login flow smoke test', () => {
  test('makeAuthHeaders uses the default test access token', () => {
    expect(makeAuthHeaders()).toEqual({
      Authorization: 'Bearer test-access-token',
    })
  })

  test('login form fixture exposes the E5 selector contract', async ({ page }) => {
    await gotoLoginForm(page)

    await expect(page).toHaveURL(LOGIN_FORM_PATH)
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    await expect(page.getByTestId('login-email')).toBeVisible()
    await expect(page.getByTestId('login-password')).toBeVisible()
    await expect(page.getByTestId('login-submit')).toBeVisible()
  })

  test('successful login stores tokens via mocked /auth/login', async ({ loginPage, page }) => {
    void loginPage

    await mockAuthMe(page)
    await loginThroughForm(page, DEMO_LOGIN)
    await page.waitForURL('/')

    await expect(page.getByText('Welcome to EduConsult CRM')).toBeVisible()

    await expect
      .poll(async () =>
        page.evaluate(() => ({
          access: localStorage.getItem('access_token'),
          refresh: localStorage.getItem('refresh_token'),
        })),
      )
      .toEqual({
        access: accessTokenForRole('counselor'),
        refresh: 'refresh-counselor',
      })
  })

  test('failed login shows an error message', async ({ page }) => {
    await mockLoginFailure(page)
    await gotoLoginForm(page)

    await loginThroughForm(page, DEMO_LOGIN)

    await expect(page.getByTestId('login-error')).toBeVisible()
    await expect(page.getByTestId('login-error')).toHaveText('Invalid email or password')
    await expect
      .poll(async () => page.evaluate(() => localStorage.getItem('access_token')))
      .toBeNull()
  })

  test('authenticatedPage fixture loads the app shell with a session token', async ({
    authenticatedPage,
    page,
  }) => {
    void authenticatedPage

    await expect(page).toHaveURL('/')
    await expect(page.getByRole('heading', { name: 'EduConsult CRM' })).toBeVisible()
    await expect(page.getByText('Welcome to EduConsult CRM')).toBeVisible()
    await expect
      .poll(async () => page.evaluate(() => localStorage.getItem('access_token')))
      .toBe(accessTokenForRole('counselor'))
  })

  test('counselor role login issues role-scoped tokens', async ({ counselorPage, page }) => {
    void counselorPage

    await mockAuthMe(page)
    await loginThroughForm(page, DEMO_LOGIN)
    await page.waitForURL('/')

    await expect(page.getByText('Welcome to EduConsult CRM')).toBeVisible()

    const expected = loginTokensForRole('counselor')
    await expect
      .poll(async () =>
        page.evaluate(() => ({
          access: localStorage.getItem('access_token'),
          refresh: localStorage.getItem('refresh_token'),
        })),
      )
      .toEqual({
        access: expected.access_token,
        refresh: expected.refresh_token,
      })
  })

  test('setAuthSession and clearAuthSession manage localStorage tokens', async ({ page }) => {
    await setAuthSession(page, 'session-token', 'refresh-token')
    await gotoHome(page)

    await expect
      .poll(async () =>
        page.evaluate(() => ({
          access: localStorage.getItem('access_token'),
          refresh: localStorage.getItem('refresh_token'),
        })),
      )
      .toEqual({ access: 'session-token', refresh: 'refresh-token' })

    await clearAuthSession(page)

    await expect
      .poll(async () =>
        page.evaluate(() => ({
          access: localStorage.getItem('access_token'),
          refresh: localStorage.getItem('refresh_token'),
        })),
      )
      .toEqual({ access: null, refresh: null })
  })
})
