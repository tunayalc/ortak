import { useEffect, useRef, useState, type ComponentRef } from 'react';
import { AppState, Image, KeyboardAvoidingView, Linking, Modal, Platform, Pressable, ScrollView, Share, View, useColorScheme } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import * as Location from 'expo-location';
import { useNetworkState } from 'expo-network';
import { ArrowRight, CheckCheck, Flag, LocateFixed, MapPin, Moon, Navigation, RefreshCw, Share2, ShieldCheck, SlidersHorizontal, Sparkles, Star, Sun, Trash2, Users, X } from 'lucide-react-native';
import { Button, Consent, Field, Heading, IconButton, Label, Notice, Section, Segmented, Stepper, Text, ThemeContext, Toggle, WeightSlider, styles, useTheme } from './src/components';
import { categories, destinationOnlyUrl, makeParticipants, normalizeWeights, priceLabel, profiles } from './src/domain';
import { dark, light } from './src/theme';
import { useMeeting, type Meeting } from './src/useMeeting';
import { MeetingPlanner } from './src/MeetingPlanner';
import type { CriterionWeights, FeedbackReason, Recommendation } from './src/types';

type Tab = 'Buluşma' | 'Tercihler' | 'Öneriler' | 'Gizlilik';
const tabs = [{ label: 'Buluşma', icon: Users }, { label: 'Tercihler', icon: SlidersHorizontal }, { label: 'Öneriler', icon: MapPin }, { label: 'Gizlilik', icon: ShieldCheck }] as const;
const weightLabels: Record<keyof CriterionWeights, string> = { rating: 'Mekân puanı', cost: 'Fiyat uygunluğu', proximity: 'Kişilere yakınlık' };

export default function App() {
  const scheme = useColorScheme();
  const [appearance, setAppearance] = useState('Sistem');
  const isDark = appearance === 'Koyu' || (appearance === 'Sistem' && scheme === 'dark');
  return <SafeAreaProvider><ThemeContext.Provider value={isDark ? dark : light}>
    <StatusBar style={isDark ? 'light' : 'dark'} /><MobileApp appearance={appearance} setAppearance={setAppearance} isDark={isDark} />
  </ThemeContext.Provider></SafeAreaProvider>;
}

