import { useEffect, useRef, useState } from 'react';
import { AppState, Modal, ScrollView, View } from 'react-native';
import { ArrowRight, Check, Sparkles, Trash2 } from 'lucide-react-native';
import { Button, Consent, Field, Heading, Label, Notice, Section, Segmented, Stepper, useTheme } from './components';
import { emptyBrief, interests, options, type MeetingPlan, type PlanBrief, type PlanInterpretation, type PlanResult } from './planner';
import type { Meeting } from './useMeeting';

export function MeetingPlanner({ m, active, onTransferred }: { m: Meeting; active: boolean; onTransferred: () => void }) {
  const t = useTheme();
  const [text, setText] = useState('');
  const [brief, setBrief] = useState<PlanBrief>({ ...emptyBrief });
  const [proposal, setProposal] = useState<PlanInterpretation | null>(null);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [selected, setSelected] = useState('');
  const [pending, setPending] = useState<MeetingPlan | null>(null);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const lock = useRef(false);
  const version = useRef(0);
  const expires = useRef(Date.now() + 7200000);
  const disabled = Boolean(busy || m.busy);
  function clear() {
    version.current++; setText(''); setBrief({ ...emptyBrief }); setProposal(null); setResult(null);
    setSelected(''); setPending(null); setConsent(false); setError('');
  }
  useEffect(() => { expires.current = Date.now() + 7200000; }, [text, brief]);
  useEffect(() => {
    const check = () => { if (Date.now() >= expires.current) { clear(); expires.current = Date.now() + 7200000; } };
    const timer = setInterval(check, 15000);
    const sub = AppState.addEventListener('change', check);
    return () => { clearInterval(timer); sub.remove(); };
  }, []);
  function update(patch: Partial<PlanBrief>) {
    setBrief(current => ({ ...current, ...patch })); setProposal(null); setResult(null); setSelected(''); setError('');
  }
  async function run(kind: string) {
    if (lock.current) return;
    lock.current = true; setBusy(kind); setError('');
    if (kind === 'interpret') setProposal(null);
    const current = version.current;
    try {
      await m.api.connect();
      if (kind === 'interpret') {
        const value = await m.api.interpretPlan(text, brief);
        if (version.current === current) setProposal(value);
      } else {
        const value = await m.api.recommendPlans(brief);
        if (version.current === current) { setResult(value); setSelected(''); }
      }
    } catch (cause) { if (version.current === current) setError(cause instanceof Error ? cause.message : 'Plan hazırlanamadı.'); }
    finally { lock.current = false; setBusy(''); }
  }

  return <View style={{ display: active ? 'flex' : 'none' }}>
    <Section><Heading>Birlikte ne yapalım?</Heading>
      <Field label="Buluşmayı anlat" multiline maxLength={1200} editable={!disabled} value={text} onChangeText={value => { setText(value); setProposal(null); }}
        placeholder="Ankara'da üç arkadaş, iki saatlik sakin ve ekonomik bir buluşma istiyoruz." style={{ minHeight: 120, textAlignVertical: 'top' }} />
      <Consent label="Metnimin sunucudaki Llama ile işlenmesini kabul ediyorum. Tam adres veya kişisel iletişim bilgisi eklemedim." checked={consent} onChange={setConsent} disabled={disabled} />
      <Button label="Anlattıklarımdan taslak çıkar" icon={Sparkles} loading={busy === 'interpret'} disabled={disabled || !consent || text.trim().length < 5 || !m.health?.ai_ready} onPress={() => void run('interpret')} />
      {!m.health?.ai_ready && <Label secondary>Llama hazır değil. Buluşma bilgilerini kendiniz doldurabilirsiniz.</Label>}
      {proposal && <View style={{ borderLeftWidth: 3, borderLeftColor: t.accent, paddingLeft: 14, gap: 12 }}>
        <Heading>Taslağı incele</Heading>
        <Label>{proposal.brief.city || 'Şehir belirtilmedi'} · {proposal.brief.area} · {proposal.brief.group_size ?? '?'} kişi · {proposal.brief.duration_minutes} dk</Label>
        <Label>{options.budget.find(([id]) => id === proposal.brief.budget)?.[1]} · {options.environment.find(([id]) => id === proposal.brief.environment)?.[1]} · {options.pace.find(([id]) => id === proposal.brief.pace)?.[1]}</Label>
        <Label>{proposal.brief.interests.map(id => interests.find(([key]) => key === id)?.[1]).join(', ') || 'İlgi alanı belirtilmedi'}</Label>
        {proposal.warnings.map(w => <Label secondary key={w}>{w}</Label>)}
        <Button label="Taslağı kullan" icon={Check} disabled={disabled} onPress={() => { setBrief(proposal.brief); setProposal(null); setResult(null); }} />
        <Button label="Vazgeç" tone="secondary" onPress={() => setProposal(null)} disabled={disabled} />
      </View>}
    </Section>
    <Section><Heading>Buluşma bilgileri</Heading>
      <Field label="Plan şehri" value={brief.city} maxLength={80} editable={!disabled} onChangeText={city => update({ city })} />
      <Field label="İlçe veya semt (isteğe bağlı)" value={brief.area} maxLength={100} editable={!disabled} onChangeText={area => update({ area })} />
      {brief.group_size === null ? <Field label="Kaç kişisiniz?" keyboardType="number-pad" maxLength={2} value="" editable={!disabled} onChangeText={value => { if (/^\d+$/.test(value)) update({ group_size: Number(value) }); }} />
        : <Stepper label="Kişi sayısı" value={brief.group_size} min={2} max={m.config?.max_participants || 8} disabled={disabled} onChange={group_size => update({ group_size })} />}
      <Stepper label="Süre (dakika)" value={brief.duration_minutes} min={30} max={360} step={15} disabled={disabled} onChange={duration_minutes => update({ duration_minutes })} />
      <Label>Bütçe tercihi</Label><Segmented items={options.budget.map(([, label]) => label)} value={options.budget.find(([id]) => id === brief.budget)![1]} disabled={disabled} onChange={label => update({ budget: options.budget.find(([, name]) => name === label)![0] })} />
      <Label>Ortam</Label><Segmented items={options.environment.map(([, label]) => label)} value={options.environment.find(([id]) => id === brief.environment)![1]} disabled={disabled} onChange={label => update({ environment: options.environment.find(([, name]) => name === label)![0] })} />
      <Label>Tempo</Label><Segmented items={options.pace.map(([, label]) => label)} value={options.pace.find(([id]) => id === brief.pace)![1]} disabled={disabled} onChange={label => update({ pace: options.pace.find(([, name]) => name === label)![0] })} />
      <Label>İlgi alanları</Label>{interests.map(([id, label]) => <Consent key={id} label={label} checked={brief.interests.includes(id)} disabled={disabled}
        onChange={checked => update({ interests: checked ? [...brief.interests, id] : brief.interests.filter(i => i !== id) })} />)}
      <Button label="Plan öner" icon={Sparkles} loading={busy === 'recommend'} disabled={disabled} onPress={() => void run('recommend')} />
    </Section>
    <Section><Heading>Plan fikirleri</Heading>
      {error ? <Notice error>{error}</Notice> : null}
      {!result && <Label secondary>Henüz bir plan oluşturulmadı.</Label>}
      {result?.questions.map(q => <Notice key={q}>{q}</Notice>)}
      {result?.plans.map(plan => <View key={plan.id} style={{ borderWidth: 1, borderColor: selected === plan.id ? t.accent : t.border, borderRadius: 4, padding: 16, gap: 14 }}>
        <Label secondary>{plan.duration_minutes} dk · {plan.handoff.group_size} kişi · {plan.handoff.city}</Label><Heading>{plan.title}</Heading><Label>{plan.summary}</Label><Label secondary>{plan.reason}</Label>
        <Button label={selected === plan.id ? 'Planı daralt' : 'Planı incele'} tone="secondary" onPress={() => setSelected(selected === plan.id ? '' : plan.id)} />
        {selected === plan.id && <View style={{ gap: 12 }}>{plan.steps.map(step => <Label key={step.title}>{step.title} · {step.minutes} dk</Label>)}{plan.checks.map(check => <Label secondary key={check}>{check}</Label>)}</View>}
        <Button label="ORTAK’ta mekân bul" icon={ArrowRight} disabled={disabled} onPress={() => setPending(plan)} />
      </View>)}
      {result?.warnings.map(w => <Label secondary key={w}>{w}</Label>)}
      <Button label="Planı temizle" icon={Trash2} tone="secondary" disabled={disabled} onPress={clear} />
      <Label secondary>Planınız yalnızca bu oturumda tutulur ve iki saat işlem yapılmadığında temizlenir.</Label>
    </Section>
    <Modal visible={pending !== null} transparent animationType="fade" onRequestClose={() => { if (!m.busy) setPending(null); }}>
      <View style={{ flex: 1, backgroundColor: '#0009', justifyContent: 'center', padding: 20 }}>
        <ScrollView style={{ maxHeight: '85%', backgroundColor: t.surface, borderRadius: 4 }} contentContainerStyle={{ padding: 24, gap: 18 }} accessibilityViewIsModal>
          <Heading>Mekân aramasına aktar</Heading><Label>{pending?.title} · {pending?.handoff.city} · {pending?.handoff.group_size} kişi</Label>
          <Label>Şehir, kişi sayısı, mekân türü ve planın kriter ağırlıkları aktarılacak. Mevcut arama, kişi konumları ve filtreler temizlenecek; planınız burada kalacak.</Label>
          <Label>Puan %{pending?.handoff.criterion_weights.rating} · Fiyat %{pending?.handoff.criterion_weights.cost} · Yakınlık %{pending?.handoff.criterion_weights.proximity}</Label>
          <Label>Kişi konumlarını ORTAK’ta gireceksiniz. Henüz Google araması yapılmayacak.</Label>
          <Button label="Bilgileri aktar" icon={ArrowRight} disabled={disabled} onPress={() => { if (pending) void m.transferPlan(pending.handoff).then(done => { if (done) { setPending(null); onTransferred(); } }); }} />
          {m.error ? <Notice error>{m.error}</Notice> : null}
          <Button label="Planda kal" tone="secondary" disabled={disabled} onPress={() => setPending(null)} />
        </ScrollView>
      </View>
    </Modal>
  </View>;
}
