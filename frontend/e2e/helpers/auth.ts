import type { Page, Route } from '@playwright/test'

/** Return Authorization headers for API requests (JWT verification wired in E5). */
export function makeAuthHeaders(accessToken = 'test-access-token'): Record<string, string> {
  return { Authorization: `Bearer ${accessToken}` }
}

export const LOGIN_PATH = '/login'

export type UserRole =
  | 'super_admin'
  | 'consultancy_owner'
  | 'branch_manager'
  | 'counselor'
  | 'document_verifier'
  | 'visa_processor'
  | 'receptionist'
  | 'student'

export type LoginCredentials = {
  email: string
  password: string
}

export type LoginTokens = {
  access_token: string
  refresh_token?: string
  token_type?: string
}

export const DEMO_LOGIN: LoginCredentials = {
  email: 'counselor@demo.test',
  password: 'demo-password',
}

const ROLE_TOKENS: Record<UserRole, string> = {
  super_admin: 'test-token-super-admin',
  consultancy_owner: 'test-token-consultancy-owner',
  branch_manager: 'test-token-branch-manager',
  counselor: 'test-token-counselor',
  document_verifier: 'test-token-document-verifier',
  visa_processor: 'test-token-visa-processor',
  receptionist: 'test-token-receptionist',
  student: 'test-token-student',
}

export function accessTokenForRole(role: UserRole): string {
  return ROLE_TOKENS[role]
}

export function loginTokensForRole(role: UserRole): LoginTokens {
  return {
    access_token: accessTokenForRole(role),
    refresh_token: `refresh-${role}`,
    token_type: 'bearer',
  }
}

export async function setAuthSession(page: Page, accessToken: string, refreshToken?: string): Promise<void> {
  await page.addInitScript(
    ({ token, refresh }) => {
      localStorage.setItem('access_token', token)
      if (refresh) {
        localStorage.setItem('refresh_token', refresh)
      }
    },
    { token: accessToken, refresh: refreshToken },
  )
}

export async function clearAuthSession(page: Page): Promise<void> {
  await page.evaluate(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  })
}

export async function mockLoginApi(
  page: Page,
  tokens: LoginTokens = loginTokensForRole('counselor'),
): Promise<void> {
  await page.route('**/auth/login', async (route: Route) => {
    if (route.request().method() !== 'POST') {
      await route.continue()
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(tokens),
    })
  })
}

export async function mockLoginFailure(
  page: Page,
  status = 401,
  detail = 'Invalid email or password',
): Promise<void> {
  await page.route('**/auth/login', async (route: Route) => {
    if (route.request().method() !== 'POST') {
      await route.continue()
      return
    }

    await route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify({ detail }),
    })
  })
}

export async function fillLoginForm(page: Page, credentials: LoginCredentials = DEMO_LOGIN): Promise<void> {
  await page.getByTestId('login-email').fill(credentials.email)
  await page.getByTestId('login-password').fill(credentials.password)
}

export async function submitLoginForm(page: Page): Promise<void> {
  await page.getByTestId('login-submit').click()
}

export async function loginThroughForm(
  page: Page,
  credentials: LoginCredentials = DEMO_LOGIN,
): Promise<void> {
  await fillLoginForm(page, credentials)
  await submitLoginForm(page)
}
