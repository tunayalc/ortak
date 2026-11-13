import type { MobileApi } from './api';
import { assertCompleteMatrix, inputKey, normalizeWeights, validateParticipants } from './domain';
import type { Candidate, ParsedLocation, Preferences, RuntimeConfig, Scenario, SearchInput } from './types';

export type Progress = 'parse' | 'scenario' | 'candidates' | 'routes' | 'recommend';

export class SearchSession {
  scenario: Scenario | null = null;
  candidates: Candidate[] | null = null;
  routesReady = false;
  key = '';
  private validated: { key: string; locations: ParsedLocation[] } | null = null;

  constructor(private api: MobileApi) {}

  async validate(input: SearchInput, max: number): Promise<ParsedLocation[]> {
    validateParticipants(input.participants, max);
    const key = inputKey(input);
    if (this.validated?.key === key) return this.validated.locations;
    const locations = await this.api.parse(input.participants);
    if (locations.length !== input.participants.length) throw new Error('Konumların tümü doğrulanamadı.');
    if (locations.every(p => !p.error && p.lat !== null && p.lng !== null && Number.isFinite(p.lat) && Number.isFinite(p.lng))) this.validated = { key, locations };
    return locations;
  }

  async run(input: SearchInput, preferences: Preferences, config: RuntimeConfig, onProgress: (step: Progress) => void) {
    const key = inputKey(input);
    if (!input.city.trim()) throw new Error('Şehir adını girin.');
    validateParticipants(input.participants, config.max_participants);
    normalizeWeights(preferences.weights);
    if (!Number.isInteger(preferences.k) || preferences.k < 1 || preferences.k > config.max_k) throw new Error('Öneri sayısını kontrol edin.');
    if (this.scenario && key !== this.key) throw new Error('Konumlar değişti. Önce mevcut buluşmayı silip yeni arama başlatın.');
    if (!this.scenario) {
      const capacity = config.google_search_capacity?.resolved_coordinates?.[String(input.participants.length)];
      if (!config.google_available || capacity?.available === false) throw new Error(capacity?.reason || config.google_unavailable_reason || 'Mekân araması şu anda kullanılamıyor.');
      onProgress('parse');
      const parsed = await this.validate(input, config.max_participants);
      if (parsed.some(p => p.error || p.lat === null || p.lng === null || !Number.isFinite(p.lat) || !Number.isFinite(p.lng))) throw new Error('Hatalı kişi konumlarını düzeltin.');
      onProgress('scenario');
      this.scenario = await this.api.create(input, parsed);
      this.key = key;
    }
    if (!this.candidates) {
      onProgress('candidates');
      this.candidates = await this.api.candidates(this.scenario.id, config.max_candidates);
    }
    if (!this.candidates.length) throw new Error('Bu konumlar için uygun mekân bulunamadı. Yeni bir buluşma deneyin.');
    if (!this.routesReady) {
      onProgress('routes');
      const routes = await this.api.routes(this.scenario.id);
      assertCompleteMatrix(this.scenario.users.map(u => u.id), this.candidates, routes);
      this.routesReady = true;
    }
    onProgress('recommend');
    const result = await this.api.recommend(this.scenario.id, input.participants, preferences);
    if (result.recommendations.some(r => !r.constraint_status.complete_route_matrix || r.candidate.provider !== 'google')) throw new Error('Eksik veya doğrulanmamış rota sonucu gösterilmedi.');
    return result;
  }

  async clear() {
    if (this.scenario) await this.api.deleteScenario(this.scenario.id);
    this.forget();
  }

  forget() { this.scenario = null; this.candidates = null; this.routesReady = false; this.key = ''; this.validated = null; }
}
