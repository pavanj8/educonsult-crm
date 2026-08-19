import type { Page, Route } from '@playwright/test'

import { expect, test } from './fixtures.js'
import { DEMO_USER, mockAuthMe } from './helpers/auth.js'
import { gotoPath } from './helpers/navigation.js'

const mockBranches = [
  {
    id: 1,
    tenant_id: 10,
    name: 'Mumbai HQ',
    city: 'Mumbai',
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 2,
    tenant_id: 10,
    name: 'Delhi Center',
    city: 'Delhi',
    created_at: '2026-01-20T10:00:00Z',
    updated_at: '2026-01-20T10:00:00Z',
  },
]

const mockStaffList = [
  {
    id: 5,
    email: 'existing.counselor@example.test',
    role: 'counselor',
    tenant_id: 10,
    branch_id: 1,
    created_at: '2026-01-10T10:00:00Z',
    updated_at: '2026-01-10T10:00:00Z',
  },
]

async function mockStaffApi(page: Page): Promise<void> {
  await page.route('**/staff**', async (route: Route) => {
    if (route.request().resourceType() === 'document') {
      await route.continue()
      return
    }

    const url = route.request().url()
    const method = route.request().method()

    if (method === 'GET' && /\/staff\/\d+$/.test(url)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStaffList[0]),
      })
      return
    }

    if (method === 'GET' && url.endsWith('/staff')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStaffList),
      })
      return
    }

    if (method === 'POST' && url.endsWith('/staff')) {
      const body = route.request().postDataJSON() as {
        email: string
        password: string
        role: string
        branch_id: number
      }
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 42,
          email: body.email,
          role: body.role,
          tenant_id: 10,
          branch_id: body.branch_id,
          created_at: '2026-02-01T10:00:00Z',
          updated_at: '2026-02-01T10:00:00Z',
        }),
      })
      return
    }

    if (method === 'PATCH' && /\/staff\/\d+$/.test(url)) {
      const body = route.request().postDataJSON() as {
        role: string
        branch_id: number
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...mockStaffList[0],
          role: body.role,
          branch_id: body.branch_id,
        }),
      })
      return
    }

    await route.continue()
  })
}

async function mockBranchesApi(page: Page, branches = mockBranches): Promise<void> {
  await page.route('**/branches', async (route: Route) => {
    if (route.request().resourceType() === 'document') {
      await route.continue()
      return
    }

    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(branches),
      })
      return
    }

    await route.continue()
  })
}

test.describe('Staff account creation', () => {
  test('consultancy owner sees staff nav link and create form', async ({
    consultancyOwnerPage,
    page,
  }) => {
    void consultancyOwnerPage
    await mockStaffApi(page)
    await mockBranchesApi(page)

    await gotoPath(page, '/staff')

    await expect(page.getByTestId('nav-staff')).toBeVisible()
    await expect(page.getByTestId('staff-page')).toBeVisible()
    await expect(page.getByTestId('staff-branch')).toBeVisible()
    await expect(page.getByTestId('staff-role')).toContainText('Branch Manager')
  })

  test('consultancy owner can create staff for selected branch', async ({
    consultancyOwnerPage,
    page,
  }) => {
    void consultancyOwnerPage
    await mockStaffApi(page)
    await mockBranchesApi(page)

    await gotoPath(page, '/staff')

    const createRequest = page.waitForRequest(
      (request) =>
        request.method() === 'POST' &&
        request.url().includes('/staff') &&
        !request.url().match(/\/staff\/\d+$/),
    )

    await page.getByTestId('staff-email').fill('new.counselor@example.test')
    await page.getByTestId('staff-password').fill('secure-password')
    await page.getByTestId('staff-role').selectOption('counselor')
    await page.getByTestId('staff-branch').selectOption('2')
    await page.getByTestId('staff-create-submit').click()

    const request = await createRequest
    expect(request.postDataJSON()).toMatchObject({
      email: 'new.counselor@example.test',
      role: 'counselor',
      branch_id: 2,
    })

    await expect(page.getByTestId('staff-create-success')).toBeVisible()
    await expect(page.getByTestId('staff-create-success')).toContainText(
      'new.counselor@example.test',
    )
  })

  test('consultancy owner can edit staff role and branch', async ({
    consultancyOwnerPage,
    page,
  }) => {
    void consultancyOwnerPage
    await mockStaffApi(page)
    await mockBranchesApi(page)

    await gotoPath(page, '/staff')

    await page.getByTestId('staff-edit-5').click()
    await expect(page.getByTestId('staff-edit-email')).toHaveValue(
      'existing.counselor@example.test',
    )

    const updateRequest = page.waitForRequest(
      (request) => request.method() === 'PATCH' && request.url().includes('/staff/5'),
    )

    await page.getByTestId('staff-edit-role').selectOption('receptionist')
    await page.getByTestId('staff-edit-branch').selectOption('2')
    await page.getByTestId('staff-edit-submit').click()

    const request = await updateRequest
    expect(request.postDataJSON()).toMatchObject({
      role: 'receptionist',
      branch_id: 2,
    })

    await expect(page.getByTestId('staff-row-5')).toContainText('Receptionist')
    await expect(page.getByTestId('staff-row-5')).toContainText('Delhi Center')
  })

  test('branch manager sees staff form without branch selector', async ({
    branchManagerPage,
    page,
  }) => {
    void branchManagerPage
    await mockStaffApi(page)

    await gotoPath(page, '/staff')

    await expect(page.getByTestId('nav-staff')).toBeVisible()
    await expect(page.getByTestId('staff-branch-readonly')).toBeVisible()
    await expect(page.getByTestId('staff-branch-readonly')).toContainText('your branch')
    await expect(page.getByTestId('staff-branch')).not.toBeVisible()
    await expect(page.getByTestId('staff-role')).not.toContainText('Branch Manager')
  })

  test('branch manager can create staff in own branch', async ({ branchManagerPage, page }) => {
    void branchManagerPage
    await mockStaffApi(page)

    await gotoPath(page, '/staff')

    await page.getByTestId('staff-email').fill('receptionist@example.test')
    await page.getByTestId('staff-password').fill('secure-password')
    await page.getByTestId('staff-role').selectOption('receptionist')
    await page.getByTestId('staff-create-submit').click()

    await expect(page.getByTestId('staff-create-success')).toBeVisible()
    await expect(page.getByTestId('staff-create-success')).toContainText(
      'receptionist@example.test',
    )
  })

  test('non-manager user is denied access to staff page', async ({ page }) => {
    await mockAuthMe(page, DEMO_USER)
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-counselor')
      localStorage.setItem('refresh_token', 'refresh-counselor')
    })

    await gotoPath(page, '/staff')

    await expect(page.getByTestId('access-denied')).toBeVisible()
    await expect(page.getByTestId('staff-page')).not.toBeVisible()
    await expect(page.getByTestId('nav-staff')).not.toBeVisible()
  })
})
