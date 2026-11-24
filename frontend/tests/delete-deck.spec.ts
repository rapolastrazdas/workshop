import { test, expect, type Page } from '@playwright/test'

const name = 'Hues & Clues'
const mismatch = 'Įvestas pavadinimas nesutampa su kaladės pavadinimu.'

async function openDeck(page: Page) {
  await page.goto('/registracija')
  await page.getByLabel('El. paštas', { exact: true }).fill(`ni07-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`)
  await page.getByLabel('Slaptažodis', { exact: true }).fill('Password123!')
  await page.getByLabel('Pakartokite slaptažodį').fill('Password123!')
  await page.getByRole('button', { name: 'Registruotis', exact: true }).click()
  await expect(page).toHaveURL(/\/mano-kalades$/)
  await page.getByRole('button', { name: '+ Nauja kaladė', exact: true }).click()
  const creation = page.getByRole('dialog', { name: 'Nauja kaladė', exact: true })
  await creation.getByLabel('Pavadinimas (nebūtinas)', { exact: true }).fill(name)
  await creation.getByRole('button', { name: 'Sukurti', exact: true }).click()
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
}

async function openDelete(page: Page) {
  await page.getByRole('button', { name: 'Nustatymai', exact: true }).click()
  await page.getByRole('dialog', { name: 'Kaladės nustatymai', exact: true }).getByRole('button', { name: 'Ištrinti kaladę', exact: true }).click()
  return page.getByRole('dialog', { name: 'Ištrinti kaladę?', exact: true })
}

test('exact name is required and successful deletion returns to the updated list', async ({ page }) => {
  await openDeck(page)
  const oldUrl = page.url()
  let writes = 0
  page.on('request', (request) => { if (request.method() === 'DELETE') writes++ })
  const dialog = await openDelete(page)
  const input = dialog.getByLabel('Kaladės pavadinimas', { exact: true })
  const confirm = dialog.getByRole('button', { name: 'Ištrinti', exact: true })
  await expect(input).toBeFocused()
  await expect(confirm).toBeDisabled()
  await input.fill('Hues & Clue')
  await expect(dialog.getByRole('alert')).toHaveText(mismatch)
  await expect(confirm).toBeDisabled()
  await input.press('Enter')
  expect(writes).toBe(0)
  await input.fill(name.toLowerCase())
  await expect(confirm).toBeDisabled()
  await input.fill(name)
  await expect(dialog.getByRole('alert')).toHaveCount(0)
  await expect(confirm).toBeEnabled()
  await confirm.click()
  await expect(page).toHaveURL(/\/mano-kalades$/)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByTestId('deck-count')).toHaveText('0 kaladžių')
  await expect(page.getByRole('alert')).toContainText('Kaladė ištrinta.')
  await expect(page.getByRole('button', { name: 'Atsijungti', exact: true })).toBeVisible()
  await page.goto(oldUrl)
  await expect(page.getByRole('heading', { name: 'Kaladė nerasta', exact: true })).toBeVisible()
})

test('cancel, close and Escape preserve the deck and unsaved settings', async ({ page }) => {
  await openDeck(page)
  await page.getByRole('button', { name: 'Nustatymai', exact: true }).click()
  const settings = page.getByRole('dialog', { name: 'Kaladės nustatymai', exact: true })
  await settings.getByLabel('Pavadinimas', { exact: true }).fill('Unsaved name')
  await settings.getByLabel('Kortų importas (nebūtinas)', { exact: true }).fill('Unknown Card')
  for (const action of ['Atšaukti', 'Uždaryti', 'Escape']) {
    await settings.getByRole('button', { name: 'Ištrinti kaladę', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Ištrinti kaladę?', exact: true })
    await expect(dialog.getByText(name, { exact: true })).toBeVisible()
    await dialog.getByLabel('Kaladės pavadinimas', { exact: true }).fill('Unsaved name')
    await expect(dialog.getByRole('button', { name: 'Ištrinti', exact: true })).toBeDisabled()
    if (action === 'Escape') await page.keyboard.press('Escape')
    else await dialog.getByRole('button', { name: action, exact: true }).click()
    await expect(dialog).toHaveCount(0)
    await expect(settings).toBeVisible()
    await expect(settings.getByLabel('Pavadinimas', { exact: true })).toHaveValue('Unsaved name')
    await expect(settings.getByLabel('Kortų importas (nebūtinas)', { exact: true })).toHaveValue('Unknown Card')
  }
  await settings.getByRole('button', { name: 'Atšaukti', exact: true }).click()
  await page.reload()
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
})

test('failed deletion can be retried without losing the deck', async ({ page }) => {
  await openDeck(page)
  let failed = false
  await page.route('**/api/decks/*', (route) => {
    if (route.request().method() === 'DELETE' && !failed) {
      failed = true
      return route.fulfill({ status: 503, json: { detail: 'Nepavyko ištrinti kaladės. Bandykite dar kartą.' } })
    }
    return route.continue()
  })
  const dialog = await openDelete(page)
  await dialog.getByLabel('Kaladės pavadinimas', { exact: true }).fill(name)
  await dialog.getByRole('button', { name: 'Ištrinti', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('Nepavyko ištrinti kaladės.')
  await expect(dialog.getByLabel('Kaladės pavadinimas', { exact: true })).toHaveValue(name)
  await dialog.getByRole('button', { name: 'Ištrinti', exact: true }).click()
  await expect(page).toHaveURL(/\/mano-kalades$/)
  await expect(page.getByTestId('deck-count')).toHaveText('0 kaladžių')
})

test('session expiration closes both settings and deletion dialogs', async ({ page }) => {
  await openDeck(page)
  await page.evaluate(() => {
    const session = JSON.parse(sessionStorage.getItem('workshop.session')!)
    session.expires_at = Math.floor(Date.now() / 1000) + 4
    sessionStorage.setItem('workshop.session', JSON.stringify(session))
  })
  await page.reload()
  const dialog = await openDelete(page)
  await expect(dialog).toBeVisible()
  await expect(page).toHaveURL(/\/prisijungimas$/, { timeout: 8000 })
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('alert')).toContainText('Jūsų sesija baigėsi.')
})
