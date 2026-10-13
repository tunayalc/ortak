import { test, expect } from '@playwright/test'

const runtime = { production: true, csrf_token: '', max_participants: 8, max_candidates: 3, max_k: 3, session_ttl_seconds: 7200, google_available: true, google_remaining_requests: 33 }

test.beforeEach(async ({ page }) => {
  await page.route('**/api/runtime-config', (route) => route.fulfill({ json: runtime }))
  await page.route('**/api/health', (route) => route.fulfill({ json: { status: 'ok', google_configured: false, ai_provider: 'ollama', ai_model: 'llama3:8b', ai_ready: true, ai_status: 'ready' } }))
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Öneri üret', exact: true })).toBeEnabled()
})

test('form, kişi sayısı, delta ve dengeli kişiler', async ({ page }) => {
  await page.getByLabel('Grup', { exact: true }).fill('4')
  await page.getByRole('button', { name: 'Link ile kişi konumu' }).click()
  await expect(page.getByLabel('Link veya koordinat', { exact: true })).toHaveCount(4)
  const deltas = page.locator('.participant-row input[type=number]')
  await deltas.nth(0).fill('2')
  await expect(deltas.nth(0)).toHaveValue('2')
  await page.getByRole('button', { name: 'Kişiler dengeli' }).click()
  for (const field of await deltas.all()) await expect(field).toHaveValue('1')
  await expect(page.getByLabel('Top-K', { exact: true })).toHaveAttribute('max', '3')
})

test('hatalı bağlantı öneri akışını durdurur', async ({ page }) => {
  let scenarios = 0
  page.on('request', (request) => { if (request.url().endsWith('/api/scenarios')) scenarios++ })
  await page.getByRole('button', { name: 'Link ile kişi konumu' }).click()
  for (const input of await page.getByLabel('Link veya koordinat', { exact: true }).all()) await input.fill('invalid-location')
  await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
  await expect(page.locator('.parse-status.fail')).toHaveCount(3)
  expect(scenarios).toBe(0)
})

test('öneriler, profiller, filtre ve boş sonuç', async ({ page }) => {
  let routes = 0
  page.on('request', (request) => { if (request.url().endsWith('/api/routes/matrix')) routes++ })
  await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  await page.getByRole('button', { name: /Puan öncelikli/ }).click()
  await expect(page.locator('.profile-control .active')).toContainText('Puan öncelikli')
  await expect(page.getByRole('button', { name: 'Güncelle', exact: true })).toBeEnabled()
  expect(routes).toBe(1)
  await page.getByLabel('En az puan', { exact: true }).fill('5')
  await page.getByRole('button', { name: 'Güncelle', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(0)
})

test('bilinmeyen fiyat nötr gösterilir', async ({ page }) => {
  await page.route('**/api/recommendations', async (route) => {
    const response = await route.fetch()
    const result = await response.json()
    for (const item of result.recommendations) {
      item.candidate.price_level = null
      item.candidate.manual_cost = null
      item.cost_source = 'unknown'
      item.cost_norm = 0.5
    }
    await route.fulfill({ json: result })
  })
  await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  await expect(page.locator('.recommendation-card').first()).toContainText(/Nötr|nötr/)
})

test('model önerisi onay verilmeden değerleri değiştirmez', async ({ page }) => {
  await page.route('**/api/preferences/interpret', (route) => route.fulfill({ json: {
    criterion_weights: { rating: 34, cost: 70, proximity: 33 },
    participant_proximity_weights: { 'user-1': 2, 'user-2': 1, 'user-3': 1 },
    min_rating: 4, max_duration_minutes: null, explanation: 'Kurgusal test önerisi.', warnings: [], source: 'ollama', model: 'llama3:8b',
  } }))
  const sliders = page.locator('.criteria-sliders input')
  await page.getByLabel('Seçim isteği').fill('Fiyat önemli; Kişi 1 iki kat önemli olsun.')
  await page.getByRole('button', { name: 'Tercihi yorumla' }).click()
  await expect(page.getByText('Önerilen değerler', { exact: true })).toBeVisible()
  await expect(sliders.nth(1)).toHaveValue('33')
  await expect(page.getByLabel('Katılımcı 1 yakınlık ağırlığı')).toHaveValue('1')
  await page.getByRole('button', { name: 'Değerleri uygula' }).click()
  await expect(sliders.nth(1)).toHaveValue('70')
  await expect(page.getByLabel('Katılımcı 1 yakınlık ağırlığı')).toHaveValue('2')
})

test('kota ve backend hataları açık gösterilir', async ({ page }) => {
  await page.route('**/api/scenarios', (route) => route.fulfill({ status: 429, json: { detail: 'Günlük kota doldu; yeni çağrı yapılmadı.' } }))
  await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
  await expect(page.getByText('Günlük kota doldu; yeni çağrı yapılmadı.', { exact: true })).toBeVisible()
  await page.route('**/api/runtime-config', (route) => route.fulfill({ json: { ...runtime, google_available: false, google_unavailable_reason: 'Google işlemleri kapalı.' } }))
  await page.reload()
  await expect(page.getByRole('button', { name: 'Öneri üret', exact: true })).toBeDisabled()
})

test('açık ve koyu tema, klavye, taşma', async ({ page }, testInfo) => {
  for (const theme of ['light', 'dark']) {
    const current = await page.locator('html').getAttribute('data-theme')
    if (current !== theme) await page.getByRole('button', { name: /temaya geç/ }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
    await page.getByRole('button', { name: 'Link ile kişi konumu' }).click()
    const overflowing = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(overflowing).toBe(false)
    await page.screenshot({ path: testInfo.outputPath(`${theme}.png`), fullPage: true })
  }
  await page.getByLabel('Şehir', { exact: true }).focus()
  await page.keyboard.press('Tab')
  await expect(page.getByLabel('Mekân türü')).toBeFocused()
})
