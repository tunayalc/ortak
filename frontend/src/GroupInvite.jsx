import { useEffect, useRef, useState } from 'react'
import { Copy, DoorOpen, Save, Share2, Trash2, UserMinus, Users } from 'lucide-react'
import { api } from './api'
import { PlacePicker } from './LocationTools'
import { travelModes } from './planner'
import { forgetRoom, forgetSeat, rememberRoom, rememberSeat, renameSavedRoom, roomLink, savedRooms, seatFor } from './rooms'

const modeName = value => travelModes.find(m => m.value === value)?.label || 'Varsayılan'

function Votes({ choices }) {
  if (!choices.length) return null
  return <div><h3>Grup oyları</h3><p>Oylar ORTAK sıralamasını değiştirmez.</p>
    {choices.map(c => <p key={c.id}>{c.name}: <strong>{c.votes} oy</strong></p>)}
    {choices.some(c => c.provider === 'google') && <small>Google Maps</small>}
    {choices.flatMap(c => c.attributions || []).map((a,i) => <small key={i}> {a.provider}</small>)}</div>
}

function ShareLink({ link, name, onNotice }) {
  const text = `${name} odasına katıl, başlangıç noktanı ekle: ${link}`
  async function share() {
    if (navigator.share) {
      try { await navigator.share({ title: `ORTAK - ${name}`, text, url: link }); return } catch (e) { if (e?.name === 'AbortError') return }
    }
    await navigator.clipboard.writeText(link); onNotice('Bağlantı kopyalandı.')
  }
  return <div className="room-share">
    <label>Oda bağlantısı<input aria-label="Oda bağlantısı" readOnly value={link} onFocus={e => e.target.select()} /></label>
    <div className="room-share-actions">
      <button type="button" className="primary" onClick={() => void share().catch(() => onNotice('Paylaşım açılamadı; bağlantıyı kopyalayın.'))}><Share2 size={16} /> Paylaş</button>
      <a className="button secondary" href={`https://wa.me/?text=${encodeURIComponent(text)}`} target="_blank" rel="noopener noreferrer">WhatsApp</a>
      <a className="button secondary" href={`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(`${name} odasına katıl`)}`} target="_blank" rel="noopener noreferrer">Telegram</a>
      <button type="button" className="secondary" onClick={() => void navigator.clipboard.writeText(link).then(() => onNotice('Bağlantı kopyalandı.'), () => onNotice('Kopyalanamadı; bağlantıyı seçip kopyalayın.'))}><Copy size={16} /> Kopyala</button>
    </div>
  </div>
}

