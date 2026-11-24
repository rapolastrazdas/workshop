import { test, expect, type Page } from '@playwright/test'

const password = 'PatikimasSlaptazodis9!'
const email = () => `ni02-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`

async function register(page: Page, address: string) {
  await page.goto('/registracija')
  await page.getByLabel('El. paštas', { exact: true }).fill(address)
  await page.getByLabel('Slaptažodis', { exact: true }).fill(password)
  await page.getByLabel('Pakartokite slaptažodį').fill(password)
  await page.getByRole('button', { name: 'Registruotis', exact: true }).click()
  await expect(page).toHaveURL(/\/mano-kalades$/)
}

test('deletion confirms password, handles errors, removes account and signs out', async ({ page }) => {
  const address = email()
  await register(page, address)
  const oldToken = await page.evaluate(() => JSON.parse(sessionStorage.getItem('workshop.session')!).access_token)
  const secondSession = await page.request.post('/api/auth/login', { data: { email: address, password } })
  const secondToken = (await secondSession.json()).access_token
  await page.getByRole('button', { name: 'Šalinti paskyrą', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Šalinti paskyrą' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByLabel('Slaptažodis', { exact: true })).toBeFocused()
  await dialog.getByRole('button', { name: 'Šalinti paskyrą', exact: true }).click()
  await expect(dialog.getByRole('alert')).toHaveText('Įveskite slaptažodį.')
  await dialog.getByLabel('Slaptažodis', { exact: true }).fill('wrong-password')
  await dialog.getByRole('button', { name: 'Šalinti paskyrą', exact: true }).click()
  await expect(dialog.getByRole('alert')).toHaveText('Neteisingas slaptažodis.')
  expect((await page.request.get('/api/auth/me', { headers: { Authorization: `Bearer ${oldToken}` } })).status()).toBe(200)
  await dialog.getByLabel('Slaptažodis', { exact: true }).fill(password)
  await dialog.getByRole('button', { name: 'Šalinti paskyrą', exact: true }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('alert')).toHaveText('Paskyra ištrinta.')
  await expect(page.getByRole('link', { name: 'Prisijungti', exact: true })).toBeVisible()
  expect(await page.evaluate(() => sessionStorage.getItem('workshop.session'))).toBeNull()
  for (const token of [oldToken, secondToken]) {
    expect((await page.request.get('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })).status()).toBe(401)
  }
  const login = await page.request.post('/api/auth/login', { data: { email: address, password } })
  expect(login.status()).toBe(401)
  await page.goto('/mano-kalades')
  await expect(page).toHaveURL(/\/prisijungimas$/)
})

test('cancel, close button and Escape keep account and clear password', async ({ page }) => {
  await register(page, email())
  const trigger = page.getByRole('button', { name: 'Šalinti paskyrą', exact: true })
  await trigger.click()
  let dialog = page.getByRole('dialog')
  await dialog.getByLabel('Slaptažodis', { exact: true }).fill(password)
  await dialog.getByRole('button', { name: 'Atšaukti' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(trigger).toBeFocused()
  await trigger.click()
  dialog = page.getByRole('dialog')
  await expect(dialog.getByLabel('Slaptažodis', { exact: true })).toHaveValue('')
  await dialog.getByRole('button', { name: 'Uždaryti', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(trigger).toBeFocused()
  await trigger.click()
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(page).toHaveURL(/\/mano-kalades$/)
  await expect(page.getByRole('button', { name: 'Atsijungti', exact: true })).toBeVisible()
})

test('session expiring during confirmation closes the dialog', async ({ page }) => {
  await register(page, email())
  await page.evaluate(() => {
    const session = JSON.parse(sessionStorage.getItem('workshop.session')!)
    session.expires_at = Math.floor(Date.now() / 1000) + 3
    sessionStorage.setItem('workshop.session', JSON.stringify(session))
  })
  await page.reload()
  await page.getByRole('button', { name: 'Šalinti paskyrą', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page).toHaveURL(/\/prisijungimas$/, { timeout: 7000 })
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('alert')).toContainText('Jūsų sesija baigėsi.')
})
