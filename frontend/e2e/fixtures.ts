import { test as base } from '@playwright/test'

import {
  accessTokenForRole,
  loginTokensForRole,
  mockLoginApi,
  setAuthSession,
  type UserRole,
} from './helpers/auth.js'
import { gotoHome, gotoLoginForm } from './helpers/navigation.js'

type AppFixtures = {
  homePage: void
  loginPage: void
  authenticatedPage: void
  counselorPage: void
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
})

export type { UserRole }

export { expect } from '@playwright/test'
