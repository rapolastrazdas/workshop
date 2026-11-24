import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'

test('imports real catalog cards and shows the saved groups after reloading', async ({ page, request }) => {
  const password = randomUUID()
  const registration = await request.post('/api/auth/register', { data: {
    email: `ni08-${randomUUID()}@example.com`, password, password_confirmation: password,
  } })
  expect(registration.status()).toBe(201)
  const session = await registration.json()
  const headers = { Authorization: `Bearer ${session.access_token}` }
  try {
    const created = await request.post('/api/decks', { headers, data: { name: 'NI-08 patikra' } })
    expect(created.status()).toBe(201)
    const { deck } = await created.json()
    await page.addInitScript(value => sessionStorage.setItem('workshop.session', value), JSON.stringify(session))
    await page.goto(`/kalades/${deck.id}`)
    await page.getByRole('button', { name: 'Nustatymai' }).click()
    await page.getByLabel('Kortų importas (nebūtinas)').fill('1 Bygone Bishop\n4 Plains\nSvarstomos\n1 Sol Ring')
    await page.getByRole('button', { name: 'Išsaugoti' }).click()
    await expect(page.getByText('Bygone Bishop', { exact: true })).toBeVisible()
    await page.reload()
    await expect(page.getByText('Kortų: 5', { exact: true })).toBeVisible()
    for (const [heading, name] of [['3 (1)', 'Bygone Bishop'], ['Žemės (4)', 'Plains'], ['Svarstomos kortos (1)', 'Sol Ring']]) {
      const group = page.locator('section.deck-card-group').filter({ has: page.getByRole('heading', { name: heading, exact: true }) })
      await expect(group.getByText(name, { exact: true })).toBeVisible()
    }
  } finally {
    const cleanup = await request.delete('/api/auth/account', { headers, data: { password } })
    expect(cleanup.status()).toBe(204)
  }
})
