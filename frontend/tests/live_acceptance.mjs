import { chromium, expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

if (process.env.ORTAK_LIVE_ACCEPTANCE !== '1' || process.env.ORTAK_LIVE_MAX_TOTAL_TL !== '100') {
  throw new Error('Explicit live acceptance opt-in and the existing 100 TL guard are required.')
}
const base = process.env.ORTAK_LIVE_URL || 'https://92.5.80.85.nip.io/'
if (new URL(base).protocol !== 'https:') throw new Error('Live acceptance requires HTTPS.')
const output = resolve(process.env.ORTAK_LIVE_OUTPUT || '../output/deployment/browser-live', 'run.json')
const report = { started_at_utc: new Date().toISOString(), status: 'running', checks: {}, stages: [],
  source_commit: process.env.ORTAK_LIVE_COMMIT || '', budget_limit_tl: 100, planned_google_calls: 10,
  expected_reservation_tl: 11.25, uses_mocks: false }
await mkdir(resolve(output, '..'), { recursive: true, mode: 0o700 })
await writeFile(output, JSON.stringify(report, null, 2), { mode: 0o600, flag: 'wx' })
let saveQueue = Promise.resolve()
function save() {
  const snapshot = JSON.stringify(report, null, 2)
  saveQueue = saveQueue.then(() => writeFile(output, snapshot, { mode: 0o600 }))
  return saveQueue
}
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage()
const pending = new Set()
const bodies = new Map()
const startTimes = new Map()
let phase = 'preflight'
let scenarioId
let csrf = ''
let candidateData = []
let routeData = []
const allowed = new Set(['/api/health', '/api/runtime-config', '/api/locations/parse', '/api/preferences/interpret',
  '/api/scenarios', '/api/candidates/search', '/api/routes/matrix', '/api/recommendations'])
page.on('request', request => startTimes.set(request, Date.now()))
page.on('response', response => {
  const path = new URL(response.url()).pathname
  if (!allowed.has(path)) return
  const task = (async () => {
    const request = response.request()
    const headers = await response.allHeaders()
    report.stages.push({ path, method: request.method(), http_status: response.status(),
      seconds: (Date.now() - startTimes.get(request)) / 1000,
      google_calls: Number(headers['x-ortak-google-calls'] || 0),
      google_retries: Number(headers['x-ortak-google-retries'] || 0) })
    if (response.ok()) {
      const data = await response.json()
      bodies.set(path, data)
      if (path === '/api/scenarios') scenarioId = data.id
      if (path === '/api/runtime-config') csrf = data.csrf_token
      if (path === '/api/candidates/search') candidateData = data
      if (path === '/api/routes/matrix') routeData = data
      if (path === '/api/preferences/interpret') {
        const participants = request.postDataJSON().participants
        report.checks.locations_not_sent_to_model = participants.every(person => !('lat' in person) && !('lng' in person) && !('value' in person))
      }
    }
    await save()
  })().catch(() => { report.checks.response_metadata = false })
  pending.add(task)
  task.finally(() => pending.delete(task))
})
async function settle() { while (pending.size) await Promise.all([...pending]) }
function check(name, value) { report.checks[name] = Boolean(value); expect(Boolean(value), name).toBe(true) }
function calls() { return report.stages.reduce((n, stage) => n + stage.google_calls, 0) }
async function recommendationAction(action) {
  const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/recommendations')
  await action()
  expect((await response).status()).toBe(200)
  await settle()
  const result = bodies.get('/api/recommendations')
  check('score_components', result.recommendations.every(row =>
    Math.abs(row.score - ['rating_component', 'cost_component', 'proximity_component']
      .reduce((n, key) => n + row.score_breakdown[key], 0)) <= .001))
  return result
}
try {
  await page.goto(base)
  await expect(page.getByRole('button', { name: 'Model bağlantısını yenile' })).toBeEnabled({ timeout: 15000 })
  await settle()
  const health = bodies.get('/api/health')
  const runtime = bodies.get('/api/runtime-config')
  check('production_ready', runtime.production && health.ai_ready && health.ai_provider === 'ollama' && health.ai_model === 'llama3:8b')
  check('budget_and_retry_guard', health.google_usage.budget_enforced && health.google_usage.budget_limit_tl === 100 && health.google_usage.max_attempts_per_request === 1)
  check('capacity_ready', runtime.google_search_capacity.resolved_coordinates['3'].available && runtime.google_remaining_requests >= 10)
  await page.getByRole('button', { name: 'Link ile kişi konumu' }).click()
  const coordinates = ['39.92,32.85', '39.93,32.86', '39.94,32.87']
  for (let i = 0; i < 3; i++) {
    await page.getByLabel('Kişi', { exact: true }).nth(i).fill(`Kişi ${i + 1}`)
    await page.getByLabel('Link veya koordinat', { exact: true }).nth(i).fill(coordinates[i])
  }
  phase = 'llama_preview'
  await page.getByLabel('Seçim isteği').fill("Fiyat uygunluğu daha önemli olsun; Kişi 1'e yakınlık iki kat önemli olsun.")
  await page.getByRole('button', { name: 'Tercihi yorumla', exact: true }).click()
  await expect(page.getByText('Önerilen değerler', { exact: true })).toBeVisible({ timeout: 125000 })
  await settle()
  const suggestion = bodies.get('/api/preferences/interpret')
  check('locations_not_sent_to_model', report.checks.locations_not_sent_to_model)
  check('llama_within_120_seconds', report.stages.find(s => s.path === '/api/preferences/interpret').seconds <= 120)
  check('real_llama_preferences', suggestion.source === 'ollama' && suggestion.model === 'llama3:8b'
    && suggestion.criterion_weights.cost === 70 && suggestion.criterion_weights.rating === 34 && suggestion.criterion_weights.proximity === 33
    && suggestion.participant_proximity_weights['user-1'] === 2 && suggestion.participant_proximity_weights['user-2'] === 1 && suggestion.participant_proximity_weights['user-3'] === 1)
  await expect(page.locator('.criteria-sliders input').nth(1)).toHaveValue('33')
  await expect(page.getByLabel('Kişi 1 yakınlık ağırlığı')).toHaveValue('1')
  check('preview_requires_confirmation', calls() === 0)
  phase = 'paid_search'
  await page.getByRole('button', { name: 'Uygula ve mekânları bul', exact: true }).click()
  await expect(page.locator('.recommendation-card')).toHaveCount(3, { timeout: 240000 })
  await expect(page.getByRole('button', { name: 'Güncelle', exact: true })).toBeEnabled()
  await settle()
  check('three_google_candidates', candidateData.length === 3 && candidateData.every(c => c.provider === 'google'))
  check('complete_google_matrix', routeData.length === 9 && new Set(routeData.map(r => `${r.user_id}:${r.candidate_id}`)).size === 9
    && routeData.every(r => r.provider === 'google' && Number.isFinite(r.duration_seconds) && r.duration_seconds >= 0 && Number.isFinite(r.distance_meters)))
  const first = bodies.get('/api/recommendations')
  check('initial_score_components', first.recommendations.every(row => Math.abs(row.score - row.score_breakdown.rating_component - row.score_breakdown.cost_component - row.score_breakdown.proximity_component) <= .001))
  check('person_weights_applied', first.recommendations.every(r => r.constraint_status.complete_route_matrix
    && r.score_breakdown.proximity_contributions.every(p => Math.abs(p.weight - (p.user_id === 'user-1' ? .5 : .25)) <= .001)))
  check('ten_google_calls', calls() === 10 && report.stages.every(s => s.google_retries === 0))
  const links = await page.getByRole('link', { name: 'Yol tarifi', exact: true }).evaluateAll(nodes => nodes.map(node => node.href))
  check('destination_only_links', links.length === 3 && links.every(href => {
    const url = new URL(href)
    return url.hostname.endsWith('google.com') && url.searchParams.has('destination') && !url.searchParams.has('origin')
  }))
  phase = 'preference_reuse'
  for (const name of ['Puan öncelikli', 'Fiyat öncelikli', 'Yakınlık öncelikli', 'Dengeli']) {
    await recommendationAction(() => page.getByRole('button', { name: new RegExp(`^${name}`) }).click())
  }
  await recommendationAction(() => page.getByRole('button', { name: 'Kişiler dengeli', exact: true }).click())
  await page.getByLabel('Kişi 1 yakınlık ağırlığı').fill('2')
  await recommendationAction(() => page.getByRole('button', { name: 'Güncelle', exact: true }).click())
  await page.getByLabel('En az puan', { exact: true }).fill('5')
  await page.getByLabel('En fazla süre (dk)', { exact: true }).fill('1')
  const filtered = await recommendationAction(() => page.getByRole('button', { name: 'Güncelle', exact: true }).click())
  check('filters_applied', filtered.recommendations.every(r => r.candidate.rating >= 5 && r.t_max_minutes <= 1))
  await page.getByLabel('En az puan', { exact: true }).fill('')
  await page.getByLabel('En fazla süre (dk)', { exact: true }).fill('')
  await recommendationAction(() => page.getByRole('button', { name: 'Güncelle', exact: true }).click())
  await expect(page.locator('.recommendation-card')).toHaveCount(3)
  check('no_rebilling_for_preferences', calls() === 10 && report.stages.filter(s => s.path === '/api/routes/matrix').length === 1 && report.stages.filter(s => s.path === '/api/candidates/search').length === 1)
  phase = 'responsive_layout'
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
    for (const theme of ['light', 'dark']) {
      if (await page.locator('html').getAttribute('data-theme') !== theme) await page.getByRole('button', { name: /temaya geç/ }).click()
      check(`layout_${width}_${theme}`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1))
      await expect(page.locator('.recommendation-card')).toHaveCount(3)
    }
  }
  phase = 'keyboard_navigation'
  await page.getByLabel('Şehir', { exact: true }).focus()
  await page.keyboard.press('Tab')
  await expect(page.getByLabel('Mekân türü')).toBeFocused()
  check('keyboard_navigation', true)
  check('http_success', report.stages.every(s => s.http_status === 200))
  check('all_recorded_checks', Object.values(report.checks).every(Boolean))
  report.status = 'passed'
} catch {
  report.status = 'failed'
  report.failed_stage = phase
} finally {
  await settle()
  if (scenarioId) {
    const response = await context.request.delete(new URL(`/api/scenarios/${scenarioId}`, base).href,
      { headers: { Origin: new URL(base).origin, 'X-ORTAK-CSRF': csrf } }).catch(() => null)
    report.session_cleanup_verified = response?.status() === 204
    if (!report.session_cleanup_verified) {
      report.status = 'failed'
      report.failed_stage = 'session_cleanup'
    }
  }
  await browser.close()
  report.google_calls = calls()
  report.finished_at_utc = new Date().toISOString()
  await save()
}
console.log(JSON.stringify({ status: report.status, checks: report.checks, google_calls: report.google_calls, failed_stage: report.failed_stage }))
process.exitCode = report.status === 'passed' ? 0 : 1
