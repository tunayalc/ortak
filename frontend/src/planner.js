import { categoryIds } from './catalog.js'

export const emptyBrief = {
  city: '', area: '', group_size: null, duration_minutes: 120,
  budget: 'unspecified', environment: 'any', pace: 'relaxed', interests: [],
  conditions: { budget_limit: null, excluded_categories: [], required_features: [] },
}
export const planInterests = [
  ['conversation', 'Sohbet'], ['nature', 'Doğa'], ['culture', 'Kültür'],
  ['food', 'Yemek'], ['study', 'Çalışma'], ['creative', 'Yaratıcılık'],
  ['entertainment', 'Eğlence'], ['adventure', 'Macera ve spor'],
]
export const planOptions = {
  budget: [['unspecified', 'Tercih yok'], ['low', 'Ekonomik'], ['flexible', 'Esnek']],
  environment: [['any', 'Fark etmez'], ['indoor', 'Kapalı alan'], ['outdoor', 'Açık alan']],
  pace: [['relaxed', 'Sakin'], ['active', 'Hareketli']],
}

export function planSearchInput(handoff, maxParticipants = 8) {
  if (!handoff || !handoff.city?.trim() || handoff.city.length > 80 ||
    !Number.isInteger(handoff.group_size) || handoff.group_size < 2 || handoff.group_size > maxParticipants ||
    !categoryIds.includes(handoff.category)) {
    throw new Error('Planın şehir, kişi sayısı veya mekân türü geçersiz.')
  }
  const weights = handoff.criterion_weights
  if (!weights || ['rating', 'cost', 'proximity'].some(key => !Number.isFinite(weights[key]) || weights[key] < 0 || weights[key] > 100) ||
    weights.rating + weights.cost + weights.proximity <= 0) throw new Error('Planın tercih ağırlıkları geçersiz.')
  return {
    city: handoff.city.trim(), category: handoff.category, group_size: handoff.group_size,
    weights: { rating: weights.rating, cost: weights.cost, proximity: weights.proximity },
    conditions: checkedConditions(handoff.conditions),
    participants: Array.from({ length: handoff.group_size }, (_, i) => ({ label: `Katılımcı ${i + 1}`, value: '', delta_weight: 1 })),
  }
}

export function checkedConditions(value) {
  const conditions = value || { budget_limit: null, excluded_categories: [], required_features: [] }
  const budget = conditions.budget_limit
  if (budget && (!Number.isFinite(budget.amount) || budget.amount <= 0 || budget.amount > 10_000_000 ||
    budget.currency !== 'TRY' || !['group', 'per_person'].includes(budget.scope))) throw new Error('TL bütçesini ve kapsamını kontrol edin.')
  if (!Array.isArray(conditions.excluded_categories) || conditions.excluded_categories.some(id => !categoryIds.includes(id)) ||
    !Array.isArray(conditions.required_features) || conditions.required_features.some(id => !['quiet', 'accessible', 'alcohol_free'].includes(id))) throw new Error('Kesin koşullar doğrulanamadı.')
  return structuredClone(conditions)
}

export const travelModes = [
  { value: 'driving', label: 'Araç' },
  { value: 'transit', label: 'Toplu taşıma' },
  { value: 'walking', label: 'Yürüme' },
  { value: 'bicycling', label: 'Bisiklet' },
]

// Moving one criterion keeps the three weights summing to 100, so the other sliders
// follow the change in the same proportion instead of only their "effective" share changing.
export function rebalanceWeights(weights, key, value) {
  const keys = Object.keys(weights)
  const next = Math.max(0, Math.min(100, Math.round(Number(value) || 0)))
  const others = keys.filter(item => item !== key)
  const rest = 100 - next
  const otherTotal = others.reduce((sum, item) => sum + Number(weights[item] || 0), 0)
  const result = { [key]: next }
  let used = 0
  others.forEach((item, index) => {
    if (index === others.length - 1) { result[item] = rest - used; return }
    const share = otherTotal > 0 ? Math.round(rest * Number(weights[item] || 0) / otherTotal) : Math.round(rest / others.length)
    result[item] = Math.min(rest - used, share)
    used += result[item]
  })
  return Object.fromEntries(keys.map(item => [item, result[item]]))
}
