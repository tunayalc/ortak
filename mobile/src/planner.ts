import { initialPreferences, makeParticipants } from './domain';
import type { Category, CriterionWeights, Preferences, SearchInput } from './types';

export type PlanBrief = {
  city: string; area: string; group_size: number | null; duration_minutes: number;
  budget: 'unspecified' | 'low' | 'flexible'; environment: 'any' | 'indoor' | 'outdoor';
  pace: 'relaxed' | 'active'; interests: string[];
};
export type PlanHandoff = { city: string; group_size: number; category: Category; criterion_weights: CriterionWeights };
export type MeetingPlan = { id: string; title: string; summary: string; reason: string; duration_minutes: number;
  steps: { title: string; minutes: number }[]; checks: string[]; handoff: PlanHandoff };
export type PlanResult = { plans: MeetingPlan[]; questions: string[]; warnings: string[]; source: 'activity_catalog' };
export type PlanInterpretation = { brief: PlanBrief; source: 'ollama'; model: string; warnings: string[] };
export const emptyBrief: PlanBrief = { city: '', area: '', group_size: null, duration_minutes: 120, budget: 'unspecified', environment: 'any', pace: 'relaxed', interests: [] };
export const interests = [['conversation', 'Sohbet'], ['nature', 'Doğa'], ['culture', 'Kültür'], ['food', 'Yemek'], ['study', 'Çalışma'], ['creative', 'Yaratıcılık']] as const;
export const options = {
  budget: [['unspecified', 'Tercih yok'], ['low', 'Ekonomik'], ['flexible', 'Esnek']],
  environment: [['any', 'Fark etmez'], ['indoor', 'Kapalı alan'], ['outdoor', 'Açık alan']],
  pace: [['relaxed', 'Sakin'], ['active', 'Hareketli']],
} as const;

export function planSearchInput(handoff: PlanHandoff, maxParticipants: number): { input: SearchInput; preferences: Preferences } {
  if (!handoff.city?.trim() || handoff.city.length > 80 || !Number.isInteger(handoff.group_size) || handoff.group_size < 2 || handoff.group_size > maxParticipants ||
    !['cafe', 'park', 'library', 'restaurant', 'museum'].includes(handoff.category)) throw new Error('Planın şehir, kişi sayısı veya mekân türü geçersiz.');
  const w = handoff.criterion_weights;
  if (!w || [w.rating, w.cost, w.proximity].some(n => !Number.isFinite(n) || n < 0 || n > 100) || w.rating + w.cost + w.proximity <= 0) throw new Error('Planın kriter ağırlıkları geçersiz.');
  return { input: { city: handoff.city.trim(), category: handoff.category, participants: makeParticipants(handoff.group_size) },
    preferences: { ...initialPreferences, weights: { rating: w.rating, cost: w.cost, proximity: w.proximity } } };
}
