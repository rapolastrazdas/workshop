import { test, expect, type Page } from '@playwright/test'

const password = 'PatikimasSlaptazodis9!'
const email = () => `ni01-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`

async function register(page: Page, address: string) {
  await page.goto('/registracija')
  await page.getByLabel('El. paštas', { exact: true }).fill(address)
  await page.getByLabel('Slaptažodis', { exact: true }).fill(password)
  await page.getByLabel('Pakartokite slaptažodį', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Registruotis', exact: true }).click()
  await expect(page).toHaveURL(/\/mano-kalades$/)
}

test('registration, reload, logout and login', async ({ page }) => {
  const address = email()
  await page.goto('/')
  await expect(page.getByRole('link', { name: 'Registruotis', exact: true })).toBeVisible()
  await register(page, address)
  await expect(page.getByRole('heading', { name: 'Mano kaladės' })).toBeVisible()
  await expect(page.getByText(address, { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Šalinti paskyrą' })).toBeDisabled()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Atsijungti', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Atsijungti', exact: true }).click()
  await expect(page).toHaveURL(/\/$/)
  expect(await page.evaluate(() => sessionStorage.getItem('workshop.session'))).toBeNull()
  await page.goto('/mano-kalades')
  await expect(page).toHaveURL(/\/prisijungimas$/)
  await page.getByLabel('El. paštas', { exact: true }).fill(address)
  await page.getByLabel('Slaptažodis', { exact: true }).fill('wrong-password')
  await page.getByRole('button', { name: 'Prisijungti', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Neteisingas el. pašto adresas arba slaptažodis.')
  await page.getByLabel('Slaptažodis', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Prisijungti', exact: true }).click()
  await expect(page).toHaveURL(/\/mano-kalades$/)
})

test('field validation and duplicate email', async ({ page }) => {
  const address = email()
  await page.goto('/registracija')
  await page.getByLabel('El. paštas', { exact: true }).fill('invalid')
  await page.getByLabel('Slaptažodis', { exact: true }).fill('12345678')
  await page.getByLabel('Pakartokite slaptažodį', { exact: true }).fill('different')
  await page.getByRole('button', { name: 'Registruotis', exact: true }).click()
  await expect(page.locator('#email-error')).toBeVisible()
  await expect(page.locator('#password-error')).toBeVisible()
  await expect(page.locator('#confirmation-error')).toBeVisible()
  await register(page, address)
  await page.getByRole('button', { name: 'Atsijungti', exact: true }).click()
  await expect(page).toHaveURL(/\/$/)
  await page.goto('/registracija')
  await page.getByLabel('El. paštas', { exact: true }).fill(address)
  await page.getByLabel('Slaptažodis', { exact: true }).fill(password)
  await page.getByLabel('Pakartokite slaptažodį', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Registruotis', exact: true }).click()
  await expect(page.locator('#email-error')).toHaveText('Šis el. paštas jau užregistruotas.')
})

test('guest deck URLs require sign-in', async ({ page }) => {
  for (const url of ['/mano-kalades', '/kalades/123', '/decks', '/decks/123']) {
    await page.goto(url)
    await expect(page).toHaveURL(/\/prisijungimas$/)
    await expect(page.getByRole('heading', { name: 'Prisijungimas' })).toBeVisible()
  }
})

test('expired session on opening the home page', async ({ page }) => {
  await register(page, email())
  await page.evaluate(() => {
    const session = JSON.parse(sessionStorage.getItem('workshop.session')!)
    session.expires_at = Math.floor(Date.now() / 1000) - 1
    sessionStorage.setItem('workshop.session', JSON.stringify(session))
  })
  await page.goto('/')
  await expect(page).toHaveURL(/\/prisijungimas$/)
  await expect(page.getByRole('alert')).toContainText('Jūsų sesija baigėsi. Prisijunkite iš naujo.')
  expect(await page.evaluate(() => sessionStorage.getItem('workshop.session'))).toBeNull()
})

test('session expires while page stays open', async ({ page }) => {
  await register(page, email())
  await page.evaluate(() => {
    const session = JSON.parse(sessionStorage.getItem('workshop.session')!)
    session.expires_at = Math.floor(Date.now() / 1000) + 2
    sessionStorage.setItem('workshop.session', JSON.stringify(session))
  })
  await page.reload()
  await expect(page).toHaveURL(/\/prisijungimas$/, { timeout: 7000 })
  await expect(page.getByRole('alert')).toContainText('Jūsų sesija baigėsi.')
})

test('server-revoked session redirects', async ({ page }) => {
  await register(page, email())
  const token = await page.evaluate(() => JSON.parse(sessionStorage.getItem('workshop.session')!).access_token)
  expect((await page.request.post('/api/auth/logout', { headers: { Authorization: `Bearer ${token}` } })).status()).toBe(204)
  await page.goto('/kalades/123')
  await expect(page).toHaveURL(/\/prisijungimas$/)
  await expect(page.getByRole('alert')).toContainText('Jūsų sesija baigėsi.')
})

test('registration fits a phone screen', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/registracija')
  await expect(page.getByRole('button', { name: 'Registruotis', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})
