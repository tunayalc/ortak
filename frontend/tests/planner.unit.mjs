import assert from 'node:assert/strict'
import test from 'node:test'
import { planSearchInput, rebalanceWeights } from '../src/planner.js'
import { categories, MAX_CATEGORIES } from '../src/catalog.js'

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

test('moving one criterion moves the others so the total stays 100', () => {
  const next = rebalanceWeights({ rating: 34, cost: 33, proximity: 33 }, 'cost', 10)
  assert.equal(next.cost, 10)
  assert.equal(next.rating + next.cost + next.proximity, 100)
  assert.ok(next.rating > 34 && next.proximity > 33)
  assert.deepEqual(rebalanceWeights({ rating: 0, cost: 50, proximity: 0 }, 'cost', 20), { rating: 40, cost: 20, proximity: 40 })
  assert.deepEqual(rebalanceWeights({ rating: 34, cost: 33, proximity: 33 }, 'rating', 100), { rating: 100, cost: 0, proximity: 0 })
})
test('catalog offers many event types, grouped, with a selection limit', () => {
  assert.ok(categories.length >= 40 && MAX_CATEGORIES === 5)
  for (const id of ['paintball', 'bowling', 'escape_room', 'go_kart', 'cinema']) assert.ok(categories.some(item => item.id === id))
  assert.equal(planSearchInput({ ...handoff, category: 'paintball' }).category, 'paintball')
})
