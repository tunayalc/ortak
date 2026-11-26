import { CONSENT_VERSION } from '../src/consent.js'

// Skips the first-launch notice for tests that are about something else.
export async function acceptConsent(page) {
  await page.addInitScript(version => {
    window.localStorage.setItem('ortak-consent', JSON.stringify({ version, accepted_at: '2026-01-01T00:00:00.000Z' }))
    // Most flows test the search itself; start them on sample locations unless a test picks a mode.
    if (!window.localStorage.getItem('ortak-input-mode')) window.localStorage.setItem('ortak-input-mode', 'synthetic')
  }, CONSENT_VERSION)
}

// Opens the "Ayrıntılı ayarlar" section of step 3 (sliders, filters, conditions).
export async function openMore(page) {
  const more = page.locator('details.more-options')
  if (!(await more.evaluate(el => el.open))) await more.locator(':scope > summary').click()
}