function MobileApp({ appearance, setAppearance, isDark }: { appearance: string; setAppearance: (v: string) => void; isDark: boolean }) {
  const t = useTheme();
  const m = useMeeting();
  const network = useNetworkState();
  const [tab, setTab] = useState<Tab>('Buluşma');
  const [engine, setEngine] = useState('Mekân bul');
  const scroll = useRef<ComponentRef<typeof ScrollView>>(null);
  useEffect(() => { scroll.current?.scrollTo({ y: 0, animated: false }); }, [tab, engine]);
  useEffect(() => { if (m.error) scroll.current?.scrollTo({ y: 0, animated: false }); }, [m.error]);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [locating, setLocating] = useState<number | null>(null);
  const [locationConsent, setLocationConsent] = useState<number | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [privateCover, setPrivateCover] = useState(false);
  useEffect(() => {
    const sub = AppState.addEventListener('change', state => setPrivateCover(state !== 'active'));
    return () => sub.remove();
  }, []);
  const offline = network.isConnected === false || network.isInternetReachable === false;
  const disabled = Boolean(m.busy) || locating !== null;

  async function useLocation(index: number) {
    setLocationConsent(null); setLocating(index); m.setError('');
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (!permission.granted) throw new Error('Konum izni verilmedi. Harita linki veya koordinat girebilirsiniz.');
      if (!(await Location.hasServicesEnabledAsync())) throw new Error('Cihazın konum servisleri kapalı. Link veya koordinat girebilirsiniz.');
      let timeout: ReturnType<typeof setTimeout> | undefined;
      try {
        const position = await Promise.race([
          Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }),
          new Promise<never>((_, reject) => { timeout = setTimeout(() => reject(new Error('Konum alınamadı. Link veya koordinat girebilirsiniz.')), 20_000); }),
        ]);
        m.setInput(current => ({ ...current, participants: current.participants.map((p, i) => i === index ? { ...p, value: `${position.coords.latitude.toFixed(6)},${position.coords.longitude.toFixed(6)}` } : p) }));
        m.setParsed([]);
      } finally { clearTimeout(timeout); }
    } catch (cause) { m.setError(cause instanceof Error ? cause.message : 'Konum alınamadı.'); }
    finally { setLocating(null); }
  }

  async function openUrl(url: string) {
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== 'https:' || parsed.username || parsed.password) throw new Error();
      await Linking.openURL(url);
    } catch { m.setError('Bağlantı açılamadı. Daha sonra yeniden deneyin.'); }
  }

  async function search() {
    await m.search();
    setTab('Öneriler');
  }

  return <SafeAreaView style={{ flex: 1, backgroundColor: t.background }} edges={['top', 'bottom', 'left', 'right']}>
    <View style={{ flex: 1, width: '100%', maxWidth: 760, alignSelf: 'center' }}>
      <View style={{ paddingHorizontal: 20, paddingVertical: 16, flexDirection: 'row', gap: 10, alignItems: 'center', borderBottomWidth: 1, borderBottomColor: t.divider }}>
        <Image source={require('./assets/splash-icon.png')} style={{ width: 34, height: 34, borderRadius: 2 }} accessible={false} />
        <View style={{ flex: 1 }}><Text style={{ color: t.text, fontSize: 28, fontWeight: '400', letterSpacing: 0 }}>ORTAK</Text><Text style={{ color: t.secondary, fontSize: 12 }}>Buluşacağımız yer</Text></View>
        <IconButton label={isDark ? 'Açık temaya geç' : 'Koyu temaya geç'} icon={isDark ? Sun : Moon} onPress={() => setAppearance(isDark ? 'Açık' : 'Koyu')} />
        <IconButton label="Bağlantıyı yenile" icon={RefreshCw} onPress={() => void m.refresh()} disabled={disabled || offline} />
      </View>
      <View style={{ paddingHorizontal: 20, paddingVertical: 12 }}><Segmented items={['Mekân bul', 'Buluşma planı']} value={engine} onChange={setEngine} /></View>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView ref={scroll} keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 24 }}>
          {offline && <View style={{ paddingTop: 16 }}><Notice error>İnternet bağlantısı yok. Yeni aramalar gönderilmiyor.</Notice></View>}
          {m.error && engine === 'Mekân bul' ? <View style={{ paddingTop: 16 }}><Notice error>{m.error}</Notice></View> : null}
          {m.notice && engine === 'Mekân bul' ? <View style={{ paddingTop: 16 }}><Notice>{m.notice}</Notice></View> : null}
          {m.busy ? <View style={{ paddingTop: 16 }}><Notice>{m.busy}</Notice></View> : null}
          <MeetingPlanner m={m} active={engine === 'Buluşma planı'} onTransferred={() => { setEngine('Mekân bul'); setTab('Buluşma'); }} />
          <View style={{ display: engine === 'Mekân bul' ? 'flex' : 'none' }}>
          {tab === 'Buluşma' && <>
            <Section><Label>Henüz bir mekân fikriniz yok mu?</Label><Button label="Buluşma planı oluştur" icon={Sparkles} tone="secondary" onPress={() => setEngine('Buluşma planı')} /></Section>
            <Section><Heading>Mekân bul</Heading>
              <Field label="Şehir" value={m.input.city} maxLength={80} editable={!disabled && !m.hasScenario} onChangeText={city => m.setInput({ ...m.input, city })} />
              <Label>Mekân türü</Label><Segmented items={categories.map(c => c.label)} value={categories.find(c => c.id === m.input.category)!.label} disabled={disabled || m.hasScenario}
                onChange={label => m.setInput({ ...m.input, category: categories.find(c => c.label === label)!.id })} />
              <Stepper label="Kişi sayısı" min={2} max={m.config?.max_participants || 8} value={m.input.participants.length} disabled={disabled || m.hasScenario}
                onChange={count => { m.setInput({ ...m.input, participants: Array.from({ length: count }, (_, i) => m.input.participants[i] || makeParticipants(count)[i]!) }); m.setParsed([]); }} />
            </Section>
            <Section><View style={styles.between}><Heading>Kişi konumları</Heading><Users color={t.accent} size={22} /></View>
              <Button label="Kişiler dengeli" icon={CheckCheck} tone="secondary" disabled={disabled} onPress={() => m.setInput({ ...m.input, participants: m.input.participants.map(p => ({ ...p, delta_weight: 1 })) })} />
              {m.input.participants.map((person, index) => <View key={index} style={{ padding: 16, borderWidth: 1, borderColor: t.divider, borderRadius: 2, backgroundColor: t.surface, gap: 16 }}>
                <Field label={`${index + 1}. kişinin adı`} value={person.label} maxLength={80} editable={!disabled && !m.hasScenario}
                  onChangeText={label => { m.setInput({ ...m.input, participants: m.input.participants.map((p, i) => i === index ? { ...p, label } : p) }); m.setParsed([]); }} />
                <Field label={`${index + 1}. kişinin konumu`} placeholder="Google Maps linki veya enlem,boylam" value={person.value} autoCapitalize="none" maxLength={2048} editable={!disabled && !m.hasScenario}
                  onChangeText={value => { m.setInput({ ...m.input, participants: m.input.participants.map((p, i) => i === index ? { ...p, value } : p) }); m.setParsed([]); }} />
                {!m.hasScenario && <Button label={locating === index ? 'Konum alınıyor' : `Konumumu ${person.label} için kullan`} icon={LocateFixed} tone="secondary" disabled={disabled} onPress={() => setLocationConsent(index)} />}
                <Stepper label={`${person.label} yakınlık ağırlığı`} min={0.5} max={2} step={0.5} suffix="×" value={person.delta_weight} disabled={disabled}
                  onChange={delta_weight => m.setInput({ ...m.input, participants: m.input.participants.map((p, i) => i === index ? { ...p, delta_weight } : p) })} />
                {m.parsed[index] ? <Notice error={!!m.parsed[index]!.error}>{m.parsed[index]!.error || 'Konum doğrulandı.'}</Notice> : null}
              </View>)}
              <Notice>Konumlar oturumluk işlenir ve en geç iki saatte sunucudan silinir. Ham linkler kalıcı kaydedilmez.</Notice>
              <Consent label="Bu kişilerin konumlarını paylaşma iznim var. Konumların buluşma ve rota hesabı için Google Maps ile işlenmesini kabul ediyorum." checked={m.consent} disabled={disabled || m.hasScenario} onChange={m.setConsent} />
              {!m.hasScenario && <Button label="Konumları doğrula" icon={CheckCheck} tone="secondary" onPress={() => void m.validate()} disabled={disabled || offline || !m.consent || !m.config} />}
            </Section>
            <Section><Button label="Tercihlere geç" icon={ArrowRight} onPress={() => setTab('Tercihler')} disabled={disabled} />
              {m.hasScenario && <Button label="Yeni buluşma için mevcut verileri sil" icon={Trash2} tone="danger" disabled={disabled} onPress={() => setConfirmDelete(true)} />}
            </Section>
          </>}

          {tab === 'Tercihler' && <>
            <Section><Heading>Seçim kriterleri</Heading>
              <Segmented items={profiles.map(p => p.label)} disabled={disabled} value={profiles.find(p => JSON.stringify(p.weights) === JSON.stringify(m.preferences.weights))?.label || ''}
                onChange={label => m.setPreferences({ ...m.preferences, weights: { ...profiles.find(p => p.label === label)!.weights } })} />
              {(Object.keys(weightLabels) as Array<keyof CriterionWeights>).map(key => <WeightSlider key={key} label={weightLabels[key]} value={m.preferences.weights[key]} disabled={disabled}
                onChange={value => m.setPreferences({ ...m.preferences, weights: { ...m.preferences.weights, [key]: value } })} />)}
              <WeightSummary weights={m.preferences.weights} />
              <Stepper label="Öneri sayısı" min={1} max={m.config?.max_k || 3} value={m.preferences.k} disabled={disabled} onChange={k => m.setPreferences({ ...m.preferences, k })} />
              <Toggle label="En düşük mekân puanı" value={m.preferences.minRating !== null} disabled={disabled} onChange={on => m.setPreferences({ ...m.preferences, minRating: on ? 4 : null })} />
              {m.preferences.minRating !== null && <Stepper label="Minimum puan" min={0} max={5} step={0.5} value={m.preferences.minRating} disabled={disabled} onChange={minRating => m.setPreferences({ ...m.preferences, minRating })} />}
              <Toggle label="Kişi başına süre sınırı" value={m.preferences.maxMinutes !== null} disabled={disabled} onChange={on => m.setPreferences({ ...m.preferences, maxMinutes: on ? 30 : null })} />
              {m.preferences.maxMinutes !== null && <Stepper label="En fazla dakika" min={5} max={240} step={5} value={m.preferences.maxMinutes} disabled={disabled} onChange={maxMinutes => m.setPreferences({ ...m.preferences, maxMinutes })} />}
              <Label secondary>Fiyat seviyesi gerçek bir TL tutarı değildir. Yol süreleri araçla ulaşım içindir; kişi ağırlıkları yalnızca yakınlık tercihini değiştirir.</Label>
            </Section>
            <Section><View style={styles.between}><Heading>İsteğini anlat</Heading><Sparkles color={t.primary} size={22} /></View>
              <Label secondary>{m.health?.ai_ready ? `Sunucudaki model: ${m.health.ai_model}` : 'Yapay zekâ hazır değilse manuel tercihler kullanılabilir.'}</Label>
              <Field label="Buluşma tercihiniz" multiline numberOfLines={4} maxLength={500} value={m.text} editable={!disabled} onChangeText={m.setText}
                placeholder="Fiyat önemli; Kişi 1'e iki kat yakın olsun." style={{ minHeight: 112, textAlignVertical: 'top' }} />
              <Consent label="Tercih metnimin sunucudaki Llama modeliyle işlenmesini kabul ediyorum. Metne konum, kimlik veya ödeme bilgisi eklemedim." checked={m.aiConsent} disabled={disabled} onChange={m.setAiConsent} />
              <Button label="Tercih önerisi oluştur" icon={Sparkles} tone="secondary" onPress={() => void m.interpret()} disabled={disabled || offline || !m.aiConsent || !m.config || m.health?.ai_ready === false} />
              {m.suggestion && <View style={{ borderLeftWidth: 3, borderLeftColor: t.accent, paddingLeft: 16, gap: 14 }}>
                <Heading>Öneriyi incele</Heading><Label secondary>Bu değerler henüz uygulanmadı.</Label>
                <WeightSummary weights={m.suggestion.criterion_weights} />
                {m.input.participants.map((p, i) => <Label key={i}>{p.label}: {m.suggestion!.participant_proximity_weights[`user-${i + 1}`]}×</Label>)}
                <Label>Minimum puan: {m.suggestion.min_rating ?? 'Sınır yok'} · Süre: {m.suggestion.max_duration_minutes === null ? 'Sınır yok' : `${m.suggestion.max_duration_minutes} dk`}</Label>
                {m.suggestion.warnings.map((warning, i) => <Notice key={i}>{warning}</Notice>)}
                <Button label="Bu tercihleri uygula" icon={CheckCheck} onPress={m.applySuggestion} disabled={disabled} />
                <View style={styles.between}><Button label="Vazgeç" icon={X} tone="secondary" onPress={() => m.setSuggestion(null)} disabled={disabled} /><IconButton label="Yapay zekâ önerisini bildir" icon={Flag} onPress={() => setReportOpen(true)} disabled={disabled} /></View>
              </View>}
              <Label secondary>Built with Meta Llama 3</Label>
            </Section>
            <Section><SearchButton m={m} disabled={disabled || offline} onPress={() => void search()} /></Section>
          </>}

          {tab === 'Öneriler' && <Section>
            <View style={styles.between}><Heading>Buluşma seçenekleri</Heading><MapPin color={t.accent} size={22} /></View>
            {m.resultsStale && m.results ? <Notice>Tercihler değişti; sonuçlar güncellenene kadar önceki sıralama gösteriliyor.</Notice> : null}
            {!m.results && <Label secondary>{m.hasScenario ? 'Arama henüz tamamlanmadı. Başarılı rotalar korunur; yeniden denemede eksikler tamamlanır.' : 'Henüz öneri yok.'}</Label>}
            {m.results && m.results.recommendations.length === 0 ? <Notice>Bu filtrelere uygun mekân bulunamadı. Tercihlerden puan veya süre sınırını değiştirebilirsiniz.</Notice> : null}
            {m.results?.recommendations.map(result => <ResultCard key={result.candidate.id} result={result} isDark={isDark} openUrl={openUrl} onError={m.setError} />)}
            <SearchButton m={m} disabled={disabled || offline} onPress={() => void search()} />
            {m.hasScenario && <Button label="Buluşmayı sil" icon={Trash2} tone="danger" onPress={() => setConfirmDelete(true)} disabled={disabled} />}
          </Section>}

          {tab === 'Gizlilik' && <>
            <Section><Heading>Gizlilik ve oturum</Heading>
              <Label>Üyelik gerekmez. Kişi adları, konumlar, sonuçlar ve mobil erişim anahtarı cihazda yalnızca bellekte tutulur; uygulama bunları dosyaya veya yedeğe yazmaz.</Label>
              <Label>Sunucudaki buluşma verileri en geç iki saatte silinir. Uygulamayı kapatmak sunucudaki verileri anında silmez; aşağıdaki düğmeyle silme isteği gönderebilirsiniz.</Label>
              <Button label="Buluşma verilerimi sil" icon={Trash2} tone="danger" onPress={() => setConfirmDelete(true)} disabled={disabled} />
              <Label>Konumunuz yalnızca ilgili düğmeye bastığınızda alınır. Arka planda konum takibi yapılmaz. Link veya koordinat girişi için konum izni gerekmez.</Label>
              <Label>Google Maps, konum çözümleme, mekân ve yol sürelerini sağlar. Llama, uygulama sunucusunda tercih metnini yorumlar; kişi konumu alanları modele gönderilmez. Reklam veya analitik SDK'sı yoktur.</Label>
              <Label>Hız ve maliyet kayıtları içerik taşımaz. Yapay zekâ bildirimlerinde yalnızca sorun türü ve kriter ağırlıkları 30 gün saklanır; tercih cümlesi veya kişi bilgisi eklenmez.</Label>
              <Button label="Gizlilik politikası" icon={ShieldCheck} tone="secondary" onPress={() => void openUrl('https://ortak-2209.vercel.app/mobile-privacy.html')} />
              <Button label="Kullanım koşulları" tone="secondary" onPress={() => void openUrl('https://ortak-2209.vercel.app/mobile-terms.html')} />
              <Button label="Google gizlilik politikası" tone="secondary" onPress={() => void openUrl('https://policies.google.com/privacy')} />
              <Button label="Destek" tone="secondary" onPress={() => void openUrl('https://github.com/tunayalc/ortak/issues')} />
            </Section>
            <Section><Heading>Görünüm</Heading><Segmented items={['Sistem', 'Açık', 'Koyu']} value={appearance} onChange={setAppearance} /></Section>
            <Section><Heading>Model ve sonuçlar</Heading><Label>ORTAK puan, fiyat ve yakınlık tercihlerinizle sıralama yapar. Yakınlık kuş uçuşu mesafeye göre hesaplanır; yol süreleri ayrı gösterilir. Sonuçlar gerçek ücret, erişilebilirlik veya yol güvenliği garantisi değildir.</Label><Label secondary>ORTAK Mobil 0.1.0 · Built with Meta Llama 3</Label></Section>
          </>}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
      <View accessibilityRole="tablist" style={{ display: engine === 'Mekân bul' ? 'flex' : 'none', flexDirection: 'row', borderTopWidth: 1, borderTopColor: t.divider, backgroundColor: t.surface }}>
        {tabs.map(({ label, icon: Icon }) => <Pressable key={label} accessibilityRole="tab" accessibilityLabel={label} accessibilityState={{ selected: tab === label }} aria-selected={tab === label}
          onPress={() => setTab(label)} style={{ flex: 1, paddingVertical: 12, gap: 5, alignItems: 'center', minHeight: 65, borderTopWidth: 2, borderTopColor: tab === label ? t.primary : 'transparent' }}>
          <Icon color={tab === label ? t.primary : t.secondary} size={22} strokeWidth={tab === label ? 2 : 1.5} /><Text style={{ color: tab === label ? t.primary : t.secondary, fontWeight: tab === label ? '600' : '400', fontSize: 12, textAlign: 'center' }}>{label}</Text>
        </Pressable>)}
      </View>
    </View>
    <Confirmation visible={confirmDelete} title="Buluşma verileri silinsin mi?" onClose={() => setConfirmDelete(false)}>
      <Label>Kişi konumları, tercihler ve sonuçlar bu cihazdan temizlenecek. Kayıtlı buluşma varsa sunucudan da silinecek.</Label>
      <Button label="Verileri sil" icon={Trash2} tone="danger" onPress={() => { setConfirmDelete(false); void m.remove(); }} />
    </Confirmation>
    <Confirmation visible={locationConsent !== null} title="Cihaz konumunu kullan" onClose={() => setLocationConsent(null)}>
      <Label>Konum yalnızca seçtiğiniz kişi satırına eklenir. Buluşma aradığınızda rota hesabı için Google Maps ile paylaşılır. Arka planda takip yapılmaz; izin vermeden link de girebilirsiniz.</Label>
      <Button label="Devam et" icon={LocateFixed} onPress={() => { if (locationConsent !== null) void useLocation(locationConsent); }} />
    </Confirmation>
    <Confirmation visible={reportOpen} title="Öneriyi bildir" onClose={() => setReportOpen(false)}>
      <Label>Yalnızca sorun türü ve kriter ağırlıkları gönderilir; metniniz ve konumlarınız eklenmez.</Label>
      {([['incorrect_preferences', 'Tercihimi yanlış anladı'], ['unsafe_response', 'Uygunsuz yanıt'], ['other', 'Başka bir sorun']] as Array<[FeedbackReason, string]>).map(([reason, label]) =>
        <Button key={reason} label={label} icon={Flag} tone="secondary" onPress={() => { setReportOpen(false); void m.report(reason); }} />)}
    </Confirmation>
    {privateCover && Platform.OS !== 'web' ? <View accessibilityLabel="ORTAK gizlilik ekranı" style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, backgroundColor: t.background, alignItems: 'center', justifyContent: 'center' }}><ShieldCheck size={40} color={t.primary} /><Heading>ORTAK</Heading></View> : null}
  </SafeAreaView>;
}

