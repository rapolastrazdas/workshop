import { test, expect, type Page } from '@playwright/test'

async function register(page: Page) {
  await page.goto('/registracija')
  await page.getByLabel('El. paštas', { exact: true }).fill(`notices-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`)
  await page.getByLabel('Slaptažodis', { exact: true }).fill('Password123!')
  await page.getByLabel('Pakartokite slaptažodį').fill('Password123!')
  await page.getByRole('button', { name: 'Registruotis', exact: true }).click()
  await expect(page).toHaveURL(/\/mano-kalades$/)
}

async function createWithImport(page: Page) {
  await page.getByRole('button', { name: '+ Nauja kaladė', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Nauja kaladė', exact: true })
  await dialog.getByLabel('Kortų sąrašas (nebūtinas)', { exact: true }).fill(`UnknownNoticeCard-${Date.now()}`)
  await dialog.getByRole('button', { name: 'Sukurti', exact: true }).click()
  await expect(page).toHaveURL(/\/kalades\/\d+$/)
  await page.getByRole('dialog', { name: 'Importo rezultatas', exact: true }).getByRole('button', { name: 'Praleisti', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Importuotų kortų: 0.')
}

test('import notice survives destination navigation but clears on leaving and logout', async ({ page }) => {
  await register(page)
  await createWithImport(page)
  const editorUrl = page.url()
  await page.getByRole('link', { name: 'Mano kaladės', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await page.goBack()
  await expect(page).toHaveURL(editorUrl)
  await expect(page.getByRole('alert')).toHaveCount(0)
  await page.getByRole('button', { name: 'Atsijungti', exact: true }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('import notice disappears automatically after five seconds', async ({ page }) => {
  await page.clock.install()
  await register(page)
  await createWithImport(page)
  await page.clock.fastForward(5001)
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('notice can be dismissed manually', async ({ page }) => {
  await register(page)
  await createWithImport(page)
  await page.getByRole('button', { name: 'Uždaryti pranešimą', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('account deletion notice clears on navigation and does not return', async ({ page }) => {
  await register(page)
  await page.getByRole('button', { name: 'Šalinti paskyrą', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Šalinti paskyrą?' })
  await dialog.getByLabel('Slaptažodis', { exact: true }).fill('Password123!')
  await dialog.getByRole('button', { name: 'Šalinti paskyrą', exact: true }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('alert')).toContainText('Paskyra ištrinta.')
  await page.getByRole('link', { name: 'Prisijungti', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await page.getByRole('link', { name: "Urza's Workshop", exact: true }).click()
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('global logout error clears when leaving its page', async ({ page }) => {
  await register(page)
  await createWithImport(page)
  await page.route('**/api/auth/logout', (route) => route.fulfill({ status: 503, json: { detail: 'Nepavyko atsijungti. Bandykite dar kartą.' } }))
  await page.getByRole('button', { name: 'Atsijungti', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Nepavyko atsijungti.')
  await page.getByRole('link', { name: 'Mano kaladės', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveCount(0)
})
