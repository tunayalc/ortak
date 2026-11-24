import assert from 'node:assert/strict';
import test from 'node:test';
import { hasConsent, saveConsent, type ConsentStorage } from '../src/consentStore';

// expo-secure-store is native-only; the tests use an in-memory storage with the same shape.
const memory = (): ConsentStorage & { data: Map<string, string> } => {
  const data = new Map<string, string>();
  return { data, get: async k => data.get(k) ?? null, set: async (k, v) => { data.set(k, v); } };
};
test('approval is remembered by notice version, and only version and time are stored', async () => {
  const store = memory();
  assert.equal(await hasConsent(store), false);
  await saveConsent(store, () => new Date('2026-11-24T10:00:00Z'));
  assert.equal(await hasConsent(store), true);
  const saved = JSON.parse([...store.data.values()][0]!);
  assert.deepEqual(Object.keys(saved).sort(), ['accepted_at', 'version']);
  store.data.set('ortak-consent', JSON.stringify({ version: 'old' }));
  assert.equal(await hasConsent(store), false);
  store.data.set('ortak-consent', '{bozuk');
  assert.equal(await hasConsent(store), false);
});
test('a failing store never throws; the notice is simply asked again', async () => {
  const broken: ConsentStorage = { get: async () => { throw new Error('x'); }, set: async () => { throw new Error('x'); } };
  assert.equal(await hasConsent(broken), false);
  await saveConsent(broken);
});