function SearchButton({ m, disabled, onPress }: { m: Meeting; disabled: boolean; onPress: () => void }) {
  const capacity = m.config?.google_search_capacity?.resolved_coordinates?.[String(m.input.participants.length)];
  const blocked = !m.routesReady && (!m.config?.google_available || (!m.hasScenario && capacity?.available === false));
  return <View style={{ gap: 12 }}>{blocked && m.config ? <Notice error>{capacity?.reason || m.config.google_unavailable_reason || 'Mekân araması şu anda kullanılamıyor.'}</Notice> : null}
    <Button label={m.routesReady ? 'Sonuçları güncelle' : m.hasScenario ? 'Eksik adımları tamamla' : 'Buluşma yeri bul'} icon={MapPin} onPress={onPress} loading={!!m.busy} disabled={disabled || blocked || !m.consent || !m.config} />
  </View>;
}

function WeightSummary({ weights }: { weights: CriterionWeights }) {
  const t = useTheme();
  let normalized;
  try { normalized = normalizeWeights(weights); } catch { return <Notice error>En az bir kriterin ağırlığını artırın.</Notice>; }
  return <View style={{ gap: 8 }}><View style={{ flexDirection: 'row', height: 6, gap: 2 }}>
    {[normalized.rating, normalized.cost, normalized.proximity].map((weight, i) => <View key={i} style={{ flex: weight, backgroundColor: [t.primary, t.accent, t.warning][i], borderRadius: 2 }} />)}
  </View><Label secondary>Puan %{Math.round(normalized.rating * 100)} · Fiyat %{Math.round(normalized.cost * 100)} · Yakınlık %{Math.round(normalized.proximity * 100)}</Label></View>;
}

