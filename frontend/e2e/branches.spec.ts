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

    const method = route.request().method()

    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(branches),
      })
      return
    }

    if (method === 'POST') {
      const body = route.request().postDataJSON() as { name: string; city: string }
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: branches.length + 1,
          tenant_id: 10,
          name: body.name,
          city: body.city,
          created_at: '2026-02-01T10:00:00Z',
          updated_at: '2026-02-01T10:00:00Z',
        }),
      })
      return
    }

    await route.continue()
  })

  await page.route('**/branches/*', async (route: Route) => {
    if (route.request().resourceType() === 'document') {
      await route.continue()
      return
    }

    if (route.request().method() === 'PATCH') {
      const url = route.request().url()
      const id = Number(url.split('/').pop())
      const body = route.request().postDataJSON() as { name?: string; city?: string }
      const existing = branches.find((branch) => branch.id === id) ?? branches[0]
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...existing,
          name: body.name ?? existing.name,
          city: body.city ?? existing.city,
          updated_at: '2026-02-02T10:00:00Z',
        }),
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

  test('consultancy owner can create a branch', async ({ consultancyOwnerPage, page }) => {
    void consultancyOwnerPage
    await mockBranchesApi(page, [])

    await gotoPath(page, '/branches')

    await expect(page.getByText('No branches yet.')).toBeVisible()

    await page.getByTestId('branch-name').fill('Bangalore Office')
    await page.getByTestId('branch-city').fill('Bangalore')
    await page.getByTestId('branch-create-submit').click()

    await expect(page.getByTestId('branch-create-success')).toBeVisible()
    await expect(page.getByRole('cell', { name: 'Bangalore Office' })).toBeVisible()
  })

  test('consultancy owner can edit a branch', async ({ consultancyOwnerPage, page }) => {
    void consultancyOwnerPage
    await mockBranchesApi(page)

    await gotoPath(page, '/branches')

    await page.getByTestId('branch-edit-1').click()
    await page.getByTestId('branch-edit-name').fill('Mumbai Main')
    await page.getByTestId('branch-edit-submit').click()

    await expect(page.getByRole('cell', { name: 'Mumbai Main' })).toBeVisible()
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
