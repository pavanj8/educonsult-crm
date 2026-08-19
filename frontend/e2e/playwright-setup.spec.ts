import { expect, test } from './fixtures.js'
import { makeAuthHeaders } from './helpers/auth.js'
import { gotoHome, LOGIN_PATH } from './helpers/navigation.js'

test.describe('Playwright base setup', () => {
  test('makeAuthHeaders returns bearer format', () => {
    expect(makeAuthHeaders('my-token')).toEqual({
      Authorization: 'Bearer my-token',
    })
  })

  test('homePage fixture redirects unauthenticated users to login', async ({ page, homePage }) => {
    void homePage

    await expect(page).toHaveURL(LOGIN_PATH)
  })

  test('gotoHome helper redirects unauthenticated users to login', async ({ page }) => {
    await gotoHome(page)

    await expect(page).toHaveURL(LOGIN_PATH)
  })
})
