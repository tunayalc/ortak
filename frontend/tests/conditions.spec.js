import { test, expect } from '@playwright/test'

const conditions = { budget_limit: { amount: 2000, scope: 'group', currency: 'TRY' }, excluded_categories: ['museum'], required_features: [] }
const proposal = { source: 'ollama', model: 'llama3:8b', warnings: [], questions: [],
  brief: { city: 'Ankara', area: '', group_size: 4, duration_minutes: 120, budget: 'low', environment: 'any', pace: 'relaxed', interests: [], conditions } }

test.beforeEach(async ({ page }) => {
  await page.route('**/api/health', route => route.fulfill({ json: { ai_ready: true, ai_provider: 'ollama', ai_model: 'llama3:8b', google_configured: false } }))
  await page.goto('/')
})

async function openPlan(page) {
  await page.getByRole('button', { name: 'Buluşma planı', exact: true }).click()
  await page.getByLabel('Buluşmayı anlat').fill('Dört kişi toplam 2000 TL, müze olmasın.')
  await page.getByRole('checkbox', { name: /Metnimin sunucudaki Llama/ }).check()
}

async function overrideRuntime(page, changes) {
  const response = await page.request.get('/api/runtime-config')
  expect(response.ok()).toBe(true)
  const json = { ...await response.json(), ...changes }
  await page.route('**/api/runtime-config', route => route.fulfill({ json }))
}

