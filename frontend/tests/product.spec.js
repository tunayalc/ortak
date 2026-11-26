import { test, expect } from '@playwright/test'
import { acceptConsent, openMore } from './helpers.js'

const runtime = { production: true, csrf_token: '', max_participants: 8, max_candidates: 3, max_k: 3, session_ttl_seconds: 7200, google_available: true, google_remaining_requests: 33, capabilities: { conditions_v1: true, plan_context_v1: true } }

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
  await page.getByRole('button', { name: 'Konumları ben gireyim' }).click()
  const fields = page.getByLabel('Yer adı, link veya koordinat', { exact: true })
  for (const [index, coordinate] of ['39.92,32.85', '39.93,32.86', '39.94,32.87'].entries()) {
    await fields.nth(index).fill(coordinate)
  }
}

test.beforeEach(async ({ page }) => {
  await acceptConsent(page)
  await page.route('**/api/runtime-config', (route) => route.fulfill({ json: runtime }))
  await page.route('**/api/health', (route) => route.fulfill({ json: { status: 'ok', google_configured: false, ai_provider: 'ollama', ai_model: 'llama3:8b', ai_ready: true, ai_status: 'ready' } }))
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Buluşma yerini bul', exact: true })).toBeEnabled()
})

test('form, kişi sayısı ve kişi ağırlıkları', async ({ page }) => {
  await page.getByRole('button', { name: 'Konumları ben gireyim' }).click()
  await page.getByLabel('Kişi sayısı', { exact: true }).fill('4')
  await expect(page.getByLabel('Yer adı, link veya koordinat', { exact: true })).toHaveCount(4)
  await expect(page.getByLabel('Katılımcı 4 ağırlığı')).toHaveValue('1')
  await page.getByLabel('Katılımcı 1 ağırlığı').selectOption('2')
  await expect(page.getByLabel('Katılımcı 1 ağırlığı')).toHaveValue('2')
  await expect(page.getByLabel('Öneri sayısı', { exact: true })).toHaveAttribute('max', '3')
})

test('ana form klavye odağını şehirden mekân türüne taşır', async ({ page }) => {
  await page.getByLabel('Şehir', { exact: true }).focus()
  await page.keyboard.press('Tab')
  await expect(page.locator('.venue-picker summary')).toBeFocused()
})

test('hatalı bağlantı öneri akışını durdurur', async ({ page }) => {
  let scenarios = 0
  page.on('request', (request) => { if (request.url().endsWith('/api/scenarios')) scenarios++ })
  await page.getByRole('button', { name: 'Konumları ben gireyim' }).click()
  for (const input of await page.getByLabel('Yer adı, link veya koordinat', { exact: true }).all()) await input.fill('invalid-location')
  await page.getByRole('button', { name: 'Buluşma yerini bul', exact: true }).click()
  await expect(page.locator('.parse-status.fail')).toHaveCount(3)
  expect(scenarios).toBe(0)
})

