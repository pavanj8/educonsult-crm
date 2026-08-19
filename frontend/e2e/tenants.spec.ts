import type { Page, Route } from '@playwright/test'

import { expect, test } from './fixtures.js'
import { DEMO_USER, mockAuthMe, SUPER_ADMIN_USER } from './helpers/auth.js'
import { gotoPath } from './helpers/navigation.js'

const mockTenants = [
  {
    id: 1,
    name: 'Apex EduConsult',
    slug: 'apex',
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
]

async function mockTenantsApi(page: Page, tenants = mockTenants): Promise<void> {
  await page.route('**/tenants', async (route: Route) => {
    if (route.request().resourceType() === 'document') {
      await route.continue()
      return
    }

    const method = route.request().method()

    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(tenants),
      })
      return
    }

    if (method === 'POST') {
      const body = route.request().postDataJSON() as {
        name: string
        slug: string
        owner_email: string
      }
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: tenants.length + 1,
          name: body.name,
          slug: body.slug,
          created_at: '2026-02-01T10:00:00Z',
          updated_at: '2026-02-01T10:00:00Z',
        }),
      })
      return
    }

    await route.continue()
  })
}

test.describe('Super admin tenant management', () => {
  test('super admin sees tenants nav link and list', async ({ superAdminPage, page }) => {
    void superAdminPage
    await mockTenantsApi(page)

    await gotoPath(page, '/tenants')

    await expect(page.getByTestId('nav-tenants')).toBeVisible()
    await expect(page.getByTestId('tenants-page')).toBeVisible()
    await expect(page.getByTestId('tenant-table')).toBeVisible()
    await expect(page.getByText('Apex EduConsult')).toBeVisible()
  })

  test('super admin can create a tenant', async ({ superAdminPage, page }) => {
    void superAdminPage
    await mockTenantsApi(page, [])

    await gotoPath(page, '/tenants')

    await expect(page.getByText('No tenants yet.')).toBeVisible()

    await page.getByTestId('tenant-name').fill('Bright Future')
    await page.getByTestId('tenant-slug').fill('bright-future')
    await page.getByTestId('tenant-owner-email').fill('owner@bright.test')
    await page.getByTestId('tenant-create-submit').click()

    await expect(page.getByTestId('tenant-create-success')).toBeVisible()
    await expect(page.getByRole('cell', { name: 'Bright Future' })).toBeVisible()
  })

  test('non-super-admin user is denied access to tenants page', async ({ page }) => {
    await mockAuthMe(page, DEMO_USER)
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-counselor')
      localStorage.setItem('refresh_token', 'refresh-counselor')
    })

    await gotoPath(page, '/tenants')

    await expect(page.getByTestId('access-denied')).toBeVisible()
    await expect(page.getByTestId('tenants-page')).not.toBeVisible()
    await expect(page.getByTestId('nav-tenants')).not.toBeVisible()
  })
})
