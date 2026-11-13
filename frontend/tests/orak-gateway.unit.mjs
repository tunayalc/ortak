import assert from 'node:assert/strict'
import test from 'node:test'
import gateway, { createGateway } from '../api/orak-gateway.js'

const ORAK = 'https://orak-2209.vercel.app'
const ORACLE = 'https://158.180.36.171.nip.io'
const SCENARIO = '/scenarios/affea414-ff85-43be-8b71-26d2ac205c35'

test('new ORTAK and legacy domains are accepted without allowing other projects', async () => {
  for (const host of ['ortak.web.tr', 'www.ortak.web.tr', 'ortak-2209.vercel.app', 'orak-2209.vercel.app']) {
    const response = await gateway.fetch(new Request(`https://${host}/api/orak-gateway?path=/unsupported`))
    assert.equal(response.status, 404)
  }
  for (const origin of ['https://unrelated.vercel.app', 'https://ortak.web.tr.example.com', 'http://ortak.web.tr']) {
    const other = await gateway.fetch(new Request(`${origin}/api/orak-gateway?path=/health`))
    assert.equal(other.status, 403)
  }
})

test('custom domains preserve same-origin CSRF protection for mutations', async () => {
  for (const origin of ['https://ortak.web.tr', 'https://www.ortak.web.tr']) {
    const response = await gateway.fetch(new Request(`${origin}/api/orak-gateway?path=/scenarios`, {
      method: 'POST', headers: { origin: 'https://unrelated.example', 'x-ortak-csrf': 'token' },
    }))
    assert.equal(response.status, 403)
  }
})

function request(path, init) {
  return new Request(`${ORAK}/api/orak-gateway?path=${encodeURIComponent(path)}`, init)
}

test('runtime config keeps only the host-only session cookie and is not cached', async () => {
  const session = 'ortak_session=signed.value; Secure; HttpOnly; Path=/; SameSite=Lax'
  const gateway = createGateway({ origins: [ORAK], send: async (url, options) => {
    assert.equal(url, `${ORACLE}/api/runtime-config`)
    assert.equal(options.method, 'GET')
    return Response.json({ csrf_token: 'token' }, { headers: [
      ['set-cookie', session],
      ['set-cookie', 'other=value; Path=/'],
      ['set-cookie', 'ortak_session=wrong; Domain=example.com'],
      ['cache-control', 'public, max-age=300'],
    ] })
  } })
  const response = await gateway(request('/runtime-config'))
  assert.equal(response.status, 200)
  assert.deepEqual(response.headers.getSetCookie(), [session])
  assert.equal(response.headers.get('cache-control'), 'no-store')
  assert.deepEqual(await response.json(), { csrf_token: 'token' })
})

test('validated mutations preserve session and CSRF without forwarding unrelated headers', async () => {
  const gateway = createGateway({ origins: [ORAK], send: async (url, { method, headers, body, redirect }) => {
    assert.equal(url, `${ORACLE}/api${method === 'DELETE' ? SCENARIO : '/scenarios'}`)
    assert.equal(headers.get('origin'), ORACLE)
    assert.equal(headers.get('x-ortak-csrf'), 'token')
    assert.equal(headers.get('cookie'), 'ortak_session=signed.value')
    assert.equal(headers.get('authorization'), null)
    assert.equal(headers.get('x-forwarded-for'), null)
    assert.equal(redirect, 'error')
    if (method === 'DELETE') return new Response(null, { status: 204 })
    assert.equal(body.toString(), '{"group_size":3}')
    return Response.json({}, { status: 201 })
  } })
  const headers = {
    origin: ORAK, 'x-ortak-csrf': 'token', 'content-type': 'application/json',
    cookie: 'other=private; ortak_session=signed.value', authorization: 'Bearer private',
    'x-forwarded-for': '192.0.2.1',
  }
  assert.equal((await gateway(request('/scenarios', { method: 'POST', headers, body: '{"group_size":3}' }))).status, 201)
  const removed = await gateway(request(SCENARIO, { method: 'DELETE', headers }))
  assert.equal(removed.status, 204)
  assert.equal(await removed.text(), '')
})

test('invalid origins, paths, CSRF and oversized bodies do not reach Oracle', async () => {
  let requests = 0
  const gateway = createGateway({ origins: [ORAK], send: async () => { requests += 1 } })
  const jsonHeaders = { origin: ORAK, 'x-ortak-csrf': 'token', 'content-type': 'application/json' }
  assert.equal((await gateway(new Request('https://example.com/api/orak-gateway?path=/health'))).status, 403)
  assert.equal((await gateway(request('/scenarios/../health'))).status, 404)
  assert.equal((await gateway(new Request(`${ORAK}/api/orak-gateway?path=/health&path=/readyz`))).status, 404)
  assert.equal((await gateway(request('/routes/matrix'))).status, 404)
  assert.equal((await gateway(request('/scenarios', { method: 'POST', headers: { ...jsonHeaders, origin: 'https://example.com' } }))).status, 403)
  assert.equal((await gateway(request('/scenarios', { method: 'POST', headers: { origin: ORAK } }))).status, 403)
  assert.equal((await gateway(request('/scenarios', { method: 'POST', headers: { ...jsonHeaders, 'content-type': 'text/plain' } }))).status, 415)
  assert.equal((await gateway(request('/scenarios', { method: 'POST', headers: jsonHeaders, body: 'x'.repeat(65537) }))).status, 413)
  assert.equal(requests, 0)
})

test('upstream limits are preserved and connection details are not exposed', async () => {
  const limited = createGateway({ origins: [ORAK], send: async () =>
    Response.json({ detail: 'Kota doldu.' }, { status: 429, headers: { 'retry-after': '60' } }),
  })
  const response = await limited(request('/runtime-config'))
  assert.equal(response.status, 429)
  assert.equal(response.headers.get('retry-after'), '60')
  assert.deepEqual(await response.json(), { detail: 'Kota doldu.' })

  const offline = createGateway({ origins: [ORAK], send: async () => { throw new Error('internal details') } })
  const failure = await offline(request('/health'))
  assert.equal(failure.status, 502)
  assert.doesNotMatch(await failure.text(), /internal details/)
})

test('independent planner routes use the same session and CSRF protection', async () => {
  const sent = []
  const gateway = createGateway({ origins: [ORAK], send: async (url) => { sent.push(url); return Response.json({}) } })
  for (const path of ['/plans/interpret', '/plans/recommend']) {
    assert.equal((await gateway(request(path, { method: 'POST', headers: { origin: ORAK } }))).status, 403)
    assert.equal((await gateway(request(path, { method: 'POST', headers: { origin: ORAK, 'x-ortak-csrf': 'token', 'content-type': 'application/json' }, body: '{}' }))).status, 200)
  }
  assert.deepEqual(sent, [`${ORACLE}/api/plans/interpret`, `${ORACLE}/api/plans/recommend`])
})
