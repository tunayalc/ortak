import assert from 'node:assert/strict'
import test from 'node:test'
import { planSearchInput } from '../src/planner.js'

const handoff = { city: ' Ankara ', group_size: 3, category: 'cafe', criterion_weights: { rating: 20, cost: 60, proximity: 20 } }
test('plan transfer creates only a fresh editable draft, not a paid scenario', () => {
  const input = structuredClone(handoff)
  const next = planSearchInput(input)
  assert.equal(next.city, 'Ankara')
  assert.equal(next.participants.length, 3)
  assert.ok(next.participants.every(p => p.value === '' && p.delta_weight === 1))
  assert.deepEqual(input, handoff)
  assert.equal(next.scenario_id, undefined)
  next.weights.rating = 99
  assert.equal(input.criterion_weights.rating, 20)
})
test('plan transfer rejects invalid or over-capacity inputs', () => {
  for (const patch of [{ group_size: 9 }, { group_size: 2.5 }, { category: 'unknown' }, { city: '' }, { criterion_weights: { rating: NaN, cost: 0, proximity: 0 } }]) {
    assert.throws(() => planSearchInput({ ...handoff, ...patch }))
  }
})
