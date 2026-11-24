import { test, expect, type Page } from '@playwright/test'

async function openDeck(page: Page) {
  await page.goto('/registracija')
  await page.getByLabel('El. paštas', { exact: true }).fill(`ni06-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`)
  await page.getByLabel('Slaptažodis', { exact: true }).fill('Password123!')
  await page.getByLabel('Pakartokite slaptažodį').fill('Password123!')
  await page.getByRole('button', { name: 'Registruotis', exact: true }).click()
  await expect(page).toHaveURL(/\/mano-kalades$/)
  await page.getByRole('button', { name: '+ Nauja kaladė', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Nauja kaladė', exact: true })
  await dialog.getByLabel('Pavadinimas (nebūtinas)', { exact: true }).fill('Original')
  await dialog.getByRole('button', { name: 'Sukurti', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Original', exact: true })).toBeVisible()
}

async function settings(page: Page) {
  await page.getByRole('button', { name: 'Nustatymai', exact: true }).click()
  return page.getByRole('dialog', { name: 'Kaladės nustatymai', exact: true })
}

test('current name is shown and a saved rename immediately updates editor and list', async ({ page }) => {
  await openDeck(page)
  const dialog = await settings(page)
  await expect(dialog.getByLabel('Pavadinimas', { exact: true })).toHaveValue('Original')
  await expect(dialog.getByLabel('Kortų importas (nebūtinas)', { exact: true })).toHaveValue('')
  await expect(dialog.getByLabel(/Formatas|Bracket/)).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: 'Ištrinti kaladę', exact: true })).toBeDisabled()
  await dialog.getByLabel('Pavadinimas', { exact: true }).fill('Atnaujinta kaladė')
  await dialog.getByRole('button', { name: 'Išsaugoti', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Atnaujinta kaladė', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Atnaujinta kaladė', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Mano kaladės', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Atnaujinta kaladė. Kortų: 0.', exact: true })).toBeVisible()
})

test('cancel, close and Escape discard changed name and import text', async ({ page }) => {
  await openDeck(page)
  for (const action of ['Atšaukti', 'Uždaryti', 'Escape']) {
    const dialog = await settings(page)
    await dialog.getByLabel('Pavadinimas', { exact: true }).fill('Discard this')
    await dialog.getByLabel('Kortų importas (nebūtinas)', { exact: true }).fill('Unknown Card')
    if (action === 'Escape') await page.keyboard.press('Escape')
    else await dialog.getByRole('button', { name: action, exact: true }).click()
    await expect(dialog).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Original', exact: true })).toBeVisible()
  }
  const dialog = await settings(page)
  await expect(dialog.getByLabel('Pavadinimas', { exact: true })).toHaveValue('Original')
  await expect(dialog.getByLabel('Kortų importas (nebūtinas)', { exact: true })).toHaveValue('')
})

test('blank and overlong names cannot be saved', async ({ page }) => {
  await openDeck(page)
  const dialog = await settings(page)
  for (const name of ['', 'ą'.repeat(101)]) {
    await dialog.getByLabel('Pavadinimas', { exact: true }).fill(name)
    await dialog.getByRole('button', { name: 'Išsaugoti', exact: true }).click()
    await expect(dialog.getByRole('alert')).toHaveText('Pavadinimą turi sudaryti nuo 1 iki 100 simbolių.')
    await expect(page.getByRole('heading', { name: 'Original', exact: true })).toBeVisible()
  }
})

test('rename with unknown import opens the existing import result dialog', async ({ page }) => {
  await openDeck(page)
  const dialog = await settings(page)
  await dialog.getByLabel('Pavadinimas', { exact: true }).fill('Importo nustatymai')
  await dialog.getByLabel('Kortų importas (nebūtinas)', { exact: true }).fill(`UnknownNI06-${Date.now()}`)
  await dialog.getByRole('button', { name: 'Išsaugoti', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  const report = page.getByRole('dialog', { name: 'Importo rezultatas', exact: true })
  await expect(report).toBeVisible()
  await report.getByRole('button', { name: 'Praleisti', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Importo nustatymai', exact: true })).toBeVisible()
  await expect(page.getByText('Kortų: 0', { exact: true })).toBeVisible()
})

test('failed save leaves the old name intact and form can be retried', async ({ page }) => {
  await openDeck(page)
  let failed = false
  await page.route('**/api/decks/*', (route) => {
    if (route.request().method() === 'PUT' && !failed) {
      failed = true
      return route.fulfill({ status: 503, json: { detail: 'Nepavyko išsaugoti pakeitimų. Bandykite dar kartą.' } })
    }
    return route.continue()
  })
  const dialog = await settings(page)
  await dialog.getByLabel('Pavadinimas', { exact: true }).fill('Retry name')
  await dialog.getByRole('button', { name: 'Išsaugoti', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('Nepavyko išsaugoti pakeitimų.')
  await expect(dialog.getByLabel('Pavadinimas', { exact: true })).toHaveValue('Retry name')
  await dialog.getByRole('button', { name: 'Išsaugoti', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Retry name', exact: true })).toBeVisible()
})
