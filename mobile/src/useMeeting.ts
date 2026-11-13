import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';
import { ApiError, createApi } from './api';
import { initialPreferences, makeParticipants, validateSuggestion } from './domain';
import { SearchSession, type Progress } from './search';
import { planSearchInput, type PlanHandoff } from './planner';
import type { FeedbackReason, Health, ParsedLocation, Preferences, RecommendationResponse, RuntimeConfig, SearchInput, Suggestion } from './types';

const labels: Record<Progress, string> = { parse: 'Konumlar doğrulanıyor', scenario: 'Buluşma hazırlanıyor', candidates: 'Mekânlar aranıyor', routes: 'Yol süreleri hesaplanıyor', recommend: 'Öneriler sıralanıyor' };
const base = process.env.EXPO_PUBLIC_API_BASE_URL || 'https://158.180.36.171.nip.io/api';

export function useMeeting() {
  const [api] = useState(() => createApi(base, fetch, Date.now, __DEV__));
  const [session] = useState(() => new SearchSession(api));
  const [input, setInput] = useState<SearchInput>({ city: 'Ankara', category: 'cafe', participants: makeParticipants(3) });
  const [preferences, setPreferences] = useState<Preferences>(initialPreferences);
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [parsed, setParsed] = useState<ParsedLocation[]>([]);
  const [results, setResults] = useState<RecommendationResponse | null>(null);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [text, setText] = useState('');
  const [consent, setConsent] = useState(false);
  const [aiConsent, setAiConsent] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [resultSignature, setResultSignature] = useState('');
  const lock = useRef(false);
  const lastRecalculation = useRef('');
  const signature = JSON.stringify([preferences, input.participants.map(p => p.delta_weight)]);

  const clearMemory = useCallback(() => {
    session.forget(); setResults(null); setParsed([]); setSuggestion(null); setText('');
    setInput({ city: 'Ankara', category: 'cafe', participants: makeParticipants(3) });
    setPreferences(initialPreferences); setConsent(false); setAiConsent(false); setResultSignature('');
    lastRecalculation.current = '';
  }, [session]);

  const task = useCallback(async (label: string, operation: () => Promise<void>) => {
    if (lock.current) return;
    lock.current = true; setBusy(label); setError(''); setNotice('');
    try { await operation(); }
    catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { clearMemory(); api.forget(); setConfig(null); }
      setError(cause instanceof Error ? cause.message : 'İşlem tamamlanamadı.');
    } finally { lock.current = false; setBusy(''); }
  }, [api, clearMemory]);

  const refresh = useCallback(() => task('Bağlantı kontrol ediliyor', async () => {
    await api.connect(); setConfig(await api.runtime());
    try { setHealth(await api.health()); }
    catch (cause) {
      setHealth(null);
      if (cause instanceof ApiError && cause.status === 401) throw cause;
    }
  }), [api, task]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const check = () => {
      if (api.expiresAt() && Date.now() >= api.expiresAt() && !lock.current) {
        clearMemory(); api.forget(); setConfig(null); setError('Oturum süresi doldu; kişi konumları ve sonuçlar bu cihazdan temizlendi.');
      }
    };
    const interval = setInterval(check, 15_000);
    const subscription = AppState.addEventListener('change', state => { if (state === 'active') check(); });
    return () => { clearInterval(interval); subscription.remove(); };
  }, [api, clearMemory]);

  useEffect(() => {
    setSuggestion(null);
  }, [preferences, input.participants, text]);

  useEffect(() => {
    if (!session.routesReady || !session.scenario || busy || signature === resultSignature || signature === lastRecalculation.current || !results) return;
    const timer = setTimeout(() => {
      lastRecalculation.current = signature;
      void task('Öneriler güncelleniyor', async () => {
        const updated = await api.recommend(session.scenario!.id, input.participants, preferences);
        setResults(updated); setResultSignature(signature);
      });
    }, 300);
    return () => clearTimeout(timer);
  }, [api, busy, input.participants, preferences, resultSignature, results, session, signature, task]);

  const validate = () => task('Konumlar doğrulanıyor', async () => {
    if (!consent) throw new Error('Konum paylaşımını onaylayın.');
    if (!config) throw new Error('Önce sunucu bağlantısını yenileyin.');
    const locations = await session.validate(input, config.max_participants);
    setParsed(locations);
    if (locations.some(p => p.error)) throw new Error('İşaretlenen kişi konumlarını düzeltin.');
    setNotice('Tüm kişi konumları doğrulandı.');
  });

  const search = () => task('Buluşma hazırlanıyor', async () => {
    if (!consent) throw new Error('Konum paylaşımını onaylayın.');
    await api.connect();
    const fresh = await api.runtime(); setConfig(fresh);
    try {
      const found = await session.run(input, preferences, fresh, step => setBusy(labels[step]));
      setResults(found); setResultSignature(signature);
    } finally {
      try { setConfig(await api.runtime()); } catch { /* Preserve the original operation error. */ }
    }
  });

  const interpret = () => task('Llama tercihlerinizi yorumluyor', async () => {
    if (!aiConsent) throw new Error('Tercih metninin işlenmesini onaylayın.');
    if (text.trim().length < 5 || text.length > 500) throw new Error('Tercihinizi 5 ile 500 karakter arasında yazın.');
    const response = await api.interpret(text, input.participants, preferences);
    setSuggestion(validateSuggestion(response, input.participants));
  });

  const applySuggestion = () => {
    if (!suggestion || lock.current) return;
    setPreferences({ ...preferences, weights: suggestion.criterion_weights, minRating: suggestion.min_rating, maxMinutes: suggestion.max_duration_minutes });
    setInput({ ...input, participants: input.participants.map((p, i) => ({ ...p, delta_weight: suggestion.participant_proximity_weights[`user-${i + 1}`]! })) });
    setSuggestion(null); setText(''); setNotice('İncelediğiniz tercihler uygulandı.');
  };

  const remove = () => task('Buluşma siliniyor', async () => {
    try { await session.clear(); }
    catch (cause) { if (!(cause instanceof ApiError && cause.status === 404)) throw cause; }
    clearMemory(); setNotice('Buluşma verileri temizlendi.');
  });

  const report = (reason: FeedbackReason) => task('Bildirim gönderiliyor', async () => {
    if (!suggestion) return;
    await api.report(reason, suggestion.criterion_weights);
    setSuggestion(null); setNotice('Bildiriminiz alındı. Tercih metni ve kişi konumları bildirime eklenmedi.');
  });

  const transferPlan = async (handoff: PlanHandoff) => {
    let applied = false;
    await task('Plan bilgileri aktarılıyor', async () => {
      const next = planSearchInput(handoff, config?.max_participants || 8);
      try { await session.clear(); }
      catch (cause) { if (!(cause instanceof ApiError && cause.status === 404)) throw cause; }
      clearMemory(); setInput(next.input);
      setPreferences({ ...next.preferences, k: Math.min(next.preferences.k, config?.max_k || 3) });
      setNotice('Plan aktarıldı. Kişi konumlarını girin; henüz Google araması yapılmadı.');
      applied = true;
    });
    return applied;
  };

  return { api, transferPlan, input, setInput, preferences, setPreferences, config, health, parsed, setParsed, results, suggestion, setSuggestion,
    text, setText, consent, setConsent, aiConsent, setAiConsent, busy, error, setError, notice, setNotice,
    refresh, validate, search, interpret, applySuggestion, remove, report,
    hasScenario: Boolean(session.scenario), resultsStale: signature !== resultSignature, routesReady: session.routesReady };
}
export type Meeting = ReturnType<typeof useMeeting>;