test('öneriler, profiller, filtre ve boş sonuç', async ({ page }, testInfo) => {
  let routes = 0
  page.on('request', (request) => { if (request.url().endsWith('/api/routes/matrix')) routes++ })
  const recommendation = page.waitForResponse(response =>
    response.url().endsWith('/api/recommendations') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Buluşma yerini bul', exact: true }).click()
  expect((await recommendation).status()).toBe(200)
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  await page.getByRole('button', { name: /Puan öncelikli/ }).click()
  await expect(page.locator('.profile-control .active')).toContainText('Puan öncelikli')
  await expect(page.getByRole('button', { name: 'Güncelle', exact: true })).toBeEnabled()
  expect(routes).toBe(1)
  for (const theme of ['light', 'dark']) {
    await page.evaluate((value) => { document.documentElement.dataset.theme = value }, theme)
    await page.locator('.result-layout').screenshot({ path: testInfo.outputPath(`results-${theme}.png`) })
  }
  await openMore(page)
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
  await page.getByRole('button', { name: 'Buluşma yerini bul', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  await expect(page.locator('.recommendation-card').first()).toContainText('Fiyat bilinmiyor')
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
  await expect(page.getByLabel('Katılımcı 1 ağırlığı')).toHaveValue('1')
  await page.getByRole('button', { name: 'Değerleri uygula' }).click()
  await expect(sliders.nth(1)).toHaveValue('70')
  await expect(page.getByLabel('Katılımcı 1 ağırlığı')).toHaveValue('2')
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
  await page.getByRole('button', { name: 'Buluşma yerini bul', exact: true }).click()
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
  await page.getByRole('button', { name: 'Buluşma yerini bul', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  await page.getByLabel('Yer adı, link veya koordinat', { exact: true }).nth(0).fill('39.95,32.88')
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
  await expect(page.getByText('Google Maps yapılandırıldı', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Buluşma yerini bul', exact: true })).toBeDisabled()
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
  await page.getByRole('button', { name: 'Buluşma yerini bul', exact: true }).click()
  await expect(page.getByText('Günlük kota doldu; yeni çağrı yapılmadı.', { exact: true })).toBeVisible()
  await page.route('**/api/runtime-config', (route) => route.fulfill({ json: { ...runtime, google_available: false, google_unavailable_reason: 'Google işlemleri kapalı.' } }))
  await page.reload()
  await expect(page.getByRole('button', { name: 'Buluşma yerini bul', exact: true })).toBeDisabled()
})

test('açık ve koyu tema, klavye, taşma', async ({ page }, testInfo) => {
  for (const theme of ['light', 'dark']) {
    const current = await page.locator('html').getAttribute('data-theme')
    if (current !== theme) await page.getByRole('button', { name: /temaya geç/ }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
    await page.getByRole('button', { name: 'Konumları ben gireyim' }).click()
    const overflowing = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(overflowing).toBe(false)
    await page.screenshot({ path: testInfo.outputPath(`${theme}.png`), fullPage: true })
  }
  await page.getByLabel('Şehir', { exact: true }).focus()
  await page.keyboard.press('Tab')
  await expect(page.locator('.venue-picker summary')).toBeFocused()
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
  await page.getByRole('button', { name: 'Konumları ben gireyim' }).click()
  const inputs = page.getByLabel('Yer adı, link veya koordinat', { exact: true })
  for (const input of await inputs.all()) await input.fill('https://www.google.com/maps?q=Ankara')
  await page.getByLabel('Katılımcı 1 ağırlığı').selectOption('2')
  await page.getByRole('button', { name: 'Buluşma yerini bul', exact: true }).click()
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
  await page.getByRole('button', { name: 'Buluşma yerini bul', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  await expect(page.getByRole('button', { name: 'Buluşma yerini bul', exact: true })).toBeDisabled()
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
  await page.getByRole('button', { name: 'Buluşma yerini bul', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Rotaları tamamla', exact: true })).toBeEnabled()
  await expect(page.locator('.recommendation-card')).toHaveCount(0)
  await page.getByRole('button', { name: 'Rotaları tamamla', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  expect(scenarios).toBe(1)
  expect(candidates).toBe(1)
  expect(ids[0]).toBe(ids[1])
})

test('birden fazla mekân türü seçilir, en fazla beşte durur ve istekte hepsi gider', async ({ page }) => {
  let body
  await page.route('**/api/scenarios', async route => { body = route.request().postDataJSON(); await route.abort() })
  await page.locator('.venue-picker summary').click()
  for (const name of ['Paintball ve macera sporları', 'Bowling', 'Sinema', 'Karaoke']) await page.getByRole('checkbox', { name, exact: true }).check()
  await expect(page.locator('.venue-picker summary')).toContainText('(5/5)')
  await expect(page.getByRole('checkbox', { name: 'Spa ve hamam', exact: true })).toBeDisabled()
  await page.getByRole('checkbox', { name: 'Kafe', exact: true }).uncheck()
  await expect(page.getByRole('checkbox', { name: 'Spa ve hamam', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Buluşma yerini bul', exact: true }).click()
  await expect.poll(() => body?.categories).toEqual(['paintball', 'bowling', 'cinema', 'karaoke'])
  expect(body.category).toBe('paintball')
})

test('her kişi kendi ulaşım biçimini seçer ve istekte kişiye göre gider', async ({ page }) => {
  let body
  await page.route('**/api/locations/parse', route => route.fulfill({ json: [
    { label: 'Katılımcı 1', lat: 39.92, lng: 32.85, source: 'coordinate', location_input_type: 'coordinate', delta_weight: 1 },
    { label: 'Katılımcı 2', lat: 39.93, lng: 32.86, source: 'coordinate', location_input_type: 'coordinate', delta_weight: 1 },
    { label: 'Katılımcı 3', lat: 39.94, lng: 32.87, source: 'coordinate', location_input_type: 'coordinate', delta_weight: 1 }] }))
  await page.route('**/api/scenarios', async route => { body = route.request().postDataJSON(); await route.abort() })
  await page.getByRole('button', { name: 'Konumları ben gireyim' }).click()
  const fields = page.getByLabel('Yer adı, link veya koordinat', { exact: true })
  await fields.nth(0).fill('39.92,32.85'); await fields.nth(1).fill('39.93,32.86'); await fields.nth(2).fill('39.94,32.87')
  await page.locator('.participant-row .transport-select select').first().selectOption('transit')
  await page.getByRole('button', { name: 'Buluşma yerini bul', exact: true }).click()
  await expect.poll(() => body?.participant_locations?.map(p => p.travel_mode)).toEqual(['transit', null, null])
  expect(body.travel_mode).toBe('driving')
})

test('bir kriter değişince diğer çubuklar da hareket eder ve toplam 100 kalır', async ({ page }) => {
  const sliders = page.locator('.criteria-sliders input[type=range]')
  await openMore(page)
  await sliders.nth(1).fill('10')
  const values = await sliders.evaluateAll(items => items.map(item => Number(item.value)))
  expect(values[1]).toBe(10)
  expect(values.reduce((a, b) => a + b, 0)).toBe(100)
  expect(values[0]).toBeGreaterThan(34)
  expect(values[2]).toBeGreaterThan(33)
})

test('ilk açılışta veri işleme onayı istenir; onay olmadan uygulama açılmaz', async ({ browser }) => {
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto('/')
  await expect(page.getByRole('heading', { name: "ORTAK'a hoş geldiniz" })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Yapay zekâ (Meta Llama 3)' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Google Maps hizmetleri' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Buluşma yerini bul', exact: true })).toHaveCount(0)
  const accept = page.getByRole('button', { name: 'Kabul et ve devam et' })
  await expect(accept).toBeDisabled()
  await page.getByRole('button', { name: 'Kabul etmiyorum' }).click()
  await expect(page.getByText('Onay vermeden ORTAK kullanılamaz')).toBeVisible()
  await page.getByRole('checkbox').check()
  await accept.click()
  await expect(page.getByRole('heading', { name: 'Mekân bul', level: 2 })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: "ORTAK'a hoş geldiniz" })).toHaveCount(0)
  await context.close()
})

test('bir kişinin ulaşımı için rota yoksa hangi kişi olduğu söylenir ve aynı rota tekrar istenmez', async ({ page }) => {
  await page.route('**/api/scenarios', route => route.fulfill({ json: { id: 's-422', city: 'Ankara', category: 'cafe', categories: ['cafe'], group_size: 3, travel_mode: 'transit', radius_m: 2500, seed: 42, session_only: true, input_mode: 'synthetic', users: [1, 2, 3].map(i => ({ id: `user-${i}`, label: `Katılımcı ${i}`, lat: 39.9, lng: 32.8 })) } }))
  await page.route('**/api/candidates/search', route => route.fulfill({ json: [{ id: 'p1', scenario_id: 's-422', place_id: 'g1', name: 'Test Kafe', address: '', category: 'cafe', rating: 4, review_count: 1, lat: 39.9, lng: 32.8, provider: 'google' }] }))
  await page.route('**/api/routes/matrix', route => route.fulfill({ status: 422, json: { detail: 'Katılımcı 1 için toplu taşıma rotası bulunamadı. Bu kişinin ulaşım biçimini değiştirip yeniden arayın.' } }))
  await page.getByRole('button', { name: 'Buluşma yerini bul', exact: true }).click()
  await expect(page.getByText('Katılımcı 1 için toplu taşıma rotası bulunamadı.', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Rotaları tamamla' })).toHaveCount(0)
})
