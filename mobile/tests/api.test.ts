import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError, createApi } from '../src/api';
import { initialPreferences, makeParticipants } from '../src/domain';

const response = (body: unknown, status = 200) => Response.json(body, { status });
const session = () => response({ access_token: 'test-only-token', expires_in: 7200, token_type: 'Bearer' });

test('native client uses memory-only bearer auth, never cookies', async () => {
  const calls: RequestInit[] = [];
  const api = createApi('https://api.test/api', async (_, init) => { calls.push(init!); return calls.length === 1 ? session() : response({}); });
  await api.connect(); await api.runtime();
  assert.equal(calls[1]!.credentials, 'omit');
  assert.equal(new Headers(calls[1]!.headers).get('Authorization'), 'Bearer test-only-token');
  assert.equal(new Headers(calls[1]!.headers).get('Cookie'), null);
  assert.equal(new Headers(calls[0]!.headers).get('Authorization'), null);
  api.forget(); await assert.rejects(api.runtime(), (e: ApiError) => e.status === 401);
});
test('session expiry is absolute and mutations are never automatically retried', async () => {
  let time = 0; let calls = 0;
  const api = createApi('https://api.test', async () => ++calls === 1 ? session() : response({ detail: 'Unavailable' }, 502), () => time);
  await api.connect();
  await assert.rejects(api.routes('scenario'));
  assert.equal(calls, 2);
  time = 7200001;
  await assert.rejects(api.routes('scenario'), (e: ApiError) => e.status === 401);
  assert.equal(calls, 2);
});
test('expired connect requires clearing the old scenario before a new identity', async () => {
  let time = 0; let calls = 0;
  const api = createApi('https://api.test', async () => { calls++; return session(); }, () => time);
  await api.connect(); time = 7200001;
  await assert.rejects(api.connect(), (e: ApiError) => e.status === 401);
  assert.equal(calls, 1); assert.equal(api.expiresAt(), 0);
  await api.connect(); assert.equal(calls, 2);
});
test('resolved coordinates sent to scenario; original link remains in form', async () => {
  let body: Record<string, any> = {};
  const api = createApi('https://api.test', async (url, init) => {
    if (String(url).endsWith('/mobile/session')) return session();
    body = JSON.parse(String(init!.body)); return response({});
  });
  await api.connect();
  const people = makeParticipants(2); people[0]!.value = 'https://maps.app.goo.gl/example';
  await api.create({ city: 'Ankara', category: 'cafe', participants: people }, people.map(p => ({ ...p, lat: 39.92, lng: 32.85, error: null })));
  assert.equal(body.participant_locations[0].value, '39.92,32.85');
  assert.equal(body.session_only, true);
  assert.match(people[0]!.value, /^https/);
  await api.interpret('Fiyat önemli olsun.', people, initialPreferences);
  assert.equal('value' in body.participants[0], false);
  assert.equal('lat' in body.participants[0], false);
});
test('HTTP rejected except explicit loopback development, token invalidated on 401', async () => {
  assert.throws(() => createApi('http://api.example.com'));
  assert.throws(() => createApi('https://user:password@api.test'));
  assert.throws(() => createApi('http://192.0.2.1', fetch, Date.now, true));
  createApi('http://127.0.0.1:8013', fetch, Date.now, true);
  let n = 0;
  const api = createApi('https://api.test', async () => ++n === 1 ? session() : response({}, 401));
  await api.connect(); await assert.rejects(api.runtime());
  assert.equal(api.expiresAt(), 0);
});
test('bootstrap is single-flight and does not send to third-party redirects', async () => {
  let n = 0;
  const api = createApi('https://api.test', async (_, init) => { n++; assert.equal(init?.redirect, 'error'); return session(); });
  const first = api.connect(); const second = api.connect();
  await first; await second;
  assert.equal(n, 1);
});
