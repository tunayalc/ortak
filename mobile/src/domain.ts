import type { Candidate, CriterionWeights, Participant, Preferences, RouteMetric, SearchInput, Suggestion } from './types';

export const categories = [
  { id: 'cafe', label: 'Kafe' }, { id: 'restaurant', label: 'Restoran' },
  { id: 'library', label: 'Kütüphane' }, { id: 'park', label: 'Park' }, { id: 'museum', label: 'Müze' },
] as const;
export const profiles = [
  { label: 'Dengeli', weights: { rating: 34, cost: 33, proximity: 33 } },
  { label: 'Puan', weights: { rating: 60, cost: 20, proximity: 20 } },
  { label: 'Fiyat', weights: { rating: 20, cost: 60, proximity: 20 } },
  { label: 'Yakınlık', weights: { rating: 20, cost: 20, proximity: 60 } },
];
export const initialPreferences: Preferences = { weights: { rating: 34, cost: 33, proximity: 33 }, minRating: null, maxMinutes: null, k: 3 };
export const makeParticipants = (count: number): Participant[] => Array.from({ length: count }, (_, i) => ({ label: `Kişi ${i + 1}`, value: '', delta_weight: 1 }));

export function normalizeWeights(weights: CriterionWeights): CriterionWeights {
  const values = [weights.rating, weights.cost, weights.proximity];
  if (values.some(n => !Number.isFinite(n) || n < 0) || values.every(n => n === 0)) {
    throw new Error('En az bir seçim kriterinin ağırlığı sıfırdan büyük olmalı.');
  }
  const sum = values.reduce((a, b) => a + b, 0);
  if (!Number.isFinite(sum)) throw new Error('Kriter ağırlıklarının toplamı geçersiz.');
  return { rating: weights.rating / sum, cost: weights.cost / sum, proximity: weights.proximity / sum };
}

export function validateParticipants(participants: Participant[], max = 8): void {
  if (participants.length < 2 || participants.length > max) throw new Error(`2 ile ${max} arasında kişi ekleyin.`);
  for (const [i, person] of participants.entries()) {
    if (!person.label.trim() || person.label.length > 80) throw new Error(`${i + 1}. kişinin adını kontrol edin.`);
    if (!person.value.trim() || person.value.length > 2048) throw new Error(`${i + 1}. kişinin konumunu girin.`);
    if (!Number.isFinite(person.delta_weight) || person.delta_weight < 0.5 || person.delta_weight > 2) {
      throw new Error('Kişi yakınlık ağırlığı 0,5 ile 2 arasında olmalı.');
    }
  }
}

export function inputKey(input: SearchInput): string {
  // Preference changes reuse the same Google matrix; location/name changes do not.
  return JSON.stringify([input.city.trim(), input.category, input.participants.map(p => [p.label.trim(), p.value.trim()])]);
}

export function participantWeights(participants: Participant[]): Record<string, number> {
  return Object.fromEntries(participants.map((p, i) => [`user-${i + 1}`, p.delta_weight]));
}

export function validateSuggestion(value: Suggestion, participants: Participant[]): Suggestion {
  const weights = normalizeWeights(value.criterion_weights);
  const expected = participants.map((_, i) => `user-${i + 1}`);
  const actual = Object.keys(value.participant_proximity_weights);
  if (actual.length !== expected.length || expected.some(id => !actual.includes(id))) throw new Error('Model kişi listesini doğru yorumlayamadı. Manuel ayarları kullanın.');
  if (Object.values(value.participant_proximity_weights).some(n => !Number.isFinite(n) || n < 0.5 || n > 2)) throw new Error('Model geçersiz kişi ağırlığı döndürdü.');
  if ((value.min_rating !== null && (!Number.isFinite(value.min_rating) || value.min_rating < 0 || value.min_rating > 5)) ||
      (value.max_duration_minutes !== null && (!Number.isFinite(value.max_duration_minutes) || value.max_duration_minutes < 1))) throw new Error('Model geçersiz filtre döndürdü.');
  return { ...value, criterion_weights: { rating: weights.rating * 100, cost: weights.cost * 100, proximity: weights.proximity * 100 } };
}

export function assertCompleteMatrix(users: string[], candidates: Candidate[], routes: RouteMetric[]): void {
  if (!candidates.length || candidates.some(c => c.provider !== 'google')) throw new Error('Doğrulanmış Google mekânı bulunamadı.');
  const pairs = new Set(routes.filter(r => r.provider === 'google' && Number.isFinite(r.duration_seconds) && r.duration_seconds >= 0 && Number.isFinite(r.distance_meters) && r.distance_meters >= 0).map(r => `${r.user_id}:${r.candidate_id}`));
  if (users.some(id => candidates.some(c => !pairs.has(`${id}:${c.id}`)))) throw new Error('Bazı rotalar tamamlanamadı. Yeniden denediğinizde yalnızca eksik rotalar hesaplanır.');
}

export function destinationOnlyUrl(url: string): string {
  const parsed = new URL(url);
  if (parsed.protocol !== 'https:' || parsed.hostname !== 'www.google.com' || parsed.pathname !== '/maps/dir/' || parsed.username || parsed.password || parsed.port) throw new Error('Yol tarifi bağlantısı doğrulanamadı.');
  if (!parsed.searchParams.get('destination')) throw new Error('Hedef konum eksik.');
  const safe = new URL('https://www.google.com/maps/dir/');
  for (const key of ['destination', 'destination_place_id', 'travelmode']) {
    const value = parsed.searchParams.get(key);
    if (value) safe.searchParams.set(key, value);
  }
  safe.searchParams.set('api', '1');
  return safe.toString();
}

export function priceLabel(price: number | null): string {
  return price === null ? 'Fiyat bilinmiyor; nötr kabul edildi.' : ['Ücretsiz', 'Ekonomik', 'Orta fiyat', 'Yüksek fiyat', 'Çok yüksek fiyat'][price] || 'Fiyat bilinmiyor; nötr kabul edildi.';
}
