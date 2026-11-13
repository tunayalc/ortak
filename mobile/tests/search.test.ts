import assert from 'node:assert/strict';
import test from 'node:test';
import type { MobileApi } from '../src/api';
import { initialPreferences, makeParticipants } from '../src/domain';
import { SearchSession } from '../src/search';
import type { Candidate, RuntimeConfig, SearchInput } from '../src/types';

const config = { max_participants: 8, max_candidates: 3, max_k: 3, google_available: true } as RuntimeConfig;
const input = (): SearchInput => ({ city: 'Ankara', category: 'cafe', participants: makeParticipants(2).map(p => ({ ...p, value: '39.92,32.85' })) });
function fixture() {
  const calls = { parse: 0, create: 0, candidates: 0, routes: 0, recommend: 0, delete: 0 };
  const candidates = [{ id: 'p1', provider: 'google' }] as Candidate[];
  const api = {
    parse: async () => { calls.parse++; return input().participants.map(p => ({ ...p, lat: 39.92, lng: 32.85, error: null })); },
    create: async () => { calls.create++; return { id: 'scenario', users: [{ id: 'user-1' }, { id: 'user-2' }] }; },
    candidates: async () => { calls.candidates++; return candidates; },
    routes: async () => { calls.routes++; return ['user-1', 'user-2'].map(user_id => ({ user_id, candidate_id: 'p1', duration_seconds: 10, distance_meters: 100, provider: 'google' })); },
    recommend: async () => { calls.recommend++; return { recommendations: [] }; },
    deleteScenario: async () => { calls.delete++; },
  } as unknown as MobileApi;
  return { api, calls, session: new SearchSession(api) };
}
test('validation reused; profile/person/filter changes only recalculate', async () => {
  const { calls, session } = fixture(); const value = input();
  await session.validate(value, 8);
  await session.run(value, initialPreferences, config, () => {});
  value.participants[0]!.delta_weight = 2;
  await session.run(value, { ...initialPreferences, weights: { rating: 20, cost: 60, proximity: 20 }, minRating: 4 }, config, () => {});
  assert.deepEqual(calls, { parse: 1, create: 1, candidates: 1, routes: 1, recommend: 2, delete: 0 });
});
test('route interruption resumes same scenario and never ranks partial routes', async () => {
  const { api, calls, session } = fixture(); const real = api.routes;
  api.routes = async () => { calls.routes++; throw new Error('interrupted'); };
  await assert.rejects(session.run(input(), initialPreferences, config, () => {}));
  assert.equal(calls.recommend, 0); assert.equal(session.scenario?.id, 'scenario');
  api.routes = real;
  await session.run(input(), initialPreferences, config, () => {});
  assert.equal(calls.create, 1); assert.equal(calls.candidates, 1); assert.equal(calls.routes, 2);
});
test('quota and invalid weights fail before any paid operation', async () => {
  const { calls, session } = fixture();
  await assert.rejects(session.run(input(), initialPreferences, { ...config, google_available: false }, () => {}));
  await assert.rejects(session.run(input(), { ...initialPreferences, weights: { rating: 0, cost: 0, proximity: 0 } }, config, () => {}));
  assert.equal(Object.values(calls).reduce((a, b) => a + b), 0);
});
test('changing coordinates requires explicit deletion and does not leak previous results', async () => {
  const { calls, session } = fixture();
  await session.run(input(), initialPreferences, config, () => {});
  const changed = input(); changed.participants[0]!.value = '40,33';
  await assert.rejects(session.run(changed, initialPreferences, config, () => {}), /silip/);
  await session.clear(); assert.equal(calls.delete, 1); assert.equal(session.scenario, null);
});
test('expired or offline deletion is never silently reported as success', async () => {
  const { api, session } = fixture();
  await session.run(input(), initialPreferences, config, () => {});
  api.deleteScenario = async () => { throw new Error('offline'); };
  await assert.rejects(session.clear()); assert.ok(session.scenario);
});
