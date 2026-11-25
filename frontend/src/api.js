const API_BASE = import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '/api')
const USE_VERCEL_GATEWAY = import.meta.env.VITE_VERCEL_GATEWAY === '1'
let csrfToken = ''
let capabilities = {}

function ensureConditions(value) {
  if (value && (value.budget_limit || value.excluded_categories?.length || value.required_features?.length) && !capabilities.conditions_v1) {
    throw new Error('Bu sunucu kesin koşulları henüz desteklemiyor. Koşullarınızı kaldırmadan güncel sürüme bağlanın.')
  }
}

function ensureContext() {
  if (!capabilities.conditions_v1 || !capabilities.plan_context_v1) throw new Error('Sunucu bağlamı koruyan yorumlama sürümünü henüz desteklemiyor. Manuel kontroller kullanılabilir.')
}

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
  group: () => request('/groups/mine'),
  createGroup: size => request('/groups', { method: 'POST', body: JSON.stringify({size}) }),
  closeGroup: () => request('/groups/mine', { method: 'DELETE' }),
  groupLocations: () => request('/groups/locations', { method: 'POST' }),
  groupBallot: (scenario_id, candidates) => request('/groups/ballot', {method:'POST', body:JSON.stringify({scenario_id,candidates})}),
  guest: body => request('/groups/guest', { method: 'POST', body: JSON.stringify(body) }),
  createRoom: name => request('/groups', { method: 'POST', body: JSON.stringify({ room: true, name }) }),
  saveRoom: name => request('/groups/save', { method: 'POST', body: JSON.stringify({ name }) }),
  renameRoom: name => request('/groups/rename', { method: 'POST', body: JSON.stringify({ name }) }),
  openRoom: key => request('/groups/open', { method: 'POST', body: JSON.stringify({ key }) }),
  forgetRoom: key => request('/groups/forget', { method: 'POST', body: JSON.stringify({ key }) }),
  removeMember: seat => request('/groups/remove', { method: 'POST', body: JSON.stringify({ seat }) }),
  joinRoom: (join, name) => request('/groups/join', { method: 'POST', body: JSON.stringify({ join, name }) }),
  searchPlaces: query => request('/locations/search', { method: 'POST', body: JSON.stringify({ query }) }),
  runtimeConfig: async () => {
    const config = await request('/runtime-config')
    csrfToken = config.csrf_token || ''
    capabilities = config.capabilities || {}
    return config
  },
  deleteScenario: (id) => request(`/scenarios/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  health: () => request('/health'),
  interpretPlan: (body) => { ensureContext(); return request('/plans/interpret', { method: 'POST', body: JSON.stringify(body) }) },
  recommendPlans: (body) => { ensureConditions(body.conditions); return request('/plans/recommend', { method: 'POST', body: JSON.stringify(body) }) },
  parseLocations: (body) =>
    request('/locations/parse', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  interpretPreferences: (body) => {
    ensureContext()
    return request('/preferences/interpret', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },
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
  recommend: (body) => {
    ensureConditions(body.conditions)
    return request('/recommendations', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },
  runExperiment: (body) => {
    ensureConditions(body.conditions)
    return request('/experiments/run', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },
}
