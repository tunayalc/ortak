import { useState } from 'react'
import { LocateFixed, Loader2, Search } from 'lucide-react'
import { api } from './api'

export function getDeviceLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) { reject(new Error('Bu tarayıcı konum paylaşımını desteklemiyor. Yer adı veya bağlantı girebilirsiniz.')); return }
    navigator.geolocation.getCurrentPosition(
      position => resolve({ lat: +position.coords.latitude.toFixed(6), lng: +position.coords.longitude.toFixed(6) }),
      error => reject(new Error(error.code === 1
        ? 'Konum izni verilmedi. Tarayıcı ayarlarından izin verebilir veya yer adıyla arayabilirsiniz.'
        : 'Konum alınamadı. Yer adıyla arayabilir veya bağlantı girebilirsiniz.')),
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 },
    )
  })
}

/** Text field for a starting point: type a place name and search, use the device location, or paste a link. */
export function PlacePicker({ label, value, place, onChange, onPick, disabled, placeholder = 'Ankara Kalesi, Google Maps linki veya 39.92,32.85' }) {
  const [results, setResults] = useState(null)
  const [working, setWorking] = useState('')
  const [notice, setNotice] = useState('')
  async function run(kind, task) {
    setWorking(kind); setNotice('')
    try { await task() } catch (e) { setNotice(e.message) } finally { setWorking('') }
  }
  const search = () => run('search', async () => {
    const found = await api.searchPlaces(value)
    setResults(found)
    if (!found.length) setNotice('Sonuç bulunamadı. Daha ayrıntılı yazmayı deneyin (ör. "Mogan Gölü, Gölbaşı").')
  })
  const locate = () => run('locate', async () => {
    const point = await getDeviceLocation()
    setResults(null)
    onPick({ name: 'Bulunduğum konum', address: '', ...point })
  })
  return <div className="place-picker">
    <label className="location-input">{label}
      <input placeholder={placeholder} value={value} disabled={disabled} maxLength={2048}
        onChange={e => { onChange(e.target.value); setResults(null) }}
        onKeyDown={e => { if (e.key === 'Enter' && value.trim().length >= 2) { e.preventDefault(); void search() } }} />
    </label>
    <div className="place-actions">
      <button type="button" className="secondary" disabled={disabled || !!working || value.trim().length < 2} onClick={search}>
        {working === 'search' ? <Loader2 size={16} className="spin" /> : <Search size={16} />} Ara
      </button>
      <button type="button" className="secondary" disabled={disabled || !!working} onClick={locate}>
        {working === 'locate' ? <Loader2 size={16} className="spin" /> : <LocateFixed size={16} />} Konumum
      </button>
    </div>
    {place && <small className="place-chosen">Seçilen: {place}</small>}
    {results?.length > 0 && <ul className="place-results" aria-label="Yer arama sonuçları">
      {results.map((item, i) => <li key={i}><button type="button" onClick={() => { setResults(null); onPick(item) }}>
        <strong>{item.name}</strong>{item.address && item.address !== item.name && <span>{item.address}</span>}
      </button></li>)}
      <li className="place-attribution">Google Maps</li>
    </ul>}
    {notice && <small className="place-notice" role="status">{notice}</small>}
  </div>
}

export const weightOptions = [[0.5, 'Düşük'], [1, 'Normal'], [1.5, 'Yüksek'], [2, 'Çok yüksek']]

/** How much a person's distance counts: higher means places nearer to them rank higher. */
export function WeightSelect({ name, value, onChange, disabled }) {
  const current = Number(value ?? 1)
  const options = weightOptions.some(([v]) => v === current) ? weightOptions : [...weightOptions, [current, `${current}×`]].sort((a, b) => a[0] - b[0])
  return <label className="weight-select">Ağırlık
    <select aria-label={`${name} ağırlığı`} value={String(current)} disabled={disabled} onChange={e => onChange(Number(e.target.value))}>
      {options.map(([v, text]) => <option key={v} value={String(v)}>{text}</option>)}
    </select>
  </label>
}
