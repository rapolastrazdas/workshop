import { test, expect, type Page } from '@playwright/test'

async function register(page: Page) {
  const email = `ni03-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`
  await page.goto('/registracija')
  await page.getByLabel('El. paštas', { exact: true }).fill(email)
  await page.getByLabel('Slaptažodis', { exact: true }).fill('Password123!')
  await page.getByLabel('Pakartokite slaptažodį').fill('Password123!')
  await page.getByRole('button', { name: 'Registruotis', exact: true }).click()
  await expect(page).toHaveURL(/\/mano-kalades$/)
}

const decks = [
  { id: 101, name: 'Hues & Clues', card_count: 60, colors: ['W', 'U', 'B'], colors_known: true },
  { id: 102, name: 'Goblinų vakarėlis', card_count: 75, colors: ['R'], colors_known: true },
  { id: 103, name: 'Nauja kaladė 3', card_count: 0, colors: [], colors_known: true },
  { id: 104, name: 'Artefaktai', card_count: 12, colors: [], colors_known: true },
]

test('empty account sees count, invitation and new deck button', async ({ page }) => {
  await register(page)
  await expect(page.getByTestId('deck-count')).toHaveText('0 kaladžių')
  await expect(page.getByRole('heading', { name: 'Dar neturite kaladžių' })).toBeVisible()
  await expect(page.getByText('Sukurkite savo pirmąją kaladę.')).toBeVisible()
  await expect(page.getByRole('button', { name: '+ Nauja kaladė', exact: true })).toBeEnabled()
  await expect(page.getByRole('list', { name: 'Mano kaladžių sąrašas' })).toHaveCount(0)
})

test('deck cards show names, counts and colors and open the editor', async ({ page }) => {
  await page.route('**/api/decks', (route) => route.fulfill({ json: { count: decks.length, decks } }))
  await page.route('**/api/decks/101', (route) => route.fulfill({ json: decks[0] }))
  await register(page)
  await expect(page.getByTestId('deck-count')).toHaveText('4 kaladės')
  await expect(page.getByRole('list', { name: 'Mano kaladžių sąrašas' }).locator(':scope > li')).toHaveCount(4)
  const multicolor = page.getByRole('link', { name: 'Hues & Clues. Kortų: 60.', exact: true })
  await expect(multicolor.getByLabel('Balta', { exact: true })).toBeVisible()
  await expect(multicolor.getByLabel('Mėlyna', { exact: true })).toBeVisible()
  await expect(multicolor.getByLabel('Juoda', { exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Goblinų vakarėlis. Kortų: 75.', exact: true }).getByLabel('Raudona')).toBeVisible()
  const empty = page.getByRole('link', { name: 'Nauja kaladė 3. Kortų: 0.', exact: true })
  await expect(empty.locator('.mana-badge')).toHaveCount(0)
  await expect(page.getByLabel('Bespalvė kaladė', { exact: true })).toBeVisible()
  await multicolor.click()
  await expect(page).toHaveURL(/\/kalades\/101$/)
  await expect(page.getByRole('heading', { name: 'Hues & Clues', exact: true })).toBeVisible()
  await expect(page.getByText('Kortų: 60', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Mano kaladės', exact: true }).click()
  await expect(page).toHaveURL(/\/mano-kalades$/)
})

test('unknown deck address shows not found without private data', async ({ page }) => {
  await register(page)
  await page.goto('/kalades/2147483647')
  await expect(page.getByRole('heading', { name: 'Kaladė nerasta', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Mano kaladės', exact: true })).toBeVisible()
})

test('list loading failure can be retried without showing a false empty state', async ({ page }) => {
  let attempts = 0
  await page.route('**/api/decks', (route) => {
    attempts++
    return attempts === 1
      ? route.fulfill({ status: 503, json: { detail: 'Nepavyko gauti kortų duomenų. Bandykite dar kartą.' } })
      : route.fulfill({ json: { count: 1, decks: [decks[0]] } })
  })
  await register(page)
  await expect(page.getByRole('alert')).toContainText('Nepavyko gauti kortų duomenų.')
  await expect(page.getByText('Dar neturite kaladžių', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Bandyti dar kartą' }).click()
  await expect(page.getByTestId('deck-count')).toHaveText('1 kaladė')
  await expect(page.getByRole('link', { name: 'Hues & Clues. Kortų: 60.', exact: true })).toBeVisible()
})

test('deck cards fit a phone and missing colors are explained', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const unknown = { id: 105, name: 'Ilgas kaladės pavadinimas be tarpų: ' + 'x'.repeat(100), card_count: 8, colors: [], colors_known: false }
  await page.route('**/api/decks', (route) => route.fulfill({ json: { count: 1, decks: [unknown] } }))
  await register(page)
  await expect(page.getByText('Spalvos nenustatytos', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})
