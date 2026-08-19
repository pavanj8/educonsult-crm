import { test as base } from '@playwright/test'

import { gotoHome } from './helpers/navigation.js'

type AppFixtures = {
  homePage: void
}

export const test = base.extend<AppFixtures>({
  homePage: async ({ page }, use) => {
    await gotoHome(page)
    await use()
  },
})

export { expect } from '@playwright/test'
