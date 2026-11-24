import { categoryIds, categoryNames } from './catalog';
import type { UserConditions } from './types';

export function validateConditions(value?: UserConditions): void {
  if (!value) return;
  const b = value.budget_limit;
  if (b && (!Number.isFinite(b.amount) || b.amount <= 0 || b.amount > 10_000_000 || b.currency !== 'TRY' || !['group', 'per_person'].includes(b.scope))) throw new Error('Bütçe tutarı veya kapsamı geçersiz.');
  if (!Array.isArray(value.excluded_categories) || value.excluded_categories.some(id => !categoryIds.includes(id)) ||
    !Array.isArray(value.required_features) || value.required_features.some(id => !['quiet', 'accessible', 'alcohol_free'].includes(id))) throw new Error('Kesin koşullar doğrulanamadı.');
}

export function conditionLines(value?: UserConditions): string[] {
  if (!value) return [];
  const lines: string[] = [];
  const names = categoryNames;
  const features = { quiet: 'Sessizlik', accessible: 'Erişilebilirlik', alcohol_free: 'Alkolsüz mekân' };
  if (value.budget_limit) {
    const b = value.budget_limit;
    lines.push(`${b.scope === 'group' ? 'Tüm grup için toplam' : 'Kişi başına'} ${b.amount} TL. Fiyat uygunluğu henüz doğrulanmadı.`);
  }
  if (value.excluded_categories.length) lines.push(`Hariç: ${value.excluded_categories.map(id => names[id]).join(', ')}`);
  if (value.required_features.length) lines.push(`Zorunlu: ${value.required_features.map(id => features[id]).join(', ')}. Kaynakta doğrulanamıyor.`);
  return lines;
}
