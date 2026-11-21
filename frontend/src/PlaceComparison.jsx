import { useState } from 'react'

const minutes = n => Number.isFinite(n) ? n.toLocaleString('tr-TR', { maximumFractionDigits: 1 }) + ' dk' : 'Bilinmiyor'
function difference(a, b) {
  if (![a, b].every(Number.isFinite)) return 'Karşılaştırılamıyor'
  const d = (Math.round(b * 10) - Math.round(a * 10)) / 10
  return d === 0 ? 'Aynı' : minutes(Math.abs(d)) + (d < 0 ? ' daha kısa' : ' daha uzun')
}

export default function PlaceComparison({ items }) {
  const [ids, setIds] = useState(['', ''])
  if (items.length < 2) return null
  const a = items.find(r => r.candidate.id === ids[0]) || items[0]
  const others = items.filter(r => r !== a)
  const b = others.find(r => r.candidate.id === ids[1]) || others[0]
  const people = new Map([...a.per_user, ...b.per_user].map(p => [p.user_id, p.label]))
  const rows = [['Ortalama yol', a.t_avg_minutes, b.t_avg_minutes], ['En uzun yol', a.t_max_minutes, b.t_max_minutes],
    ...Array.from(people, ([id, label]) => [label, ...[a, b].map(r => r.per_user.find(p => p.user_id === id)?.raw_duration_minutes)])]
  return <details className="planner-band comparison"><summary>İki mekânı karşılaştır</summary>
    <div className="planner-fields">{[a, b].map((r, i) => <label key={i}>{i ? 'B mekânı' : 'A mekânı'}
      <select value={r.candidate.id} onChange={e => setIds(i ? [a.candidate.id, e.target.value] : [e.target.value, b.candidate.id])}>
        {(i ? others : items).map(x => <option key={x.candidate.id} value={x.candidate.id}>{x.candidate.name}</option>)}</select></label>)}</div>
    <dl aria-live="polite">{rows.map(([label, x, y], i) => <div key={i}><dt>{label}</dt><dd>A: {minutes(x)} / B: {minutes(y)}<br/><strong>B: {difference(x, y)}</strong></dd></div>)}</dl>
  </details>
}
