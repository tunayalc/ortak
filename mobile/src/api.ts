import type { Candidate, FeedbackReason, Health, ParsedLocation, Participant, Preferences, RecommendationResponse, RouteMetric, RuntimeConfig, Scenario, SearchInput, Suggestion } from './types';
import { normalizeWeights, participantWeights } from './domain';
import type { PlanBrief, PlanInterpretation, PlanResult } from './planner';

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export function createApi(baseUrl: string, send: typeof fetch = fetch, now = Date.now, allowLocalHttp = false) {
  const base = new URL(baseUrl);
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(base.hostname);
  if ((base.protocol !== 'https:' && !(allowLocalHttp && local && base.protocol === 'http:')) || base.username || base.password || base.search || base.hash) throw new Error('API adresi güvenli bir HTTPS adresi olmalı.');
  const root = baseUrl.replace(/\/$/, '');
  let token = '';
  let expiresAt = 0;
  let opening: Promise<void> | null = null;

  async function raw<T>(path: string, method: string, body?: unknown, authenticated = true): Promise<T> {
    const abort = new AbortController();
    const timeout = setTimeout(() => abort.abort(), ['/preferences/interpret', '/plans/interpret'].includes(path) ? 145_000 : 120_000);
    try {
      const response = await send(`${root}${path}`, {
        method, signal: abort.signal, credentials: 'omit', redirect: 'error',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...(authenticated ? { Authorization: `Bearer ${token}` } : {}) },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (response.status === 204) return undefined as T;
      const json = response.headers.get('content-type')?.includes('application/json');
      const value = json ? await response.json() : null;
      if (!response.ok) {
        if (response.status === 401) { token = ''; expiresAt = 0; }
        const detail = typeof value?.detail === 'string' ? value.detail : null;
        throw new ApiError(detail || (response.status === 422 ? 'Girdiğiniz bilgileri kontrol edin.' : path === '/mobile/session' && response.status === 404 ? 'Sunucuda mobil bağlantı henüz etkin değil.' : 'İşlem tamamlanamadı. Biraz sonra yeniden deneyin.'), response.status);
      }
      if (!json) throw new ApiError('Sunucudan geçerli bir yanıt alınamadı.', response.status);
      return value as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(abort.signal.aborted ? 'İşlem zaman aşımına uğradı. Otomatik olarak tekrar gönderilmedi.' : 'Sunucuya ulaşılamıyor. İnternet bağlantınızı kontrol edin.', 0);
    } finally { clearTimeout(timeout); }
  }

  async function connect() {
    if (token) {
      if (now() < expiresAt) return;
      token = ''; expiresAt = 0;
      // The controller must clear the previous scenario before opening another identity.
      throw new ApiError('Mobil oturumun süresi doldu. Bağlantıyı yenileyip yeni bir buluşma oluşturun.', 401);
    }
    if (!opening) opening = (async () => {
      const result = await raw<{ access_token: string; expires_in: number; token_type: string }>('/mobile/session', 'POST', {}, false);
      if (!result.access_token || result.token_type !== 'Bearer' || !Number.isFinite(result.expires_in) || result.expires_in <= 0 || result.expires_in > 7200) throw new ApiError('Mobil oturum doğrulanamadı.', 0);
      token = result.access_token;
      expiresAt = now() + result.expires_in * 1000;
    })().finally(() => { opening = null; });
    await opening;
  }

  async function request<T>(path: string, body?: unknown, method = body === undefined ? 'GET' : 'POST'): Promise<T> {
    if (!token || now() >= expiresAt) throw new ApiError('Oturumun süresi doldu. Yeni bir buluşma oluşturun.', 401);
    return raw<T>(path, method, body);
  }

  return {
    connect,
    expiresAt: () => expiresAt,
    forget: () => { token = ''; expiresAt = 0; },
    runtime: () => request<RuntimeConfig>('/runtime-config'),
    health: () => request<Health>('/health'),
    interpretPlan: (text: string, current: PlanBrief) => request<PlanInterpretation>('/plans/interpret', { text, current }),
    recommendPlans: (brief: PlanBrief) => request<PlanResult>('/plans/recommend', brief),
    parse: (participants: Participant[]) => request<ParsedLocation[]>('/locations/parse', { items: participants }),
    create: (input: SearchInput, parsed: ParsedLocation[]) => request<Scenario>('/scenarios', {
      city: input.city.trim(), category: input.category, group_size: input.participants.length,
      input_mode: 'link', session_only: true, travel_mode: 'driving', radius_m: 2500,
      participant_locations: parsed.map((p, i) => ({ label: input.participants[i]!.label.trim(), value: `${p.lat},${p.lng}`, delta_weight: input.participants[i]!.delta_weight })),
    }),
    candidates: (id: string, maximum: number) => request<Candidate[]>('/candidates/search', { scenario_id: id, max_results: maximum }),
    routes: (id: string) => request<RouteMetric[]>('/routes/matrix', { scenario_id: id, provider: 'google' }),
    recommend: (id: string, participants: Participant[], preferences: Preferences) => request<RecommendationResponse>('/recommendations', {
      scenario_id: id, scoring_mode: 'criteria_delta', k: preferences.k,
      criterion_weights: normalizeWeights(preferences.weights), participant_proximity_weights: participantWeights(participants),
      min_rating: preferences.minRating, max_duration_minutes: preferences.maxMinutes, use_adjusted_durations: false,
    }),
    interpret: (text: string, participants: Participant[], preferences: Preferences) => request<Suggestion>('/preferences/interpret', {
      text: text.trim(), participants: participants.map((p, i) => ({ id: `user-${i + 1}`, label: p.label, delta_weight: p.delta_weight })),
      criterion_weights: preferences.weights, min_rating: preferences.minRating, max_duration_minutes: preferences.maxMinutes,
    }),
    report: (reason: FeedbackReason, weights: Suggestion['criterion_weights']) => request<{ id: string }>('/mobile/feedback', { reason, criterion_weights: normalizeWeights(weights) }),
    deleteScenario: (id: string) => request<void>(`/scenarios/${encodeURIComponent(id)}`, undefined, 'DELETE'),
  };
}
export type MobileApi = ReturnType<typeof createApi>;
