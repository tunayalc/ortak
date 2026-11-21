import { useEffect, useState } from 'react'
import { api } from './api'

function Votes({ choices }) {
  if (!choices.length) return null
  return <div><h3>Grup oyları</h3><p>Oylar ORTAK sıralamasını değiştirmez.</p>
    {choices.map(c => <p key={c.id}>{c.name}: <strong>{c.votes} oy</strong></p>)}
    {choices.some(c => c.provider === 'google') && <small>Google Maps</small>}
    {choices.flatMap(c => c.attributions || []).map((a,i) => <small key={i}> {a.provider}</small>)}</div>
}

export function GroupHost({ size, result, onImport, disabled }) {
  const [group, setGroup] = useState(null), [busy,setBusy] = useState(false), [notice, setNotice] = useState('')
  const [loaded, setLoaded] = useState(false)
  async function run(fn) {
    if (busy) return
    setBusy(true); setNotice('')
    try { await fn() } catch(e) { setNotice(e.message) } finally { setBusy(false) }
  }
  async function refresh() { setGroup(await api.group()); setLoaded(true) }
  const ids = result?.recommendations.slice(0,3).map(x => x.candidate.id) || []
  return <details className="planner-band" onToggle={e => { if(e.currentTarget.open) void run(refresh) }}><summary>Katılımcı davetleri ve oylama</summary>
    <p>Her kişiye kendi bağlantısını gönderin. Bağlantıyı alan kişi o koltuğun başlangıç noktasını ve oyunu değiştirebilir. Davet iki saat içinde kapanır.</p>
    <fieldset disabled={disabled || busy} className="group-actions">
      {!group && loaded && <button className="secondary" onClick={() => run(async () => setGroup(await api.createGroup(size)))}>{size} kişilik davet oluştur</button>}
      {group && <>{group.seats.map((s,i) => { const url = location.origin + '/#davet=' + s.token
        return <label key={s.token}>Kişi {i+1}: {s.ready ? 'Konum eklendi' : 'Konum bekleniyor'}
          <input aria-label={'Kişi '+(i+1)+' davet bağlantısı'} readOnly value={url} onFocus={e => e.target.select()} />
          <button className="secondary" onClick={() => run(async () => { await navigator.clipboard.writeText(url); setNotice('Bağlantı kopyalandı.') })}>Bağlantıyı kopyala</button></label>})}
        <button className="secondary" disabled={!group.seats.every(s => s.ready) || !!result} onClick={() => run(async () => { onImport(await api.groupLocations()); setNotice('Başlangıç noktaları aktarıldı. Henüz arama yapılmadı.') })}>Başlangıç noktalarını kullan</button>
        {!group.choices.length && <button className="secondary" disabled={ids.length < 2} onClick={() => run(async () => setGroup(await api.groupBallot(result.scenario.id, ids)))}>Sonuçları oylamaya aç</button>}
        <Votes choices={group.choices}/>
        <button className="secondary" onClick={() => run(async () => { await api.closeGroup(); setGroup(null); setNotice('Davet kapatıldı.') })}>Daveti kapat</button></>}
      <button className="secondary" onClick={() => run(refresh)}>Davet durumunu yenile</button>
    </fieldset><p role="status">{notice}</p></details>
}

export function Guest({ token }) {
  const [view, setView] = useState(null), [point, setPoint] = useState(''), [consent,setConsent] = useState(false)
  const [busy,setBusy] = useState(false), [notice,setNotice] = useState('')
  useEffect(() => {
    let current = true
    api.runtimeConfig().then(() => api.guest({token})).then(v => { if(current) setView(v) }).catch(e => { if(current) setNotice(e.message) })
    return () => { current = false }
  }, [token])
  async function act(action, extra={}) {
    setBusy(true); setNotice('')
    try { setView(await api.guest({token,action,...extra})); if(action === 'locate' || action === 'withdraw') setPoint('') }
    catch(e) { if(e.status === 404) setView(null); setNotice(e.message) } finally {setBusy(false)}
  }
  const parts = point.split(',').map(p => p.trim())
  const valid = parts.length === 2 && parts.every(p => /^[-+]?\d+(\.\d+)?$/.test(p)) && Math.abs(+parts[0])<=90 && Math.abs(+parts[1])<=180
  return <main className="guest-page planner-band"><span className="eyebrow">ORTAK</span><h1>Buluşma daveti</h1>
    {!view && !notice && <p>Davet açılıyor…</p>}{view && <fieldset disabled={busy} className="group-actions"><legend>Kişi {view.seat}</legend>
    <p>{view.ready ? 'Başlangıç noktanız kaydedildi.' : 'Başlangıç olarak ev adresiniz yerine yakın bir durak da seçebilirsiniz.'}</p>
    {!view.choices.length && <><label>Başlangıç koordinatı<input placeholder="39.92,32.85" value={point} onChange={e => setPoint(e.target.value)} maxLength={64}/></label>
      <label className="planner-consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>Bu noktayı düzenleyen kişiyle ve arama sırasında Google Maps ile paylaşmayı kabul ediyorum. Diğer katılımcılar konumumu göremez.</label>
      <button className="primary" disabled={!consent || !valid} onClick={()=>act('locate',{location:{lat:+parts[0],lng:+parts[1]},consent:true})}>Başlangıç noktamı kaydet</button></>}
    {view.choices.length > 0 && <><Votes choices={view.choices}/>{view.choices.map(c => <button key={c.id} aria-pressed={view.vote===c.id} className="secondary" onClick={()=>act('vote',{candidate_id:c.id})}>{c.name}{view.vote===c.id ? ' (oyunuz)' : ' için oy ver'}</button>)}</>}
    <button className="secondary" onClick={()=>act('view')}>Durumu yenile</button>
    {view.ready && <small>Geri çekme, düzenleyenin daha önce aramaya aktardığı bir kopyayı silmez.</small>}
    {view.ready && <button className="secondary" onClick={()=>act('withdraw')}>Paylaşımımı geri çek</button>}</fieldset>}
    <p role="status">{notice}</p><a href="/">ORTAK ana sayfa</a></main>
}