test('preview cancel keeps current values; approved transfer preserves conditions without Google', async ({ page }) => {
  const paid = []
  page.on('request', r => { if (/\/(scenarios|candidates\/search|routes\/matrix)$/.test(r.url())) paid.push(r.url()) })
  await page.route('**/api/plans/interpret', route => route.fulfill({ json: proposal }))
  await openPlan(page)
  await page.getByRole('button', { name: 'Anlattıklarımdan taslak çıkar' }).click()
  await expect(page.getByLabel('Taslak TL bütçesi', { exact: true })).toHaveValue('2000')
  await expect(page.getByLabel('Plan şehri', { exact: true })).toHaveValue('')
  await page.getByRole('button', { name: 'Vazgeç', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Buluşma planı', exact: true }).getByLabel('TL bütçesi', { exact: true })).toHaveValue('')
  await page.getByRole('button', { name: 'Anlattıklarımdan taslak çıkar' }).click()
  await page.getByRole('button', { name: 'Taslağı kullan' }).click()
  await page.getByRole('button', { name: 'Plan öner', exact: true }).click()
  await page.getByRole('button', { name: 'ORTAK’ta mekân bul' }).first().click()
  await page.getByRole('button', { name: 'Bilgileri aktar' }).click()
  await page.getByText('Kesin koşullar ve TL bütçesi', { exact: true }).click()
  const preferences = page.getByRole('region', { name: 'Mekân tercihleri' })
  await expect(preferences.getByLabel('TL bütçesi', { exact: true })).toHaveValue('2000')
  await expect(preferences.getByLabel('Bütçenin kapsamı', { exact: true })).toHaveValue('group')
  await expect(preferences.getByLabel('Müze olmasın')).toBeChecked()
  expect(paid).toHaveLength(0)
})

test('late model response never overwrites a manual plan edit', async ({ page }) => {
  let release
  const gate = new Promise(resolve => { release = resolve })
  await page.route('**/api/plans/interpret', async route => { await gate; await route.fulfill({ json: proposal }) })
  await openPlan(page)
  await page.getByRole('button', { name: 'Anlattıklarımdan taslak çıkar' }).click()
  await expect(page.getByText('Taslak yorumlanıyor. Mevcut bilgiler henüz değişmedi.')).toBeVisible()
  await page.getByLabel('Plan şehri', { exact: true }).fill('İzmir')
  release()
  await expect(page.getByRole('button', { name: 'Anlattıklarımdan taslak çıkar' })).toBeEnabled()
  await expect(page.getByRole('heading', { name: 'Taslağı incele' })).toHaveCount(0)
  await expect(page.getByLabel('Plan şehri', { exact: true })).toHaveValue('İzmir')
})

test('manual plan can finish while a late model request is still pending', async ({ page }) => {
  let release
  const gate = new Promise(resolve => { release = resolve })
  await page.route('**/api/plans/interpret', async route => { await gate; await route.fulfill({ json: proposal }) })
  await openPlan(page)
  await page.getByRole('button', { name: 'Anlattıklarımdan taslak çıkar' }).click()
  await page.getByLabel('Plan şehri', { exact: true }).fill('İzmir')
  await page.getByLabel('Kaç kişisiniz?', { exact: true }).fill('3')
  await page.getByRole('button', { name: 'Plan öner', exact: true }).click()
  await expect(page.getByRole('button', { name: 'ORTAK’ta mekân bul' })).toHaveCount(3)
  release()
  await expect(page.getByLabel('Plan şehri', { exact: true })).toHaveValue('İzmir')
  await expect(page.getByRole('heading', { name: 'Taslağı incele' })).toHaveCount(0)
})

test('clarification blocks application without changing the form', async ({ page }) => {
  await page.route('**/api/plans/interpret', route => route.fulfill({ json: { ...proposal, questions: ['Bütçe kişi başına mı, toplam mı?'] } }))
  await openPlan(page)
  await page.getByRole('button', { name: 'Anlattıklarımdan taslak çıkar' }).click()
  await expect(page.getByRole('button', { name: 'Taslağı kullan' })).toBeDisabled()
  await expect(page.getByText('Bütçe kişi başına mı, toplam mı?')).toBeVisible()
  await expect(page.getByLabel('Plan şehri', { exact: true })).toHaveValue('')
})

test('venue Llama delay allows manual controls; stale response is discarded', async ({ page }) => {
  let release
  const gate = new Promise(resolve => { release = resolve })
  await page.route('**/api/preferences/interpret', async route => { await gate; await route.fulfill({ json: {
    criterion_weights: { rating: 34, cost: 70, proximity: 33 }, participant_proximity_weights: { 'user-1': 1, 'user-2': 1, 'user-3': 1 },
    min_rating: null, max_duration_minutes: null, source: 'ollama', model: 'llama3:8b', explanation: 'Test', warnings: [],
  } }) })
  await page.getByLabel('Seçim isteği').fill('Fiyat önemli olsun.')
  await page.getByRole('button', { name: 'Tercihi yorumla' }).click()
  await expect(page.getByText('Tercih yorumlanıyor; mevcut ayarlar korunuyor.')).toBeVisible()
  await page.getByRole('button', { name: /Puan öncelikli/ }).click()
  await expect(page.locator('.criteria-sliders input').first()).toHaveValue('60')
  release()
  await expect(page.getByRole('button', { name: 'Tercihi yorumla' })).toBeEnabled()
  await expect(page.getByText('Önerilen değerler', { exact: true })).toHaveCount(0)
})

test('absolute session expiry removes private inputs and results', async ({ page }) => {
  await page.clock.install()
  await overrideRuntime(page, { session_ttl_seconds: 2 })
  await page.reload()
  await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  await page.clock.fastForward(2100)
  await expect(page.locator('.recommendation-card')).toHaveCount(0)
  await expect(page.getByRole('alert')).toContainText('Oturum süresi doldu')
  await expect(page.getByLabel('Seçim isteği')).toHaveValue('')
})

test('unknown price keeps the budget and entered costs reuse routes', async ({ page }) => {
  let routeRequests = 0
  page.on('request', request => { if (request.url().endsWith('/routes/matrix')) routeRequests++ })
  await page.getByText('Kesin koşullar ve TL bütçesi', { exact: true }).click()
  await page.getByRole('region', { name: 'Mekân tercihleri' }).getByLabel('TL bütçesi', { exact: true }).fill('2000')
  await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
  await expect(page.getByText('Kısıtlara uygun mekân bulunamadı', { exact: true })).toBeVisible()
  const costs = page.getByRole('group', { name: 'Adayların kişi başı maliyeti' }).getByRole('spinbutton')
  await expect(costs).toHaveCount(12)
  for (const input of await costs.all()) await input.fill('250')
  await page.getByRole('button', { name: 'Güncelle', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  expect(routeRequests).toBe(1)
})

test('older backend cannot silently discard conditions or context', async ({ page }) => {
  await overrideRuntime(page, { capabilities: {} })
  await page.reload()
  let mutations = 0
  page.on('request', r => { if (r.method() === 'POST') mutations++ })
  await page.getByLabel('Seçim isteği').fill('Fiyat önemli olsun')
  await page.getByRole('button', { name: 'Tercihi yorumla' }).click()
  await expect(page.getByRole('alert')).toContainText('Sunucu bağlamı koruyan')
  await page.getByText('Kesin koşullar ve TL bütçesi', { exact: true }).click()
  await page.getByRole('region', { name: 'Mekân tercihleri' }).getByLabel('TL bütçesi', { exact: true }).fill('2000')
  await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Sunucu kesin koşulları henüz desteklemiyor')
  expect(mutations).toBe(0)
})

test('phone landscape, tablet, desktop, long labels and reduced motion fit', async ({ page }) => {
  await openPlan(page)
  await page.getByLabel('Plan şehri', { exact: true }).fill('Çok uzun bir şehir ve semt başlığı')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  for (const [width, height] of [[390, 844], [844, 390], [768, 1024], [1440, 1000]]) {
    await page.setViewportSize({ width, height })
    for (const theme of ['light', 'dark']) {
      await page.evaluate(t => { document.documentElement.dataset.theme = t }, theme)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    }
  }
  await page.getByRole('link', { name: '2 Koşullar', exact: true }).click()
  await expect(page.locator('#plan-details')).toBeFocused()
  expect(await page.locator('meta[name=viewport]').getAttribute('content')).not.toMatch(/user-scalable=no|maximum-scale=1/)
})
