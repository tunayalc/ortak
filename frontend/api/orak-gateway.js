const ORACLE_ORIGIN = 'https://158.180.36.171.nip.io'
const MAX_BODY_BYTES = 65536
const GET_PATHS = new Set(['/health', '/readyz', '/runtime-config'])
const POST_PATHS = new Set([
  '/locations/parse', '/preferences/interpret', '/scenarios', '/candidates/search',
  '/routes/matrix', '/recommendations', '/experiments/run',
  '/plans/interpret', '/plans/recommend',
])
const SCENARIO_PATH = /^\/scenarios\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/
const RESPONSE_HEADERS = ['content-type', 'retry-after', 'x-ortak-google-calls', 'x-ortak-google-retries', 'x-ortak-google-elapsed-ms']
const PRIVATE_HEADERS = { 'Cache-Control': 'no-store', 'Vercel-CDN-Cache-Control': 'no-store' }

function error(status, detail) {
  return Response.json({ detail }, { status, headers: PRIVATE_HEADERS })
}

function isAllowed(method, path) {
  if (method === 'GET') return GET_PATHS.has(path) || SCENARIO_PATH.test(path)
  if (method === 'POST') return POST_PATHS.has(path)
  return method === 'DELETE' && SCENARIO_PATH.test(path)
}

async function readBody(request) {
  const chunks = []
  let size = 0
  for await (const chunk of request.body || []) {
    size += chunk.byteLength
    if (size > MAX_BODY_BYTES) throw new RangeError('body_limit')
    chunks.push(chunk)
  }
  return Buffer.concat(chunks, size)
}

export function createGateway({ origins, send = fetch }) {
  const allowedOrigins = new Set(origins)
  return async (request) => {
    const url = new URL(request.url)
    const [path, ...extras] = url.searchParams.getAll('path')
    if (!allowedOrigins.has(url.origin)) return error(403, 'İstek kaynağı doğrulanamadı.')
    if (!path || extras.length || !isAllowed(request.method, path)) return error(404, 'Bu API yolu bulunamadı.')

    const headers = new Headers({ Accept: 'application/json' })
    const cookies = (request.headers.get('cookie') || '').split(';').map((part) => part.trim())
    const session = cookies.find((part) => /^ortak_session=[a-zA-Z0-9._+/=-]+$/.test(part))
    if (session) headers.set('cookie', session)

    if (request.method !== 'GET') {
      if (request.headers.get('origin') !== url.origin) return error(403, 'İstek kaynağı doğrulanamadı.')
      const csrf = request.headers.get('x-ortak-csrf')
      if (!csrf) return error(403, 'Oturum doğrulaması gerekli. Sayfayı yenileyin.')
      // Oracle still verifies the signed session and CSRF token after this origin check.
      headers.set('origin', ORACLE_ORIGIN)
      headers.set('x-ortak-csrf', csrf)
    }

    let body
    if (request.method === 'POST') {
      if (request.headers.get('content-type')?.split(';', 1)[0].trim().toLowerCase() !== 'application/json') {
        return error(415, 'İstek JSON biçiminde olmalıdır.')
      }
      headers.set('content-type', 'application/json')
      try {
        body = await readBody(request)
      } catch (cause) {
        if (cause instanceof RangeError) return error(413, 'İstek boyutu izin verilen sınırı aşıyor.')
        return error(400, 'İstek okunamadı.')
      }
    }

    try {
      const upstream = await send(`${ORACLE_ORIGIN}/api${path}`, {
        method: request.method, headers, body, redirect: 'error', signal: AbortSignal.timeout(145_000),
      })
      const outgoing = new Headers(PRIVATE_HEADERS)
      for (const name of RESPONSE_HEADERS) {
        const value = upstream.headers.get(name)
        if (value !== null) outgoing.set(name, value)
      }
      for (const cookie of upstream.headers.getSetCookie()) {
        if (/^ortak_session=/.test(cookie) && !/;\s*domain=/i.test(cookie)) outgoing.append('set-cookie', cookie)
      }
      return new Response(upstream.body, { status: upstream.status, headers: outgoing })
    } catch {
      return error(502, 'Uygulama servisine şu anda ulaşılamıyor. Biraz sonra tekrar deneyin.')
    }
  }
}

const deploymentOrigins = [
  'https://ortak.web.tr',
  'https://www.ortak.web.tr',
  'https://ortak-2209.vercel.app',
  'https://orak-2209.vercel.app',
  ...[process.env.VERCEL_URL, process.env.VERCEL_PROJECT_PRODUCTION_URL]
    .filter((host) => /^[a-z0-9-]+\.vercel\.app$/.test(host || ''))
    .map((host) => `https://${host}`),
]

export default { fetch: createGateway({ origins: deploymentOrigins }) }
