import type { Page } from '@playwright/test'

export async function gotoHome(page: Page): Promise<void> {
  await page.goto('/')
}

export async function gotoPath(page: Page, path: string): Promise<void> {
  await page.goto(path)
}
