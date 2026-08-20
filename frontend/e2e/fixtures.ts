import { test as base } from '@playwright/test'

import {
  accessTokenForRole,
  BRANCH_MANAGER_USER,
  CONSULTANCY_OWNER_USER,
  loginTokensForRole,
  mockAuthMe,
  mockLoginApi,
  setAuthSession,
  SUPER_ADMIN_USER,
  type UserRole,
} from './helpers/auth.js'
import { gotoHome, gotoLoginForm } from './helpers/navigation.js'

type AppFixtures = {
  homePage: void
  loginPage: void
  authenticatedPage: void
  counselorPage: void
  superAdminPage: void
  consultancyOwnerPage: void
  branchManagerPage: void
}

export const test = base.extend<AppFixtures>({
  homePage: async ({ page }, use) => {
    await gotoHome(page)
    await use()
  },

  loginPage: async ({ page }, use) => {
    await mockLoginApi(page)
    await gotoLoginForm(page)
    await use()
  },

  authenticatedPage: async ({ page }, use) => {
    await mockAuthMe(page)
    await setAuthSession(page, accessTokenForRole('counselor'))
    await gotoHome(page)
    await use()
  },

  counselorPage: async ({ page }, use) => {
    const tokens = loginTokensForRole('counselor')
    await mockLoginApi(page, tokens)
    await gotoLoginForm(page)
    await use()
  },

  superAdminPage: async ({ page }, use) => {
    await mockAuthMe(page, SUPER_ADMIN_USER)
    await setAuthSession(page, accessTokenForRole('super_admin'))
    await gotoHome(page)
    await use()
  },

  consultancyOwnerPage: async ({ page }, use) => {
    await mockAuthMe(page, CONSULTANCY_OWNER_USER)
    await setAuthSession(page, accessTokenForRole('consultancy_owner'))
    await gotoHome(page)
    await use()
  },

  branchManagerPage: async ({ page }, use) => {
    await mockAuthMe(page, BRANCH_MANAGER_USER)
    await setAuthSession(page, accessTokenForRole('branch_manager'))
    await gotoHome(page)
    await use()
  },
})

export type { UserRole }

export { expect } from '@playwright/test'
