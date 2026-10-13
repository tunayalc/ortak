import { chromium, expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const base = process.env.ORTAK_LIVE_URL || 'https://92.5.80.85.nip.io/'
if (new URL(base).protocol !== 'https:') throw new Error('Read-only production checks require HTTPS.')
const report = { started_at_utc: new Date().toISOString(), status: 'running',
  source_commit: process.env.ORTAK_LIVE_COMMIT || '', checks: {}, stages: [], google_calls: 0,
  llama_generation_calls: 0, uses_mocks: false }
const output = resolve(process.env.ORTAK_LIVE_OUTPUT || '../output/deployment/live-readiness', 'run.json')
await mkdir(resolve(output, '..'), { recursive: true, mode: 0o700 })
await writeFile(output, JSON.stringify(report, null, 2), { mode: 0o600, flag: 'wx' })
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
let runtime
let health
let phase = 'health_and_capacity'
const pending = new Set()
page.on('response', response => {
  const path = new URL(response.url()).pathname
  if (!path.startsWith('/api/')) return
  const task = (async () => {
    const headers = await response.allHeaders()
    report.google_calls += Number(headers['x-ortak-google-calls'] || 0)
    report.stages.push({ path, method: response.request().method(), http_status: response.status() })
    if (path === '/api/runtime-config') runtime = await response.json()
    if (path === '/api/health') health = await response.json()
    if (path === '/api/preferences/interpret') report.llama_generation_calls++
  })()
  pending.add(task)
  task.finally(() => pending.delete(task))
})
function check(name, value) { report.checks[name] = Boolean(value); expect(Boolean(value), name).toBe(true) }
try {
  await page.goto(base)
  await expect(page.getByRole('button', { name: 'Model bağlantısını yenile' })).toBeEnabled({ timeout: 15000 })
  while (pending.size) await Promise.all([...pending])
  check('production_health', runtime.production && health.status === 'ok' && health.ai_ready && health.ai_model === 'llama3:8b')
  check('normal_retry_and_budget_restored', health.google_usage.max_attempts_per_request === 2 && health.google_usage.budget_enforced && health.google_usage.budget_limit_tl === 100)
  const capacity = runtime.google_search_capacity.synthetic['3']
  check('search_button_matches_live_capacity', await page.getByRole('button', { name: 'Öneri üret', exact: true }).isEnabled() === Boolean(runtime.google_available && capacity.available))
  if (!capacity.available) await expect(page.locator('.control-band').getByRole('status')).toContainText(capacity.reason)
  phase = 'keyboard_navigation'
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
    await page.getByLabel('Şehir', { exact: true }).focus()
    await page.keyboard.press('Tab')
    await expect(page.getByLabel('Mekân türü')).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByLabel('Grup', { exact: true })).toBeFocused()
    check(`keyboard_${width}`, true)
  }
  check('zero_charge_read_only', report.google_calls === 0 && report.llama_generation_calls === 0
    && report.stages.every(stage => stage.method === 'GET' && stage.http_status === 200))
  report.status = 'passed'
} catch {
  report.status = 'failed'
  report.failed_stage = phase
} finally {
  await browser.close()
  report.finished_at_utc = new Date().toISOString()
  await writeFile(output, JSON.stringify(report, null, 2), { mode: 0o600 })
}
console.log(JSON.stringify(report))
process.exitCode = report.status === 'passed' ? 0 : 1
