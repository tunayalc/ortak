import { CONSENT_VERSION } from './consent';

const KEY = 'ortak-consent';
export type ConsentStorage = { get: (key: string) => Promise<string | null>; set: (key: string, value: string) => Promise<void> };

// Only the notice version and approval time are stored, never names, locations or results.
export async function hasConsent(storage: ConsentStorage): Promise<boolean> {
  try { return (JSON.parse((await storage.get(KEY)) || 'null') as { version?: string } | null)?.version === CONSENT_VERSION; } catch { return false; }
}

export async function saveConsent(storage: ConsentStorage, now: () => Date = () => new Date()): Promise<void> {
  try { await storage.set(KEY, JSON.stringify({ version: CONSENT_VERSION, accepted_at: now().toISOString() })); } catch { /* asked again next launch */ }
}
