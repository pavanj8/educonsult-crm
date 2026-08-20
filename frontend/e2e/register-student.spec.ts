import { expect, test } from './fixtures.js'
import { REGISTER_PATH } from '../src/routes/paths.js'

const VALID_REGISTRATION = {
  tenantSlug: 'apex',
  branchId: '1',
  name: 'Rahul Kumar',
  email: 'new.student@example.test',
  password: 'StudentPass1!',
  phone: '+91-9876543210',
  dateOfBirth: '2000-05-15',
}

async function mockRegisterStudentSuccess(page: import('@playwright/test').Page) {
  await page.route('**/auth/register-student', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 42,
        email: VALID_REGISTRATION.email,
        role: 'student',
        tenant_id: 10,
        branch_id: 1,
        name: VALID_REGISTRATION.name,
        phone: VALID_REGISTRATION.phone,
        date_of_birth: VALID_REGISTRATION.dateOfBirth,
        target_country_id: null,
        target_university_id: null,
        target_program_id: null,
        access_token: 'student-access-token',
        refresh_token: 'student-refresh-token',
        token_type: 'bearer',
        created_at: '2026-01-01T00:00:00Z',
      }),
    })
  })

  await page.route('**/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 42,
        email: VALID_REGISTRATION.email,
        role: 'student',
        tenant_id: 10,
        branch_id: 1,
      }),
    })
  })
}

async function fillRegisterForm(
  page: import('@playwright/test').Page,
  data = VALID_REGISTRATION,
) {
  await page.getByTestId('register-tenant-slug').fill(data.tenantSlug)
  await page.getByTestId('register-branch-id').fill(data.branchId)
  await page.getByTestId('register-name').fill(data.name)
  await page.getByTestId('register-email').fill(data.email)
  await page.getByTestId('register-password').fill(data.password)
  await page.getByTestId('register-phone').fill(data.phone)
  await page.getByTestId('register-date-of-birth').fill(data.dateOfBirth)
}

test.describe('Student registration form', () => {
  test('registration page exposes the form selector contract', async ({ page }) => {
    await page.goto(REGISTER_PATH)

    await expect(page).toHaveURL(REGISTER_PATH)
    await expect(page.getByRole('heading', { name: 'Create student account' })).toBeVisible()
    await expect(page.getByTestId('register-tenant-slug')).toBeVisible()
    await expect(page.getByTestId('register-branch-id')).toBeVisible()
    await expect(page.getByTestId('register-name')).toBeVisible()
    await expect(page.getByTestId('register-email')).toBeVisible()
    await expect(page.getByTestId('register-password')).toBeVisible()
    await expect(page.getByTestId('register-phone')).toBeVisible()
    await expect(page.getByTestId('register-date-of-birth')).toBeVisible()
    await expect(page.getByTestId('register-submit')).toBeVisible()
  })

  test('successful registration stores tokens via mocked /auth/register-student', async ({
    page,
  }) => {
    await mockRegisterStudentSuccess(page)
    await page.goto(REGISTER_PATH)

    await fillRegisterForm(page)
    await page.getByTestId('register-submit').click()
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
        access: 'student-access-token',
        refresh: 'student-refresh-token',
      })
  })

  test('failed registration shows an error message', async ({ page }) => {
    await page.route('**/auth/register-student', async (route) => {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Email already registered' }),
      })
    })

    await page.goto(REGISTER_PATH)
    await fillRegisterForm(page)
    await page.getByTestId('register-submit').click()

    await expect(page.getByTestId('register-error')).toBeVisible()
    await expect(page.getByTestId('register-error')).toHaveText('Email already registered')
    await expect
      .poll(async () => page.evaluate(() => localStorage.getItem('access_token')))
      .toBeNull()
  })

  test('login page links to registration page', async ({ page }) => {
    await page.goto('/login')

    await page.getByRole('link', { name: 'Create an account' }).click()
    await expect(page).toHaveURL(REGISTER_PATH)
    await expect(page.getByRole('heading', { name: 'Create student account' })).toBeVisible()
  })
})