/** Host side of a room: create or reopen, share one link, watch who added a point, import. */
export function RoomHost({ result, onImport, disabled }) {
  const [room, setRoom] = useState(null), [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false), [notice, setNotice] = useState('')
  const [rooms, setRooms] = useState(savedRooms), [name, setName] = useState(''), [saveName, setSaveName] = useState('')
  const [openedKey, setOpenedKey] = useState('')
  const busyRef = useRef(false)
  async function run(fn) {
    if (busyRef.current) return
    busyRef.current = true; setBusy(true); setNotice('')
    try { await fn() } catch (e) { setNotice(e.message) } finally { busyRef.current = false; setBusy(false) }
  }
  useEffect(() => { void run(async () => { const mine = await api.group(); setRoom(mine?.room ? mine : null); setLoaded(true) }) }, [])
  useEffect(() => {
    if (!room) return
    const timer = setInterval(() => {
      if (document.visibilityState !== 'visible' || busyRef.current) return
      api.group().then(next => setRoom(next?.room ? next : null)).catch(() => {})
    }, 5000)
    return () => clearInterval(timer)
  }, [Boolean(room)])

  const local = rooms.find(r => r.key === openedKey)
  const join = room?.join || local?.join
  const ready = room?.seats.filter(s => s.ready).length || 0
  const ids = result?.recommendations.slice(0,3).map(x => x.candidate.id) || []

  if (!loaded) return <section className="room-panel"><p>Oda bilgisi yükleniyor…</p><p role="status">{notice}</p></section>
  if (!room) return <section className="room-panel">
    <p>Tek bir bağlantı oluşturun ve grubunuzla paylaşın. Bağlantıyı açan herkes adını yazıp kendi başlangıç noktasını ekler; siz kimin eklediğini görür, hazır olanları listeye aktarırsınız.</p>
    <fieldset className="group-actions" disabled={disabled || busy}>
      <label>Oda adı<input placeholder="Örn. Cuma ekibi" value={name} maxLength={40} onChange={e => setName(e.target.value)} /></label>
      <button type="button" className="primary" onClick={() => run(async () => { const created = await api.createRoom(name.trim() || 'Oda'); setOpenedKey(''); setRoom(created); setSaveName(created.name) })}><DoorOpen size={16} /> Oda kur</button>
      {rooms.length > 0 && <div className="saved-rooms"><h3>Kayıtlı odalarım</h3>
        {rooms.map(r => <div className="saved-room" key={r.key}><strong>{r.name}</strong>
          <button type="button" className="secondary" onClick={() => run(async () => { const opened = await api.openRoom(r.key); setOpenedKey(r.key); setRoom(opened); setSaveName(opened.name) })}>Aç</button>
          <button type="button" className="secondary" aria-label={`${r.name} kaydını sil`} onClick={() => run(async () => {
            if (!confirm(`"${r.name}" odasının kaydı ve üye adları silinsin mi? Bu geri alınamaz.`)) return
            try { await api.forgetRoom(r.key) } catch (e) { if (e.status !== 404) throw e }
            forgetRoom(r.key); setRooms(savedRooms()); setNotice('Oda kaydı silindi.')
          })}><Trash2 size={16} /></button></div>)}
      </div>}
    </fieldset><p role="status">{notice}</p></section>

  return <section className="room-panel">
    <div className="room-head"><Users size={18} /><strong>{room.name}</strong>{room.saved && <span className="room-badge">Kayıtlı</span>}</div>
    {join ? <ShareLink link={roomLink(join)} name={room.name} onNotice={setNotice} /> : <p className="error">Bu odanın bağlantısı bu cihazda yok.</p>}
    <p className="privacy-note">Siz de bu bağlantıyı açıp odaya katılabilirsiniz. Üyeler birbirinin konumunu görmez.</p>
    <fieldset className="group-actions" disabled={disabled || busy}>
      <div className="room-members" aria-live="polite">
        <h3>Katılanlar ({room.seats.length}/{room.capacity}) · Konum ekleyen: {ready}</h3>
        {!room.seats.length && <p>Henüz kimse katılmadı. Bağlantıyı paylaşın.</p>}
        {room.seats.map((s, i) => <div className="room-member" key={i}>
          <span>{s.name}</span>
          <span className={s.ready ? 'pass' : ''}>{s.ready ? 'Konum eklendi' : 'Konum bekleniyor'}{s.travel_mode ? ` · ${modeName(s.travel_mode)}` : ''}</span>
          {!room.choices.length && <button type="button" className="secondary" aria-label={`${s.name} kişisini odadan çıkar`} onClick={() => run(async () => setRoom(await api.removeMember(i + 1)))}><UserMinus size={16} /></button>}
        </div>)}
      </div>
      <button type="button" className="primary" disabled={ready < 2 || !!result} onClick={() => run(async () => { onImport(await api.groupLocations()); setNotice(`${ready} kişinin konumu listeye aktarıldı. Henüz arama yapılmadı.`) })}>Konumları kişi listesine aktar</button>
      {!room.saved ? <div className="room-save">
        <label>Sık buluşuyorsanız odayı kaydedin<input placeholder="Oda adı" value={saveName} maxLength={40} onChange={e => setSaveName(e.target.value)} /></label>
        <button type="button" className="secondary" disabled={!saveName.trim()} onClick={() => run(async () => {
          const saved = await api.saveRoom(saveName.trim())
          rememberRoom({ name: saved.name, key: saved.owner_key, join: saved.join || join })
          setRooms(savedRooms()); setOpenedKey(saved.owner_key); setRoom(saved)
          setNotice('Oda kaydedildi. Aynı bağlantı sonraki buluşmalarda da çalışır; konumlar her seferinde yeniden eklenir.')
        })}><Save size={16} /> Odayı kaydet</button>
        <small>Kayıtta oda adı ile üyelerin adları ve ulaşım tercihleri tutulur; konumlar tutulmaz. 90 gün kullanılmazsa silinir.</small>
      </div> : <div className="room-save">
        <label>Oda adı<input value={saveName} maxLength={40} onChange={e => setSaveName(e.target.value)} /></label>
        <button type="button" className="secondary" disabled={!saveName.trim() || saveName.trim() === room.name} onClick={() => run(async () => {
          const renamed = await api.renameRoom(saveName.trim()); setRoom(renamed)
          if (openedKey) { renameSavedRoom(openedKey, renamed.name); setRooms(savedRooms()) }
        })}>Adı değiştir</button>
      </div>}
      {!room.choices.length && <button type="button" className="secondary" disabled={ids.length < 2} onClick={() => run(async () => setRoom(await api.groupBallot(result.scenario.id, ids)))}>Sonuçları odada oylamaya aç</button>}
      <Votes choices={room.choices}/>
      <button type="button" className="secondary" onClick={() => run(async () => { await api.closeGroup(); setRoom(null); setOpenedKey(''); setNotice(room.saved ? 'Buluşma bitti; oda kayıtlı kalıyor.' : 'Oda kapatıldı.') })}>{room.saved ? 'Bu buluşmayı bitir' : 'Odayı kapat'}</button>
    </fieldset><p role="status">{notice}</p></section>
}

