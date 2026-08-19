import type { Page } from '@playwright/test'

/** Example login form path on the Vite dev-server origin (E5 adds /login). */
export const LOGIN_FORM_PATH = '/e2e/login-form.html'

export async function gotoHome(page: Page): Promise<void> {
  await page.goto('/')
}

export async function gotoPath(page: Page, path: string): Promise<void> {
  await page.goto(path)
}

/** Open the example login form fixture (real /login UI is wired in E5). */
export async function gotoLoginForm(page: Page): Promise<void> {
  await page.goto(LOGIN_FORM_PATH)
}
