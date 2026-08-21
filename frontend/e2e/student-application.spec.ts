import type { Page } from '@playwright/test'

import { expect, test } from './fixtures.js'
import {
  STUDENT_USER,
  accessTokenForRole,
  loginTokensForRole,
  mockAuthMe,
  setAuthSession,
} from './helpers/auth.js'
import { gotoPath } from './helpers/navigation.js'
import { STUDENT_DASHBOARD_PATH } from '../src/routes/paths.js'

const mockCreatedApplication = {
  id: 1,
  tenant_id: 10,
  student_id: 8,
  university_id: 1,
  program_id: 10,
  stage: 'registered',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

async function mockApplicationsApi(page: Page): Promise<void> {
  await page.route('**/applications', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue()
      return
    }

    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify(mockCreatedApplication),
    })
  })
}

async function setupStudentSession(page: Page): Promise<void> {
  await setAuthSession(page, accessTokenForRole('student'), loginTokensForRole('student').refresh_token)
  await mockAuthMe(page, STUDENT_USER)
  await mockApplicationsApi(page)
}

test.describe('Student new application form', () => {
  test('student dashboard exposes the application form selector contract', async ({ page }) => {
    await setupStudentSession(page)
    await gotoPath(page, STUDENT_DASHBOARD_PATH)

    await expect(page.getByTestId('student-dashboard-page')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Student dashboard' })).toBeVisible()
    await expect(page.getByTestId('application-university')).toBeVisible()
    await expect(page.getByTestId('application-program')).toBeVisible()
    await expect(page.getByTestId('application-submit')).toBeVisible()
    await expect(page.getByTestId('nav-dashboard')).toBeVisible()
  })

  test('student can create an application via mocked POST /applications', async ({ page }) => {
    await setupStudentSession(page)
    await gotoPath(page, STUDENT_DASHBOARD_PATH)

    await page.getByTestId('application-university').selectOption('1')
    await page.getByTestId('application-program').selectOption('10')
    await page.getByTestId('application-submit').click()

    await expect(page.getByTestId('application-success')).toContainText(
      'Application created for MSc Computer Science at University of Toronto',
    )
  })
})