function GuestLocation({ onSave, view, busy }) {
  const [text, setText] = useState(''), [point, setPoint] = useState(null)
  const [mode, setMode] = useState(view.travel_mode || '')
  return <>
    <PlacePicker label="Başlangıç noktanız" value={text} place={point?.label} disabled={busy}
      onChange={value => { setText(value); setPoint(null) }}
      onPick={item => { setText(item.name); setPoint({ lat: item.lat, lng: item.lng, label: item.address || item.name }) }} />
    {view.room && <label className="transport-select">Nasıl geleceksiniz?
      <select value={mode} onChange={e => setMode(e.target.value)}><option value="">Oda sahibinin seçimi</option>
        {travelModes.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}</select></label>}
    <button type="button" className="primary" disabled={!point} onClick={() => onSave({ location: { lat: point.lat, lng: point.lng }, ...(view.room ? { travel_mode: mode || null } : {}) })}>Başlangıç noktamı kaydet</button>
    {!point && <small>Yer adını yazıp "Ara"ya basın ve listeden seçin, ya da "Konumum" ile bulunduğunuz yeri kullanın.</small>}
  </>
}

function GuestBody({ view, busy, act, extra }) {
  const [editing, setEditing] = useState(false)
  return <fieldset disabled={busy} className="group-actions">
    {view.room ? <legend>{view.room_name} · {view.name}</legend> : <legend>Kişi {view.seat}</legend>}
    {view.ready && !editing && <p className="pass">Başlangıç noktanız kaydedildi{view.travel_mode ? ` (${modeName(view.travel_mode)})` : ''}. Düzenleyen aramayı başlattığında kullanılacak.</p>}
    {!view.choices.length && (!view.ready || editing) && <GuestLocation view={view} busy={busy} onSave={async body => { await act('locate', body); setEditing(false) }} />}
    {!view.choices.length && view.ready && !editing && <button type="button" className="secondary" onClick={() => setEditing(true)}>Başlangıç noktamı değiştir</button>}
    {view.choices.length > 0 && <><Votes choices={view.choices}/>{view.choices.map(c => <button type="button" key={c.id} aria-pressed={view.vote===c.id} className="secondary" onClick={()=>act('vote',{candidate_id:c.id})}>{c.name}{view.vote===c.id ? ' (oyunuz)' : ' için oy ver'}</button>)}</>}
    <button type="button" className="secondary" onClick={()=>act('view')}>Durumu yenile</button>
    {view.ready && <button type="button" className="secondary" onClick={()=>act('withdraw')}>Konumumu geri çek</button>}
    {view.ready && <small>Geri çekme, düzenleyenin daha önce aramaya aktardığı bir kopyayı silmez.</small>}
    {extra}
  </fieldset>
}

