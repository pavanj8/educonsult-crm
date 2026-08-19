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

test.describe('Consultancy owner branch management', () => {
  test('consultancy owner sees branches nav link and list', async ({ consultancyOwnerPage, page }) => {
    void consultancyOwnerPage
    await mockBranchesApi(page)

    await gotoPath(page, '/branches')

    await expect(page.getByTestId('nav-branches')).toBeVisible()
    await expect(page.getByTestId('branches-page')).toBeVisible()
    await expect(page.getByTestId('branch-table')).toBeVisible()
    await expect(page.getByText('Mumbai HQ')).toBeVisible()
    await expect(page.getByText('Delhi Center')).toBeVisible()
  })

  test('consultancy owner sees empty state when no branches exist', async ({
    consultancyOwnerPage,
    page,
  }) => {
    void consultancyOwnerPage
    await mockBranchesApi(page, [])

    await gotoPath(page, '/branches')

    await expect(page.getByText('No branches yet.')).toBeVisible()
  })

  test('non-owner user is denied access to branches page', async ({ page }) => {
    await mockAuthMe(page, DEMO_USER)
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-counselor')
      localStorage.setItem('refresh_token', 'refresh-counselor')
    })

    await gotoPath(page, '/branches')

    await expect(page.getByTestId('access-denied')).toBeVisible()
    await expect(page.getByTestId('branches-page')).not.toBeVisible()
    await expect(page.getByTestId('nav-branches')).not.toBeVisible()
  })
})
