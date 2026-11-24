import { test, expect, type Page } from '@playwright/test'

async function register(page: Page) {
  await page.goto('/registracija')
  await page.getByLabel('El. paštas', { exact: true }).fill(`ni04-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`)
  await page.getByLabel('Slaptažodis', { exact: true }).fill('Password123!')
  await page.getByLabel('Pakartokite slaptažodį').fill('Password123!')
  await page.getByRole('button', { name: 'Registruotis', exact: true }).click()
  await expect(page).toHaveURL(/\/mano-kalades$/)
}

async function openNew(page: Page) {
  await page.getByRole('button', { name: '+ Nauja kaladė', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Nauja kaladė', exact: true })
  await expect(dialog).toBeVisible()
  return dialog
}

test('named deck is created, opens and remains in the list after reload', async ({ page }) => {
  await register(page)
  const dialog = await openNew(page)
  await expect(dialog.getByLabel('Pavadinimas (nebūtinas)', { exact: true })).toBeFocused()
  await expect(dialog.getByLabel(/Formatas|Bracket/)).toHaveCount(0)
  await dialog.getByLabel('Pavadinimas (nebūtinas)', { exact: true }).fill('Hues & Clues')
  await dialog.getByRole('button', { name: 'Sukurti', exact: true }).click()
  await expect(page).toHaveURL(/\/kalades\/\d+$/)
  await expect(page.getByRole('heading', { name: 'Hues & Clues', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Hues & Clues', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Mano kaladės', exact: true }).click()
  await expect(page.getByTestId('deck-count')).toHaveText('1 kaladė')
  await expect(page.getByRole('link', { name: 'Hues & Clues. Kortų: 0.', exact: true })).toBeVisible()
})

test('blank names are numbered for the current account', async ({ page }) => {
  await register(page)
  for (const number of [1, 2]) {
    const dialog = await openNew(page)
    await dialog.getByRole('button', { name: 'Sukurti', exact: true }).click()
    await expect(page.getByRole('heading', { name: `Nauja kaladė ${number}`, exact: true })).toBeVisible()
    await page.getByRole('link', { name: 'Mano kaladės', exact: true }).click()
  }
  await expect(page.getByTestId('deck-count')).toHaveText('2 kaladės')
})

test('cancel, close and Escape do not create a deck', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await register(page)
  for (const action of ['Atšaukti', 'Uždaryti', 'Escape']) {
    const dialog = await openNew(page)
    await dialog.getByLabel('Pavadinimas (nebūtinas)', { exact: true }).fill('Do not save')
    if (action === 'Escape') await page.keyboard.press('Escape')
    else await dialog.getByRole('button', { name: action, exact: true }).click()
    await expect(dialog).toHaveCount(0)
    await expect(page.getByTestId('deck-count')).toHaveText('0 kaladžių')
  }
  const dialog = await openNew(page)
  await expect(dialog.getByLabel('Pavadinimas (nebūtinas)', { exact: true })).toHaveValue('')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('long name is rejected at the name field', async ({ page }) => {
  await register(page)
  const dialog = await openNew(page)
  await dialog.getByLabel('Pavadinimas (nebūtinas)', { exact: true }).fill('ą'.repeat(101))
  await dialog.getByRole('button', { name: 'Sukurti', exact: true }).click()
  await expect(dialog.getByRole('alert')).toHaveText('Pavadinimas negali būti ilgesnis nei 100 simbolių.')
  await dialog.getByRole('button', { name: 'Atšaukti', exact: true }).click()
  await expect(page.getByTestId('deck-count')).toHaveText('0 kaladžių')
})

test('unknown lines can be corrected or skipped without losing the new deck', async ({ page }) => {
  await register(page)
  const dialog = await openNew(page)
  const unknown = `UnknownNI04-${Date.now()}`
  await dialog.getByLabel('Pavadinimas (nebūtinas)', { exact: true }).fill('Importo patikra')
  await dialog.getByLabel('Kortų sąrašas (nebūtinas)', { exact: true }).fill(`${unknown}\nMaybeboard\n${unknown}-maybe`)
  await dialog.getByRole('button', { name: 'Sukurti', exact: true }).click()
  const result = page.getByRole('dialog', { name: 'Importo rezultatas', exact: true })
  await expect(result).toBeVisible()
  await expect(result.getByText('Šiuo bandymu į kaladę „Importo patikra“ kortų neimportuota.', { exact: true })).toBeVisible()
  await expect(result.getByText('Neatpažintų eilučių: 2. Pataisykite jas arba praleiskite.')).toBeVisible()
  await expect(result.getByLabel('Neatpažintos eilutės', { exact: true })).toHaveValue(`${unknown}\nSvarstomos\n${unknown}-maybe`)
  await result.getByLabel('Neatpažintos eilutės', { exact: true }).fill(`Svarstomos\n${unknown}-corrected`)
  await result.getByRole('button', { name: 'Importuoti pataisytas', exact: true }).click()
  await expect(result.getByText('Neatpažintų eilučių: 1. Pataisykite jas arba praleiskite.')).toBeVisible()
  await result.getByRole('button', { name: 'Uždaryti', exact: true }).click()
  await expect(result).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Importo patikra', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Mano kaladės', exact: true }).click()
  await expect(page.getByTestId('deck-count')).toHaveText('1 kaladė')
})

test('server failure preserves form values and allows retry', async ({ page }) => {
  await register(page)
  let attempts = 0
  await page.route('**/api/decks', (route) => {
    if (route.request().method() === 'POST' && ++attempts === 1) {
      return route.fulfill({ status: 503, json: { detail: 'Nepavyko sukurti kaladės. Bandykite dar kartą.' } })
    }
    return route.continue()
  })
  const dialog = await openNew(page)
  await dialog.getByLabel('Pavadinimas (nebūtinas)', { exact: true }).fill('Retry deck')
  await dialog.getByRole('button', { name: 'Sukurti', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('Nepavyko sukurti kaladės.')
  await expect(dialog.getByLabel('Pavadinimas (nebūtinas)', { exact: true })).toHaveValue('Retry deck')
  await dialog.getByRole('button', { name: 'Sukurti', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Retry deck', exact: true })).toBeVisible()
})