function useGuest(token, onGone) {
  const [view, setView] = useState(null), [busy, setBusy] = useState(false), [notice, setNotice] = useState('')
  useEffect(() => {
    if (!token) return
    let current = true
    api.runtimeConfig().then(() => api.guest({ token })).then(v => { if (current) setView(v) })
      .catch(e => { if (!current) return; if (e.status === 404) onGone?.(); setNotice(e.message) })
    return () => { current = false }
  }, [token])
  async function act(action, extra = {}) {
    setBusy(true); setNotice('')
    try { const next = await api.guest({ token, action, ...extra }); setView(next.left ? null : next); return next }
    catch (e) { if (e.status === 404) { setView(null); onGone?.() } setNotice(e.message) } finally { setBusy(false) }
  }
  return { view, setView, busy, notice, setNotice, act }
}

/** Someone opened a room link: join with a name, then add a starting point. */
export function RoomGuest({ join }) {
  const [token, setToken] = useState(() => seatFor(join))
  const [name, setName] = useState(''), [joining, setJoining] = useState(false), [joinNotice, setJoinNotice] = useState('')
  const guest = useGuest(token, () => { forgetSeat(join); setToken('') })
  async function enter() {
    setJoining(true); setJoinNotice('')
    try {
      await api.runtimeConfig()
      const joined = await api.joinRoom(join, name.trim())
      rememberSeat(join, joined.token); guest.setView(joined); setToken(joined.token)
    } catch (e) { setJoinNotice(e.message) } finally { setJoining(false) }
  }
  return <main className="guest-page planner-band"><span className="eyebrow">ORTAK</span><h1>Buluşma odası</h1>
    {!token && <fieldset className="group-actions" disabled={joining}>
      <p>Grubunuz buluşma yeri arıyor. Adınızı yazıp odaya katılın, sonra başlangıç noktanızı ekleyin. Diğer üyeler konumunuzu görmez.</p>
      <label>Adınız<input value={name} maxLength={40} autoComplete="given-name" onChange={e => setName(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && name.trim()) void enter() }} /></label>
      <button type="button" className="primary" disabled={!name.trim()} onClick={() => void enter()}>Odaya katıl</button>
      <p role="status">{joinNotice}</p>
    </fieldset>}
    {token && !guest.view && !guest.notice && <p>Oda açılıyor…</p>}
    {token && guest.view && <GuestBody view={guest.view} busy={guest.busy} act={guest.act}
      extra={<button type="button" className="secondary" onClick={async () => {
        if (!confirm('Odadan ayrılmak istiyor musunuz? Adınız ve konumunuz odadan silinir.')) return
        const left = await guest.act('leave'); if (left?.left) { forgetSeat(join); setToken('') }
      }}>Odadan ayrıl</button>} />}
    <p role="status">{guest.notice}</p><a href="/">ORTAK ana sayfa</a></main>
}

/** Older per-seat invite links (#davet=...). */
export function Guest({ token }) {
  const guest = useGuest(token)
  return <main className="guest-page planner-band"><span className="eyebrow">ORTAK</span><h1>Buluşma daveti</h1>
    {!guest.view && !guest.notice && <p>Davet açılıyor…</p>}
    {guest.view && <GuestBody view={guest.view} busy={guest.busy} act={guest.act} />}
    <p role="status">{guest.notice}</p><a href="/">ORTAK ana sayfa</a></main>
}
