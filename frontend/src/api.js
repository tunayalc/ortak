const API_BASE = import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '/api')
let csrfToken = ''

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
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
    throw new Error(Array.isArray(message) ? message.map((item) => `${item.loc?.slice(1).join(' / ') || 'Girdi'}: ${item.msg}`).join(' ') : message)
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
