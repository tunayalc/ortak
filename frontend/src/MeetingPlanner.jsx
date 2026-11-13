import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Check, Clock3, MapPin, Sparkles, Trash2, Users, X } from 'lucide-react'
import { api } from './api'
import { emptyBrief, planInterests, planOptions } from './planner'

export default function MeetingPlanner({ active, maxParticipants, available, onTransfer, transferring }) {
  const [text, setText] = useState('')
  const [brief, setBrief] = useState({ ...emptyBrief })
  const [proposal, setProposal] = useState(null)
  const [result, setResult] = useState(null)
  const [selected, setSelected] = useState(null)
  const [pending, setPending] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [consent, setConsent] = useState(false)
  const version = useRef(0)
  const lock = useRef(false)
  const dialog = useRef(null)
  const disabled = Boolean(busy || transferring)

  function clear() {
    version.current += 1
    setText(''); setBrief({ ...emptyBrief }); setProposal(null); setResult(null)
    setSelected(null); setPending(null); setConsent(false); setError('')
  }
  useEffect(() => {
    const timer = setTimeout(clear, 2 * 60 * 60 * 1000)
    return () => clearTimeout(timer)
  }, [text, brief])
  useEffect(() => {
    if (pending) dialog.current?.showModal()
    else dialog.current?.close()
  }, [pending])

  function update(key, value) {
    setBrief(current => ({ ...current, [key]: value }))
    setProposal(null); setResult(null); setSelected(null); setError('')
  }
  async function run(kind) {
    if (lock.current) return
    lock.current = true; setBusy(kind); setError('')
    if (kind === 'interpret') setProposal(null)
    const current = version.current
    try {
      await api.runtimeConfig()
      if (kind === 'interpret') {
        const next = await api.interpretPlan({ text, current: brief })
        if (current === version.current) setProposal(next)
      } else {
        const next = await api.recommendPlans(brief)
        if (current === version.current) { setResult(next); setSelected(null) }
      }
    } catch (cause) { if (current === version.current) setError(cause.message) }
    finally { lock.current = false; setBusy('') }
  }
  async function transfer() {
    try { await onTransfer(pending); setPending(null) }
    catch (cause) { setError(cause.message); setPending(null) }
  }

  return <section hidden={!active} className="meeting-planner" aria-label="Buluşma planı">
    <div className="planner-heading"><div><span className="eyebrow">BULUŞMA PLANI</span><h2>Birlikte ne yapalım?</h2></div>
      <button className="theme-toggle" title="Planı temizle" aria-label="Planı temizle" disabled={disabled} onClick={clear}><Trash2 size={18} /></button>
    </div>
    <div className="planner-layout">
      <div className="planner-inputs">
        <section className="planner-band">
          <label htmlFor="plan-story">Buluşmayı anlat</label>
          <textarea id="plan-story" rows={4} maxLength={1200} disabled={disabled} value={text} onChange={event => { setText(event.target.value); setProposal(null) }}
            placeholder="Ankara, Gölbaşı'nda yaşıyorum. Üç arkadaş iki saatliğine buluşacağız; sakin ve ekonomik bir şeyler yapalım." />
          <label className="planner-consent"><input type="checkbox" checked={consent} disabled={disabled} onChange={e => setConsent(e.target.checked)} />
            Metnimin sunucudaki Llama ile işlenmesini kabul ediyorum. Tam adres veya kişisel iletişim bilgisi eklemedim.</label>
          <button className="secondary" disabled={disabled || !consent || text.trim().length < 5 || !available} onClick={() => run('interpret')}><Sparkles size={17} />{busy === 'interpret' ? 'Yorumlanıyor…' : 'Anlattıklarımdan taslak çıkar'}</button>
          {!available && <p className="source-note">Llama şu anda hazır değil. Buluşma bilgileriyle plan oluşturabilirsiniz.</p>}
          {proposal && <div className="planner-proposal" role="status"><h3>Taslağı incele</h3>
            <p>{proposal.brief.city || 'Şehir belirtilmedi'}{proposal.brief.area ? ` · ${proposal.brief.area}` : ''} · {proposal.brief.group_size ?? '?'} kişi · {proposal.brief.duration_minutes} dk</p>
            <p>{planOptions.budget.find(([id]) => id === proposal.brief.budget)?.[1]} · {planOptions.environment.find(([id]) => id === proposal.brief.environment)?.[1]} · {planOptions.pace.find(([id]) => id === proposal.brief.pace)?.[1]}</p>
            <p>{proposal.brief.interests.map(id => planInterests.find(([key]) => key === id)?.[1]).join(', ') || 'İlgi alanı belirtilmedi'}</p>
            {proposal.warnings.map(w => <p key={w} className="source-note">{w}</p>)}
            <div className="action-row"><button className="secondary" disabled={disabled} onClick={() => { setBrief(proposal.brief); setProposal(null); setResult(null); setSelected(null) }}><Check size={16} />Taslağı kullan</button>
              <button className="secondary" disabled={disabled} onClick={() => setProposal(null)}><X size={16} />Vazgeç</button></div>
          </div>}
        </section>
        <section className="planner-band"><h3>Buluşma bilgileri</h3>
          <div className="planner-fields">
            <label>Plan şehri<input value={brief.city} maxLength={80} disabled={disabled} onChange={e => update('city', e.target.value)} /></label>
            <label>İlçe veya semt (isteğe bağlı)<input value={brief.area} maxLength={100} disabled={disabled} onChange={e => update('area', e.target.value)} /></label>
            <label>Kaç kişisiniz?<input type="number" min={2} max={maxParticipants} value={brief.group_size ?? ''} disabled={disabled} onChange={e => update('group_size', e.target.value === '' ? null : Number(e.target.value))} /></label>
            <label>Birlikte geçireceğiniz süre<select value={brief.duration_minutes} disabled={disabled} onChange={e => update('duration_minutes', Number(e.target.value))}>
              {[...new Set([30, 45, 60, 90, 120, 180, 240, 360, brief.duration_minutes])].sort((a, b) => a - b).map(n => <option key={n} value={n}>{n} dakika</option>)}</select></label>
            {Object.entries(planOptions).map(([key, options]) => <label key={key}>{({ budget: 'Bütçe tercihi', environment: 'Ortam', pace: 'Tempo' })[key]}<select value={brief[key]} disabled={disabled} onChange={e => update(key, e.target.value)}>{options.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>)}
          </div>
          <fieldset className="planner-interests" disabled={disabled}><legend>İlgi alanları</legend>{planInterests.map(([id, label]) => <label key={id}><input type="checkbox" checked={brief.interests.includes(id)} onChange={() => update('interests', brief.interests.includes(id) ? brief.interests.filter(i => i !== id) : [...brief.interests, id])} />{label}</label>)}</fieldset>
          <button className="primary" disabled={disabled} onClick={() => run('recommend')}><Sparkles size={18} />{busy === 'recommend' ? 'Planlar hazırlanıyor…' : 'Plan öner'}</button>
        </section>
      </div>
      <section className="planner-results" aria-live="polite"><h3>Plan fikirleri</h3>
        {error && <p className="error" role="alert">{error}</p>}
        {!result && <div className="planner-empty"><Sparkles size={32} /><h3>Bugün neye zaman ayıralım?</h3><p>Sohbet, kültür, doğa veya birlikte bir şeyler üretmek.</p></div>}
        {result?.questions.map(q => <p className="privacy-note" key={q}>{q}</p>)}
        {result?.plans.map(plan => <article className={`plan-card ${selected === plan.id ? 'selected' : ''}`} key={plan.id}>
          <div className="plan-meta"><span><Clock3 size={15} />{plan.duration_minutes} dk</span><span><Users size={15} />{plan.handoff.group_size} kişi</span><span><MapPin size={15} />{plan.handoff.city}</span></div>
          <h3>{plan.title}</h3><p>{plan.summary}</p><p className="source-note">{plan.reason}</p>
          <button className="secondary" aria-expanded={selected === plan.id} aria-controls={`plan-${plan.id}`} onClick={() => setSelected(selected === plan.id ? null : plan.id)}>{selected === plan.id ? 'Planı daralt' : 'Planı incele'}</button>
          <div id={`plan-${plan.id}`} hidden={selected !== plan.id}>
            <ol className="plan-steps">{plan.steps.map(step => <li key={step.title}><span>{step.title}</span><strong>{step.minutes} dk</strong></li>)}</ol>
            {plan.checks.map(check => <p className="source-note" key={check}>{check}</p>)}
          </div>
          <button className="primary" disabled={disabled} onClick={() => setPending(plan)}><ArrowRight size={17} />ORTAK’ta mekân bul</button>
        </article>)}
        {result?.warnings.map(w => <p key={w} className="source-note">{w}</p>)}
      </section>
    </div>
    <p className="privacy-note">Planınız yalnızca bu oturumda tutulur ve iki saat işlem yapılmadığında temizlenir.</p>
    <dialog ref={dialog} className="plan-transfer" onCancel={e => { if (transferring) e.preventDefault(); else setPending(null) }} aria-labelledby="transfer-heading">
      {pending && <><h2 id="transfer-heading">Mekân aramasına aktar</h2><p>{pending.title} · {pending.handoff.city} · {pending.handoff.group_size} kişi</p>
        <p>Şehir, kişi sayısı, mekân türü ve planın kriter ağırlıkları aktarılacak. Mevcut arama sonuçları, konumlar ve filtreler temizlenecek; planınız burada kalacak.</p>
        <p>Puan %{pending.handoff.criterion_weights.rating} · Fiyat %{pending.handoff.criterion_weights.cost} · Yakınlık %{pending.handoff.criterion_weights.proximity}</p>
        <p>Kişi konumlarını ORTAK’ta gireceksiniz. Henüz Google araması yapılmayacak.</p>
        <div className="action-row"><button className="primary" disabled={transferring} onClick={transfer}><ArrowRight size={16} />{transferring ? 'Aktarılıyor…' : 'Bilgileri aktar'}</button><button className="secondary" disabled={transferring} onClick={() => setPending(null)}>Planda kal</button></div></>}
    </dialog>
  </section>
}
