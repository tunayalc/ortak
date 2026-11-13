import assert from 'node:assert/strict';
import test from 'node:test';
import { assertCompleteMatrix, destinationOnlyUrl, inputKey, makeParticipants, normalizeWeights, participantWeights, priceLabel, validateParticipants, validateSuggestion } from '../src/domain';
import type { Candidate, SearchInput, Suggestion } from '../src/types';

test('criterion weights normalize; zero, negative and non-finite rejected', () => {
  assert.deepEqual(normalizeWeights({ rating: 2, cost: 1, proximity: 1 }), { rating: 0.5, cost: 0.25, proximity: 0.25 });
  for (const rating of [-1, Infinity, NaN]) assert.throws(() => normalizeWeights({ rating, cost: 1, proximity: 1 }));
  assert.throws(() => normalizeWeights({ rating: 0, cost: 0, proximity: 0 }));
  assert.throws(() => normalizeWeights({ rating: 1e308, cost: 1e308, proximity: 1e308 }));
});
test('balanced people reset and 2x preference retain independent person ids', () => {
  const people = makeParticipants(3);
  assert.deepEqual(participantWeights(people), { 'user-1': 1, 'user-2': 1, 'user-3': 1 });
  people[0]!.delta_weight = 2;
  assert.equal(participantWeights(people)['user-1'], 2);
});
test('location/name changes invalidate matrix; delta changes do not', () => {
  const input: SearchInput = { city: 'Ankara', category: 'cafe', participants: makeParticipants(3) };
  const key = inputKey(input);
  input.participants[0]!.delta_weight = 2;
  assert.equal(inputKey(input), key);
  input.participants[0]!.value = '39.92,32.85';
  assert.notEqual(inputKey(input), key);
});
test('participant limits, empty locations and infinite delta rejected', () => {
  const people = makeParticipants(3);
  assert.throws(() => validateParticipants(people));
  people.forEach(p => p.value = '39.92,32.85');
  validateParticipants(people);
  assert.throws(() => validateParticipants(people, 2));
  people[1]!.delta_weight = Infinity;
  assert.throws(() => validateParticipants(people));
});
test('AI suggestion is a preview and must match every known person', () => {
  const people = makeParticipants(2);
  const suggestion: Suggestion = { criterion_weights: { rating: 20, cost: 60, proximity: 20 }, participant_proximity_weights: { 'user-1': 2, 'user-2': 1 }, min_rating: null, max_duration_minutes: null, explanation: '', warnings: [], source: 'ollama', model: 'llama3:8b' };
  assert.equal(validateSuggestion(suggestion, people).participant_proximity_weights['user-1'], 2);
  assert.equal(people[0]!.delta_weight, 1);
  assert.throws(() => validateSuggestion({ ...suggestion, participant_proximity_weights: { stranger: 2 } }, people));
  assert.throws(() => validateSuggestion({ ...suggestion, min_rating: 6 }, people));
});
test('destination links strip origins and other location parameters', () => {
  const result = new URL(destinationOnlyUrl('https://www.google.com/maps/dir/?api=1&destination=39.9,32.8&origin=private&waypoints=private&destination_place_id=place-1'));
  assert.equal(result.searchParams.get('origin'), null);
  assert.equal(result.searchParams.get('waypoints'), null);
  assert.equal(result.searchParams.get('destination_place_id'), 'place-1');
  for (const url of ['javascript:alert(1)', 'https://www.google.com.evil.test/maps/dir/?destination=x', 'https://user@www.google.com/maps/dir/?destination=x']) assert.throws(() => destinationOnlyUrl(url));
});
test('full genuine-provider route matrix required; partial or synthetic is not success', () => {
  const candidates = [{ id: 'p1', provider: 'google' }] as Candidate[];
  const route = { user_id: 'user-1', candidate_id: 'p1', duration_seconds: 60, distance_meters: 100, provider: 'google' };
  assertCompleteMatrix(['user-1'], candidates, [route]);
  assert.throws(() => assertCompleteMatrix(['user-1', 'user-2'], candidates, [route]));
  assert.throws(() => assertCompleteMatrix(['user-1'], candidates, [{ ...route, provider: 'synthetic' }]));
  assert.throws(() => assertCompleteMatrix(['user-1'], candidates, [{ ...route, duration_seconds: NaN }]));
});
test('unknown prices are neutral, not free', () => {
  assert.match(priceLabel(null), /nötr/);
  assert.equal(priceLabel(0), 'Ücretsiz');
});
