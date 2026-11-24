import { expect, test } from '@playwright/test'
import type { DeckCard } from '../src/decks'

const user = { id: 1, email: 'ni08@example.com' }
const summary = { id: 8, name: 'Bandomoji kaladė', card_count: 0, colors: [], colors_known: true }
const plains: DeckCard = {
  oracle_id: 'plains', list_name: 'main', quantity: 4, name: 'Plains',
  mana_cost: '', mana_value: 0, is_land: true,
}
const expensive: DeckCard = {
  oracle_id: 'expensive', list_name: 'main', quantity: 2, name: 'Expensive Spell',
  mana_cost: '{5}{R}', mana_value: 6, is_land: false,
}
const zero: DeckCard = {
  oracle_id: 'zero', list_name: 'main', quantity: 1, name: 'Zero Spell',
  mana_cost: '{0}', mana_value: 0, is_land: false,
}
const candidate: DeckCard = {
  ...expensive, list_name: 'maybeboard', quantity: 3,
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(sessionUser => {
    sessionStorage.setItem('workshop.session', JSON.stringify({
      access_token: 'test-session', expires_at: Date.now() / 1000 + 3600, user: sessionUser,
    }))
  }, user)
  await page.route('**/api/auth/me', route => route.fulfill({ json: user }))
})

test('shows the empty invitation and refreshes the grouped lists after importing', async ({ page }) => {
  let imported = false
  const updated = { ...summary, card_count: 7, colors: ['W', 'R'] }
  await page.route('**/api/decks/8', route => {
    if (route.request().method() === 'PUT') {
      imported = true
      return route.fulfill({ json: { deck: updated, import_result: {
        imported: 10, unrecognized_lines: [], skipped_main: 0,
      } } })
    }
    return route.fulfill({ json: imported
      ? { ...updated, cards: [plains, expensive, zero, candidate] }
      : { ...summary, cards: [] } })
  })
  await page.goto('/kalades/8')
  await expect(page.getByText('Kaladėje dar nėra kortų. Ieškokite kortų arba importuokite kortų sąrašą.')).toBeVisible()
  await page.getByRole('button', { name: 'Nustatymai' }).click()
  const settings = page.getByRole('dialog')
  await settings.locator('textarea').fill('4 Plains')
  await settings.getByRole('button', { name: 'Išsaugoti', exact: true }).click()

  await expect(page.getByText('Kortų: 7', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '0 (1)', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '6+ (2)', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Žemės (4)', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Svarstomos kortos (3)', exact: true })).toBeVisible()
  const rows = page.getByRole('listitem').filter({ hasText: 'Expensive Spell' })
  await expect(rows).toHaveCount(2)
  await expect(rows.first()).toContainText('2×')
  await expect(rows.first()).toContainText('{5}{R}')
  await expect(rows.last()).toContainText('3×')
})
