import assert from 'node:assert/strict';
import test from 'node:test';
import { planSearchInput, type PlanHandoff } from '../src/planner';

const handoff: PlanHandoff = { city: 'Ankara', group_size: 3, category: 'cafe', criterion_weights: { rating: 20, cost: 60, proximity: 20 } };
test('optional plan handoff is a clean draft, with no coordinates or stale filters', () => {
  const next = planSearchInput(handoff, 8);
  assert.equal(next.input.city, 'Ankara');
  assert.equal(next.input.participants.length, 3);
  assert.ok(next.input.participants.every(p => p.value === '' && p.delta_weight === 1));
  assert.equal(next.preferences.minRating, null);
  assert.equal(next.preferences.maxMinutes, null);
  assert.deepEqual(next.preferences.weights, handoff.criterion_weights);
  next.preferences.weights.cost = 90;
  assert.equal(handoff.criterion_weights.cost, 60);
});
test('plan handoff rejects unsupported group and invalid weights', () => {
  assert.throws(() => planSearchInput({ ...handoff, group_size: 9 }, 8));
  assert.throws(() => planSearchInput({ ...handoff, criterion_weights: { rating: NaN, cost: 1, proximity: 1 } }, 8));
});
