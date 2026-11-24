import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'

test('guest opens a search result and closes it using Escape or the close button', async ({ page }) => {
  await page.goto('/')
  const search = page.getByRole('searchbox')
  await search.fill('!"Lightning Bolt"')
  await search.press('Enter')
  const result = page.getByRole('button', { name: 'Lightning Bolt', exact: true })
  await result.click({ timeout: 15000 })
  const dialog = page.getByRole('dialog', { name: 'Kortos informacija' })
  await expect(dialog.getByRole('img', { name: 'Lightning Bolt' })).toHaveAttribute('src', /^https:\/\/cards\.scryfall\.io\//)
  await expect(dialog.getByText('Lightning Bolt deals 3 damage to any target.')).toBeVisible()
  await expect(dialog.getByText('{R}', { exact: true })).toBeVisible()
  await expect(dialog.getByText('Instant', { exact: true })).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Rasti panašias' })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: '+ Pagrindinis', exact: true })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await result.click()
  await dialog.getByRole('button', { name: 'Uždaryti langą' }).click()
  await expect(dialog).toHaveCount(0)
})

test('editor opens a deck card and saves additions to both lists', async ({ page, request }) => {
  const password = randomUUID()
  const response = await request.post('/api/auth/register', { data: {
    email: `ni11-${randomUUID()}@example.com`, password, password_confirmation: password,
  } })
  expect(response.status()).toBe(201)
  const session = await response.json()
  const headers = { Authorization: `Bearer ${session.access_token}` }
  try {
    const created = await request.post('/api/decks', {
      headers, data: { name: 'NI-11 patikra', card_list: '1 Lightning Bolt' },
    })
    expect(created.status()).toBe(201)
    const { deck } = await created.json()
    await page.addInitScript(value => sessionStorage.setItem('workshop.session', value), JSON.stringify(session))
    await page.goto(`/kalades/${deck.id}`)
    await page.getByRole('button', { name: 'Lightning Bolt', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Kortos informacija' })
    await expect(dialog.getByText('Lightning Bolt deals 3 damage to any target.')).toBeVisible()
    await dialog.getByRole('button', { name: '+ Pagrindinis', exact: true }).click()
    await expect(dialog.locator('[aria-label="Kiekis pagrindinių kortų sąraše"]')).toHaveText('2')
    await dialog.getByRole('button', { name: '+ Svarstomos', exact: true }).click()
    await expect(dialog.locator('[aria-label="Kiekis svarstomų kortų sąraše"]')).toHaveText('1')
    await dialog.getByRole('button', { name: 'Sumažinti pagrindinių kortų kiekį' }).click()
    await expect(dialog.locator('[aria-label="Kiekis pagrindinių kortų sąraše"]')).toHaveText('1')
    await page.reload()
    await expect(page.getByText('Kortų: 1', { exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Svarstomos kortos (1)' })).toBeVisible()
  } finally {
    expect((await request.delete('/api/auth/account', { headers, data: { password } })).status()).toBe(204)
  }
})
