import { useState } from 'react';
import { View } from 'react-native';
import type { Recommendation } from './types';
import { Button, Label } from './components';

function minutes(n?: number) { return n !== undefined && Number.isFinite(n) ? Number(n.toFixed(1)).toLocaleString('tr-TR') + ' dk' : 'Bilinmiyor'; }
export function PlaceComparison({ items }: { items: Recommendation[] }) {
  const [open, setOpen] = useState(false);
  const [ids, setIds] = useState(['', '']);
  if (items.length < 2) return null;
  const a = items.find(r => r.candidate.id === ids[0]) || items[0]!;
  const others = items.filter(r => r !== a);
  const b = others.find(r => r.candidate.id === ids[1]) || others[0]!;
  const users = new Map([...a.per_user, ...b.per_user].map(p => [p.user_id, p.label]));
  const rows: Array<[string, number | undefined, number | undefined]> = [['Ortalama yol', a.t_avg_minutes, b.t_avg_minutes], ['En uzun yol', a.t_max_minutes, b.t_max_minutes]];
  users.forEach((label, id) => rows.push([label, a.per_user.find(p => p.user_id === id)?.raw_duration_minutes, b.per_user.find(p => p.user_id === id)?.raw_duration_minutes]));
  return <View style={{ gap: 12 }}><Button label={open ? 'Karşılaştırmayı kapat' : 'İki mekânı karşılaştır'} tone="secondary" onPress={() => setOpen(!open)} />
    {open && <>{[a,b].map((r,i) => <View key={i} style={{ gap: 6 }}><Label>{i ? 'B' : 'A'} mekânı: {r.candidate.name}</Label>
      {(i ? others : items).map(x => <Button key={x.candidate.id} label={x.candidate.name} tone={x === r ? 'primary' : 'secondary'} onPress={() => setIds(i ? [a.candidate.id, x.candidate.id] : [x.candidate.id, b.candidate.id])} />)}</View>)}
      {rows.map(([label,x,y], i) => { const d = (Math.round((y ?? NaN)*10) - Math.round((x ?? NaN)*10))/10;
        return <View key={i}><Label>{label}</Label><Label secondary>A: {minutes(x)} / B: {minutes(y)}</Label><Label>{!Number.isFinite(d) ? 'Karşılaştırılamıyor' : d === 0 ? 'Aynı' : 'B: ' + minutes(Math.abs(d)) + (d < 0 ? ' daha kısa' : ' daha uzun')}</Label></View>;
      })}</>}
  </View>;
}
