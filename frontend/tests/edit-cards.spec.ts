import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'

test('adds, saves, decreases and removes deck cards', async ({ page, request }) => {
  const password = randomUUID()
  const registration = await request.post('/api/auth/register', { data: {
    email: `ni09-${randomUUID()}@example.com`, password, password_confirmation: password,
  } })
  expect(registration.status()).toBe(201)
  const session = await registration.json()
  const headers = { Authorization: `Bearer ${session.access_token}` }
  try {
    const created = await request.post('/api/decks', { headers, data: { name: 'NI-09 patikra' } })
    expect(created.status()).toBe(201)
    const { deck } = await created.json()
    await page.addInitScript(value => sessionStorage.setItem('workshop.session', value), JSON.stringify(session))
    await page.goto(`/kalades/${deck.id}`)
    await page.getByRole('searchbox').fill('Sol Ring')
    await page.getByRole('button', { name: 'Ieškoti' }).click()
    const hit = page.locator('.search-results li').filter({ has: page.getByText('Sol Ring', { exact: true }) })
    await hit.getByRole('button', { name: '+ Pagrindinis' }).click()
    const rows = page.locator('.deck-card-list li')
    const main = rows.first()
    await expect(main).toContainText('1×')
    await main.getByLabel('Padidinti kiekį').click()
    await expect(main).toContainText('2×')
    await hit.getByRole('button', { name: '+ Svarstomos' }).click()
    await expect(rows).toHaveCount(2)
    await page.reload()
    await expect(main).toContainText('2×')
    await main.getByRole('button', { name: 'Perkelti į svarstomas' }).click()
    await expect(rows).toHaveCount(1)
    await expect(main).toContainText('3×')
    await expect(page.getByText('Kortų: 0', { exact: true })).toBeVisible()
    await main.getByRole('button', { name: 'Perkelti į pagrindines' }).click()
    await expect(page.getByText('Kortų: 3', { exact: true })).toBeVisible()
    await page.reload()
    await expect(main).toContainText('3×')
    await main.getByLabel('Sumažinti kiekį').click()
    await expect(main).toContainText('2×')
    await main.getByLabel('Sumažinti kiekį').click()
    await expect(main).toContainText('1×')
    await page.getByRole('searchbox').fill('Sol Ring')
    await page.getByRole('searchbox').press('Enter')
    await hit.getByRole('button', { name: '+ Svarstomos' }).click()
    await expect(rows).toHaveCount(2)
    await main.getByLabel('Sumažinti kiekį').click()
    await expect(rows).toHaveCount(1)
    await rows.last().getByRole('button', { name: 'Pašalinti' }).click()
    await expect(rows).toHaveCount(0)
  } finally {
    expect((await request.delete('/api/auth/account', { headers, data: { password } })).status()).toBe(204)
  }
})
