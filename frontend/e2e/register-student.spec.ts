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
  countryId: '1',
  universityId: '10',
  programId: '100',
}

const MOCK_COUNTRIES = [{ id: 1, tenant_id: 10, name: 'Canada', code: 'CA' }]
const MOCK_UNIVERSITIES = [{ id: 10, tenant_id: 10, country_id: 1, name: 'University of Toronto' }]
const MOCK_PROGRAMS = [{ id: 100, tenant_id: 10, university_id: 10, name: 'Computer Science MSc' }]

async function waitForSelectOption(
  page: import('@playwright/test').Page,
  selectTestId: string,
  optionLabel: string,
) {
  await expect(
    page.getByTestId(selectTestId).locator('option', { hasText: optionLabel }),
  ).toHaveCount(1, { timeout: 5000 })
}

async function expectSelectOptionAbsent(
  page: import('@playwright/test').Page,
  selectTestId: string,
  optionLabel: string,
) {
  await expect(
    page.getByTestId(selectTestId).locator('option', { hasText: optionLabel }),
  ).toHaveCount(0)
}

async function mockMasterDataRoutes(page: import('@playwright/test').Page) {
  await page.route('**/tenants/apex/countries', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_COUNTRIES),
    })
  })

  await page.route('**/tenants/apex/universities?country_id=1', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_UNIVERSITIES),
    })
  })

  await page.route('**/tenants/apex/programs?university_id=10', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_PROGRAMS),
    })
  })
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
        target_country_id: 1,
        target_university_id: 10,
        target_program_id: 100,
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
  await waitForSelectOption(page, 'register-target-country', 'Canada')
  if (data.countryId) {
    await page.getByTestId('register-target-country').selectOption(data.countryId)
    await waitForSelectOption(page, 'register-target-university', 'University of Toronto')
  }
  if (data.universityId) {
    await page.getByTestId('register-target-university').selectOption(data.universityId)
    await waitForSelectOption(page, 'register-target-program', 'Computer Science MSc')
  }
  if (data.programId) {
    await page.getByTestId('register-target-program').selectOption(data.programId)
  }
  await page.getByTestId('register-branch-id').fill(data.branchId)
  await page.getByTestId('register-name').fill(data.name)
  await page.getByTestId('register-email').fill(data.email)
  await page.getByTestId('register-password').fill(data.password)
  await page.getByTestId('register-phone').fill(data.phone)
  await page.getByTestId('register-date-of-birth').fill(data.dateOfBirth)
}

test.describe('Student registration form', () => {
  test('registration page exposes the form selector contract', async ({ page }) => {
    await mockMasterDataRoutes(page)
    await page.goto(REGISTER_PATH)

    await expect(page).toHaveURL(REGISTER_PATH)
    await expect(page.getByRole('heading', { name: 'Create student account' })).toBeVisible()
    await expect(page.getByTestId('register-tenant-slug')).toBeVisible()
    await expect(page.getByTestId('register-branch-id')).toBeVisible()
    await expect(page.getByTestId('register-target-country')).toBeVisible()
    await expect(page.getByTestId('register-target-university')).toBeVisible()
    await expect(page.getByTestId('register-target-program')).toBeVisible()
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
    let registerRequestBody: Record<string, unknown> | null = null
    await mockMasterDataRoutes(page)
    await page.route('**/auth/register-student', async (route) => {
      registerRequestBody = route.request().postDataJSON() as Record<string, unknown>
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
          target_country_id: 1,
          target_university_id: 10,
          target_program_id: 100,
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
    await page.goto(REGISTER_PATH)

    await fillRegisterForm(page)
    await page.getByTestId('register-submit').click()
    await page.waitForURL('/')

    await expect(page.getByText('Welcome to EduConsult CRM')).toBeVisible()
    expect(registerRequestBody).toMatchObject({
      target_country_id: 1,
      target_university_id: 10,
      target_program_id: 100,
    })

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
    await mockMasterDataRoutes(page)
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

  test('slower previous slug response does not replace current country options', async ({
    page,
  }) => {
    let resolveSlow: (() => void) | null = null
    const slowReady = new Promise<void>((resolve) => {
      resolveSlow = resolve
    })

    await page.route('**/tenants/slow/countries', async (route) => {
      await slowReady
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 99, tenant_id: 10, name: 'Stale Country', code: 'ST' }]),
      })
    })

    await page.route('**/tenants/fast/countries', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_COUNTRIES),
      })
    })

    await page.goto(REGISTER_PATH)
    await page.getByTestId('register-tenant-slug').fill('slow')
    await page.waitForTimeout(350)
    await page.getByTestId('register-tenant-slug').fill('fast')

    await waitForSelectOption(page, 'register-target-country', 'Canada')
    await expectSelectOptionAbsent(page, 'register-target-country', 'Stale Country')

    resolveSlow?.()
    await page.waitForTimeout(300)
    await waitForSelectOption(page, 'register-target-country', 'Canada')
    await expectSelectOptionAbsent(page, 'register-target-country', 'Stale Country')
  })

  test('unknown consultancy shows country error alert inside study preferences fieldset', async ({
    page,
  }) => {
    await page.route('**/tenants/missing/countries', async (route) => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Tenant not found' }),
      })
    })

    await page.goto(REGISTER_PATH)
    await page.getByTestId('register-tenant-slug').fill('missing')

    const fieldset = page.getByRole('group', { name: 'Study preferences' })
    await expect(fieldset.getByTestId('register-countries-error')).toBeVisible({ timeout: 5000 })
    await expect(fieldset.getByTestId('register-countries-error')).toHaveText(
      'Consultancy not found',
    )
  })

  test('changing country clears university and program selections', async ({ page }) => {
    await mockMasterDataRoutes(page)
    await page.goto(REGISTER_PATH)

    await page.getByTestId('register-tenant-slug').fill(VALID_REGISTRATION.tenantSlug)
    await waitForSelectOption(page, 'register-target-country', 'Canada')
    await page.getByTestId('register-target-country').selectOption(VALID_REGISTRATION.countryId)
    await waitForSelectOption(page, 'register-target-university', 'University of Toronto')
    await page.getByTestId('register-target-university').selectOption(VALID_REGISTRATION.universityId)
    await waitForSelectOption(page, 'register-target-program', 'Computer Science MSc')
    await page.getByTestId('register-target-program').selectOption(VALID_REGISTRATION.programId)

    await page.getByTestId('register-target-country').selectOption('')

    await expect(page.getByTestId('register-target-university')).toHaveValue('')
    await expect(page.getByTestId('register-target-program')).toHaveValue('')
  })
})
