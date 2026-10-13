import { test, expect } from '@playwright/test'

const runtime = { production: true, csrf_token: '', max_participants: 8, max_candidates: 3, max_k: 3, session_ttl_seconds: 7200, google_available: true, google_remaining_requests: 33 }

async function previewPreference(page) {
  await page.route('**/api/preferences/interpret', (route) => route.fulfill({ json: {
    criterion_weights: { rating: 34, cost: 70, proximity: 33 },
    participant_proximity_weights: { 'user-1': 2, 'user-2': 1, 'user-3': 1 },
    min_rating: null, max_duration_minutes: null, explanation: 'Kurgusal test önerisi.', warnings: [], source: 'ollama', model: 'llama3:8b',
  } }))
  await page.getByLabel('Seçim isteği').fill('Fiyat önemli; Kişi 1 iki kat önemli olsun.')
  await page.getByRole('button', { name: 'Tercihi yorumla' }).click()
  await expect(page.getByText('Önerilen değerler', { exact: true })).toBeVisible()
}

async function enterLocations(page) {
  await page.getByRole('button', { name: 'Link ile kişi konumu' }).click()
  const fields = page.getByLabel('Link veya koordinat', { exact: true })
  for (const [index, coordinate] of ['39.92,32.85', '39.93,32.86', '39.94,32.87'].entries()) {
    await fields.nth(index).fill(coordinate)
  }
}

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

