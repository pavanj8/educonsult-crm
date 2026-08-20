import type { Page, Route } from '@playwright/test'

import { expect, test } from './fixtures.js'
import { DEMO_USER, mockAuthMe } from './helpers/auth.js'
import { gotoPath } from './helpers/navigation.js'

const mockApplications = [
  {
    id: 1,
    tenant_id: 10,
    student_id: 42,
    university_id: 1,
    program_id: 10,
    stage: 'registered',
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 2,
    tenant_id: 10,
    student_id: 42,
    university_id: 2,
    program_id: 20,
    stage: 'counseling',
    created_at: '2026-01-20T10:00:00Z',
    updated_at: '2026-01-21T10:00:00Z',
  },
]

async function mockApplicationsApi(page: Page, applications = mockApplications): Promise<void> {
  await page.route('**/applications', async (route: Route) => {
    if (route.request().resourceType() === 'document') {
      await route.continue()
      return
    }

    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(applications),
      })
      return
    }

    await route.continue()
  })
}

test.describe('Student applications list', () => {
  test('student sees dashboard nav link and applications list', async ({ studentPage, page }) => {
    void studentPage
    await mockApplicationsApi(page)

    await gotoPath(page, '/dashboard')

    await expect(page.getByTestId('nav-dashboard')).toBeVisible()
    await expect(page.getByTestId('student-dashboard-page')).toBeVisible()
    await expect(page.getByTestId('application-table')).toBeVisible()
    await expect(page.getByText('University of Toronto')).toBeVisible()
    await expect(page.getByText('MSc Computer Science')).toBeVisible()
    await expect(page.getByText('University of Melbourne')).toBeVisible()
    await expect(page.getByTestId('application-stage-1')).toHaveText('Registered')
    await expect(page.getByTestId('application-stage-2')).toHaveText('Counseling')
  })

  test('student sees empty state when no applications exist', async ({ studentPage, page }) => {
    void studentPage
    await mockApplicationsApi(page, [])

    await gotoPath(page, '/dashboard')

    await expect(page.getByText('No applications yet.')).toBeVisible()
    await expect(page.getByTestId('application-table')).not.toBeVisible()
  })

  test('non-student user is denied access to student dashboard', async ({ page }) => {
    await mockAuthMe(page, DEMO_USER)
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-counselor')
      localStorage.setItem('refresh_token', 'refresh-counselor')
    })

    await gotoPath(page, '/dashboard')

    await expect(page.getByTestId('access-denied')).toBeVisible()
    await expect(page.getByTestId('student-dashboard-page')).not.toBeVisible()
    await expect(page.getByTestId('nav-dashboard')).not.toBeVisible()
  })
})
