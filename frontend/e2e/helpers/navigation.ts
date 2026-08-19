import type { Page } from '@playwright/test'

import { LOGIN_PATH } from './auth.js'

/** Login page path on the Vite dev-server origin. */
export const LOGIN_FORM_PATH = LOGIN_PATH

export async function gotoHome(page: Page): Promise<void> {
  await page.goto('/')
}

export async function gotoPath(page: Page, path: string): Promise<void> {
  await page.goto(path)
}

/** Open the login page. */
export async function gotoLoginForm(page: Page): Promise<void> {
  await page.goto(LOGIN_FORM_PATH)
}
