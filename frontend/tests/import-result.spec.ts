import { test, expect } from '@playwright/test'

test('result follows the mockup and corrected lines require an explicit button click', async ({ page }) => {
  const deck = { id: 501, name: 'Hues & Clues', card_count: 2, colors: ['R'], colors_known: true }
  let writes = 0
  await page.route('**/api/decks', (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    writes++
    return route.fulfill({ status: 201, json: { deck, import_result: {
      imported: 2, skipped_main: 0,
      unrecognized_lines: [{ text: '1 Sol Rign (C21) 263', list_name: 'main' }],
    } } })
  })
  await page.route('**/api/decks/501', (route) => route.fulfill({ json: deck }))
  await page.route('**/api/decks/501/import', (route) => {
    writes++
    expect(route.request().postDataJSON()).toEqual({ card_list: '1 Sol Ring (C21) 263' })
    return route.fulfill({ json: { deck: { ...deck, card_count: 3 }, import_result: {
      imported: 1, unrecognized_lines: [], skipped_main: 0,
    } } })
  })
  await page.goto('/registracija')
  await page.getByLabel('El. paštas', { exact: true }).fill(`ni05-${Date.now()}@example.com`)
  await page.getByLabel('Slaptažodis', { exact: true }).fill('Password123!')
  await page.getByLabel('Pakartokite slaptažodį').fill('Password123!')
  await page.getByRole('button', { name: 'Registruotis', exact: true }).click()
  await expect(page).toHaveURL(/\/mano-kalades$/)
  await page.getByRole('button', { name: '+ Nauja kaladė', exact: true }).click()
  const creation = page.getByRole('dialog', { name: 'Nauja kaladė', exact: true })
  await creation.getByLabel('Pavadinimas (nebūtinas)', { exact: true }).fill(deck.name)
  await creation.getByLabel('Kortų sąrašas (nebūtinas)', { exact: true }).fill('2 Lightning Bolt\n1 Sol Rign (C21) 263')
  expect(writes).toBe(0)
  await creation.getByRole('button', { name: 'Sukurti', exact: true }).click()
  const result = page.getByRole('dialog', { name: 'Importo rezultatas', exact: true })
  await expect(result).toBeVisible()
  await expect(result.getByText('Atpažintos kortos jau įrašytos į kaladę „Hues & Clues“.', { exact: true })).toBeVisible()
  await expect(result.getByText('Viena korta eilutėje: kiekis ir pavadinimas.', { exact: true })).toBeVisible()
  await expect(result.getByRole('button', { name: 'Uždaryti', exact: true })).toBeVisible()
  await expect(result.getByRole('button', { name: 'Uždaryti langą', exact: true })).toBeVisible()
  const corrected = result.getByLabel('Neatpažintos eilutės', { exact: true })
  await expect(corrected).toHaveValue('1 Sol Rign (C21) 263')
  await corrected.fill('1 Sol Ring (C21) 263')
  expect(writes).toBe(1)
  await result.getByRole('button', { name: 'Importuoti pataisytas', exact: true }).click()
  await expect(result).toHaveCount(0)
  expect(writes).toBe(2)
  await expect(page.getByText('Kortų: 3', { exact: true })).toBeVisible()
})
