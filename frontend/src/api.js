const API_BASE = import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '/api')
const USE_VERCEL_GATEWAY = import.meta.env.VITE_VERCEL_GATEWAY === '1'
let csrfToken = ''

async function request(path, options = {}) {
  const url = USE_VERCEL_GATEWAY ? `/api/orak-gateway?path=${encodeURIComponent(path)}` : `${API_BASE}${path}`
  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrfToken ? { 'X-ORTAK-CSRF': csrfToken } : {}),
      ...(options.headers || {}),
    },
  })

  const contentType = response.headers.get('content-type') || ''
  const payload = response.status === 204 ? null : contentType.includes('application/json') ? await response.json() : await response.text()

  if (!response.ok) {
    const message = typeof payload === 'string' ? payload : payload.detail || 'Beklenmeyen API hatası'
    const error = new Error(Array.isArray(message) ? message.map((item) => `${item.loc?.slice(1).join(' / ') || 'Girdi'}: ${item.msg}`).join(' ') : message)
    error.status = response.status
    throw error
  }

  return payload
}

export const api = {
  runtimeConfig: async () => {
    const config = await request('/runtime-config')
    csrfToken = config.csrf_token || ''
    return config
  },
  deleteScenario: (id) => request(`/scenarios/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  health: () => request('/health'),
  interpretPlan: (body) => request('/plans/interpret', { method: 'POST', body: JSON.stringify(body) }),
  recommendPlans: (body) => request('/plans/recommend', { method: 'POST', body: JSON.stringify(body) }),
  parseLocations: (body) =>
    request('/locations/parse', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  interpretPreferences: (body) =>
    request('/preferences/interpret', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  createScenario: (body) =>
    request('/scenarios', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  searchCandidates: (body) =>
    request('/candidates/search', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  buildRoutes: (body) =>
    request('/routes/matrix', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  recommend: (body) =>
    request('/recommendations', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  runExperiment: (body) =>
    request('/experiments/run', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}