test('onaylanan tercih kişi konumlarıyla arama başlatır; konumlar modele gönderilmez', async ({ page }) => {
  await enterLocations(page)
  const requests = []
  page.on('request', (request) => {
    if (request.method() === 'POST') requests.push({ path: new URL(request.url()).pathname, body: request.postDataJSON() })
  })
  await previewPreference(page)
  expect(requests.filter((request) => request.path === '/api/scenarios')).toHaveLength(0)
  const prompt = requests.find((request) => request.path === '/api/preferences/interpret').body
  expect(JSON.stringify(prompt)).not.toContain('39.92')
  expect(prompt.participants[0]).not.toHaveProperty('value')
  await page.getByRole('button', { name: 'Uygula ve mekânları bul', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  const scenario = requests.find((request) => request.path === '/api/scenarios').body
  expect(scenario.session_only).toBe(true)
  expect(scenario.participant_locations[0].value).toBe('39.92,32.85')
  expect(scenario.participant_locations[0].delta_weight).toBe(2)
  const recommendation = requests.find((request) => request.path === '/api/recommendations').body
  expect(recommendation.criterion_weights.cost).toBe(70)
  expect(recommendation.participant_proximity_weights['user-1']).toBe(2)
})

test('tercih güncellemesi mevcut rotaları kullanır', async ({ page }) => {
  let routes = 0
  let candidates = 0
  page.on('request', (request) => {
    if (request.url().endsWith('/api/routes/matrix')) routes++
    if (request.url().endsWith('/api/candidates/search')) candidates++
  })
  await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  await previewPreference(page)
  await expect(page.getByText(/Mevcut rotalar kullanılır/)).toBeVisible()
  await page.getByRole('button', { name: 'Uygula ve mekânları bul', exact: true }).click()
  await expect(page.locator('.criteria-sliders input').nth(1)).toHaveValue('70')
  await expect(page.getByRole('button', { name: 'Güncelle', exact: true })).toBeEnabled()
  expect(routes).toBe(1)
  expect(candidates).toBe(1)
})

test('değişen kişi konumu eski rotalarla sıralanmaz', async ({ page }) => {
  await enterLocations(page)
  let routes = 0
  page.on('request', (request) => { if (request.url().endsWith('/api/routes/matrix')) routes++ })
  await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  await page.getByLabel('Link veya koordinat', { exact: true }).nth(0).fill('39.95,32.88')
  await expect(page.locator('.recommendation-card')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Güncelle', exact: true })).toBeDisabled()
  await previewPreference(page)
  await page.getByRole('button', { name: 'Uygula ve mekânları bul', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  expect(routes).toBe(2)
})

test('kota kapalıyken model yeni Google araması başlatamaz; manuel onay korunur', async ({ page }) => {
  await page.route('**/api/runtime-config', (route) => route.fulfill({ json: { ...runtime, google_available: false } }))
  await page.reload()
  let scenarios = 0
  page.on('request', (request) => { if (request.url().endsWith('/api/scenarios')) scenarios++ })
  await previewPreference(page)
  await expect(page.getByRole('button', { name: 'Uygula ve mekânları bul', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: 'Değerleri uygula', exact: true }).click()
  await expect(page.locator('.criteria-sliders input').nth(1)).toHaveValue('70')
  expect(scenarios).toBe(0)
})

test('yerel Google anahtarı varken kapalı çağrılar model tarafından açılmaz', async ({ page }) => {
  await page.route('**/api/runtime-config', (route) => route.fulfill({ json: { ...runtime, production: false, google_available: false, google_unavailable_reason: 'Google çağrıları kapalı.' } }))
  await page.route('**/api/health', (route) => route.fulfill({ json: { google_configured: true, ai_provider: 'ollama', ai_model: 'llama3:8b', ai_ready: true, ai_status: 'ready' } }))
  await page.reload()
  await previewPreference(page)
  await expect(page.getByRole('button', { name: 'Öneri üret', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Uygula ve mekânları bul', exact: true })).toBeDisabled()
  await expect(page.getByText('Google çağrıları kapalı.', { exact: true })).toBeVisible()
})

test('onaylı prompt ekranı açık ve koyu temada taşmaz', async ({ page }, testInfo) => {
  for (const theme of ['light', 'dark']) {
    if (await page.locator('html').getAttribute('data-theme') !== theme) await page.getByRole('button', { name: /temaya geç/ }).click()
    await previewPreference(page)
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false)
    await page.screenshot({ path: testInfo.outputPath(`prompt-${theme}.png`), fullPage: true })
  }
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

test('doğrulanan linkler koordinat olarak aktarılır ve delta değişince yeniden çözülmez', async ({ page }) => {
  let parses = 0
  let scenarioPayload
  await page.route('**/api/locations/parse', (route) => {
    parses++
    return route.fulfill({ json: [1, 2, 3].map((i) => ({ label: `Katılımcı ${i}`, lat: 39.92, lng: 32.85,
      source: 'google_geocoding', location_input_type: 'geocoded_text', error: null, delta_weight: 1 })) })
  })
  page.on('request', (request) => { if (request.url().endsWith('/api/scenarios')) scenarioPayload = request.postDataJSON() })
  await page.getByRole('button', { name: 'Link ile kişi konumu' }).click()
  const inputs = page.getByLabel('Link veya koordinat', { exact: true })
  for (const input of await inputs.all()) await input.fill('https://www.google.com/maps?q=Ankara')
  await page.getByRole('button', { name: 'Konumları doğrula', exact: true }).click()
  await expect(page.locator('.parse-status.pass')).toHaveCount(3)
  await page.getByLabel('Katılımcı 1 yakınlık ağırlığı').fill('2')
  await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  expect(parses).toBe(1)
  expect(scenarioPayload.participant_locations[0].value).toBe('39.92,32.85')
  expect(scenarioPayload.participant_locations[0].delta_weight).toBe(2)
  await expect(inputs.first()).toHaveValue('https://www.google.com/maps?q=Ankara')
})

test('arama sonrası kota yenilenir; mevcut öneriler yine güncellenebilir', async ({ page }) => {
  let exhausted = false
  let routes = 0
  await page.route('**/api/runtime-config', (route) => route.fulfill({ json: exhausted
    ? { ...runtime, google_available: false, google_remaining_requests: 0, google_unavailable_reason: 'Günlük kota doldu.' }
    : runtime }))
  await page.route('**/api/routes/matrix', async (route) => {
    routes++
    const response = await route.fetch()
    exhausted = true
    await route.fulfill({ response })
  })
  await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  await expect(page.getByRole('button', { name: 'Öneri üret', exact: true })).toBeDisabled()
  await expect(page.getByText(/Günlük kota doldu/)).toBeVisible()
  await page.getByRole('button', { name: /Puan öncelikli/ }).click()
  await expect(page.getByRole('button', { name: 'Güncelle', exact: true })).toBeEnabled()
  expect(routes).toBe(1)
})

test('kesilen rota adımı aynı senaryoyla sürer; aday araması tekrarlanmaz', async ({ page }) => {
  let routes = 0
  let scenarios = 0
  let candidates = 0
  const ids = []
  page.on('request', (request) => {
    if (request.url().endsWith('/api/scenarios') && request.method() === 'POST') scenarios++
    if (request.url().endsWith('/api/candidates/search')) candidates++
  })
  await page.route('**/api/routes/matrix', async (route) => {
    ids.push(route.request().postDataJSON().scenario_id)
    routes++
    if (routes === 1) return route.fulfill({ status: 502, json: { detail: 'Geçici rota hatası.' } })
    const response = await route.fetch()
    return route.fulfill({ response })
  })
  await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Rotaları tamamla', exact: true })).toBeEnabled()
  await expect(page.locator('.recommendation-card')).toHaveCount(0)
  await page.getByRole('button', { name: 'Rotaları tamamla', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  expect(scenarios).toBe(1)
  expect(candidates).toBe(1)
  expect(ids[0]).toBe(ids[1])
})
