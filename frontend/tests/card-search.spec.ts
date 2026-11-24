import { test, expect } from '@playwright/test'

test('guest searches Scryfall and expands the results', async ({ page }) => {
  await page.goto('/')
  const query = page.getByRole('searchbox')
  await query.fill('t:instant c:u')
  await query.press('Enter')
  const hits = page.locator('.search-results li')
  await expect(hits).toHaveCount(8, { timeout: 15000 })
  await page.getByRole('button', { name: 'Rodyti daugiau' }).click()
  await expect(hits).toHaveCount(16)
  await expect(query).toHaveValue('t:instant c:u')
})
