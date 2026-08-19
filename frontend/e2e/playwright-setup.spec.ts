import { expect, test } from './fixtures.js'
import { makeAuthHeaders } from './helpers/auth.js'
import { gotoHome } from './helpers/navigation.js'

test.describe('Playwright base setup', () => {
  test('makeAuthHeaders returns bearer format', () => {
    expect(makeAuthHeaders('my-token')).toEqual({
      Authorization: 'Bearer my-token',
    })
  })

  test('homePage fixture loads the app shell', async ({ page, homePage }) => {
    void homePage

    await expect(page).toHaveTitle('EduConsult CRM')
    await expect(page.getByRole('heading', { name: 'EduConsult CRM' })).toBeVisible()
    await expect(page.getByText('Welcome to EduConsult CRM')).toBeVisible()
  })

  test('gotoHome helper navigates to the home route', async ({ page }) => {
    await gotoHome(page)

    await expect(page).toHaveURL('/')
    await expect(page.getByText('Welcome to EduConsult CRM')).toBeVisible()
  })
})