function ResultCard({ result: r, isDark, openUrl, onError }: { result: Recommendation; isDark: boolean; openUrl: (url: string) => Promise<void>; onError: (message: string) => void }) {
  const t = useTheme();
  const [expanded, setExpanded] = useState(false);
  const openDirections = () => { try { void openUrl(destinationOnlyUrl(r.directions_url)); } catch { onError('Yol tarifi bağlantısı doğrulanamadı.'); } };
  const share = async () => {
    try { await Share.share({ message: `Buluşma noktası: ${destinationOnlyUrl(r.directions_url)}` }); }
    catch { onError('Paylaşım açılamadı.'); }
  };
  return <View style={{ gap: 14, padding: 16, backgroundColor: t.surface, borderRadius: 2, borderWidth: 1, borderColor: r.rank === 1 ? t.primary : t.divider }}>
    <View style={styles.between}><Text style={{ color: t.accent, fontWeight: '700', fontSize: 13 }}>{r.rank === 1 ? 'İlk tercih' : `${r.rank}. seçenek`}</Text><Label>{(r.score * 100).toFixed(1)} / 100</Label></View>
    <Heading>{r.candidate.name}</Heading><Label secondary>{r.candidate.address}</Label>
    <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}><Star color={t.warning} size={17} /><Label>{r.candidate.rating.toFixed(1)} · {r.candidate.review_count} değerlendirme</Label></View>
    <Label>{priceLabel(r.candidate.price_level)}</Label>
    <View style={{ flexDirection: 'row', gap: 16, flexWrap: 'wrap' }}><View style={{ gap: 3 }}><Label secondary>Ortalama yol</Label><Text style={{ color: t.text, fontWeight: '700', fontSize: 22 }}>{r.t_avg_minutes.toFixed(0)} dk</Text></View><View style={{ gap: 3 }}><Label secondary>En uzun yol</Label><Text style={{ color: t.text, fontWeight: '700', fontSize: 22 }}>{r.t_max_minutes.toFixed(0)} dk</Text></View></View>
    <View style={{ gap: 8 }}>{r.per_user.map(p => <View key={p.user_id} style={styles.between}><View style={{ flex: 1 }}><Label>{p.label}</Label></View><Label>{p.raw_duration_minutes.toFixed(0)} dk · {p.distance_km.toFixed(1)} km</Label></View>)}</View>
    <View style={{ paddingTop: 10, paddingHorizontal: 10, paddingBottom: 5, alignSelf: 'flex-start' }}>
      <Image accessibilityLabel="Google Maps" source={isDark ? require('./assets/GoogleMaps_Logo_White_4x.png') : require('./assets/GoogleMaps_Logo_DarkGray_4x.png')} style={{ height: 18, width: 101 }} resizeMode="contain" />
    </View>
    {r.candidate.attributions?.map((a, i) => <Pressable key={i} accessibilityRole="link" onPress={() => a.providerUri && void openUrl(a.providerUri)} style={{ minHeight: 44, justifyContent: 'center' }}><Label secondary>{a.provider}</Label></Pressable>)}
    <View style={{ borderTopWidth: 1, borderTopColor: t.divider, paddingTop: 12, gap: 12 }}>
      <Pressable accessibilityRole="button" accessibilityLabel="Neden bu mekân?" accessibilityState={{ expanded }} aria-expanded={expanded} onPress={() => setExpanded(!expanded)} style={{ minHeight: 44, justifyContent: 'center' }}><Text style={{ color: t.primary, fontSize: 15, fontWeight: '600' }}>Neden bu mekân?</Text></Pressable>
      {expanded && <>
        <Label>Puan katkısı: {(r.score_breakdown.rating_component * 100).toFixed(1)}</Label>
        <Label>Fiyat katkısı: {(r.score_breakdown.cost_component * 100).toFixed(1)}</Label>
        <Label>Yakınlık katkısı: {(r.score_breakdown.proximity_component * 100).toFixed(1)}</Label>
        {r.score_breakdown.proximity_contributions.map(p => <Label key={p.user_id}>{p.label}: yakınlıkta %{Math.round(p.weight * 100)} ağırlık · {p.distance_km.toFixed(1)} km kuş uçuşu</Label>)}
      </>}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><View style={{ flex: 1 }}><Button label="Yol tarifi" icon={Navigation} onPress={openDirections} /></View><IconButton label={`${r.candidate.name} hedefini paylaş`} icon={Share2} onPress={() => void share()} /></View>
    </View>
  </View>;
}

function Confirmation({ visible, title, onClose, children }: { visible: boolean; title: string; onClose: () => void; children: React.ReactNode }) {
  const t = useTheme();
  return <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
    <SafeAreaView style={{ flex: 1, backgroundColor: '#00000077', justifyContent: 'center', padding: 20 }}>
      <View accessibilityViewIsModal style={{ padding: 24, backgroundColor: t.surface, borderRadius: 2, borderWidth: 1, borderColor: t.divider, width: '100%', maxWidth: 520, alignSelf: 'center', maxHeight: '90%' }}>
        <ScrollView contentContainerStyle={{ gap: 16 }}><View style={styles.between}><View style={{ flex: 1 }}><Heading>{title}</Heading></View><IconButton label="Kapat" icon={X} onPress={onClose} /></View>{children}</ScrollView>
      </View>
    </SafeAreaView>
  </Modal>;
}
