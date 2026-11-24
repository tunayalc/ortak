import { CONSENT_VERSION } from '../src/consent.js'

// Skips the first-launch notice for tests that are about something else.
export async function acceptConsent(page) {
  await page.addInitScript(version => {
    window.localStorage.setItem('ortak-consent', JSON.stringify({ version, accepted_at: '2026-01-01T00:00:00.000Z' }))
  }, CONSENT_VERSION)
}
