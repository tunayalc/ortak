import { useState } from 'react';
import { Share, View } from 'react-native';
import { Button, Heading, Label, Notice, Section } from './components';
import type { Group } from './types';
import type { Meeting } from './useMeeting';
import { makeParticipants } from './domain';

export function GroupHost({m}: {m:Meeting}) {
  const [group,setGroup] = useState<Group|null>(null), [open,setOpen] = useState(false);
  const [working,setWorking] = useState(false), [notice,setNotice] = useState('');
  async function run(fn:()=>Promise<void>) {
    if(working || m.busy) return;
    setWorking(true); setNotice('');
    try { await fn(); } catch(e) { setNotice(e instanceof Error ? e.message : 'Davet işlemi tamamlanamadı.'); } finally { setWorking(false); }
  }
  const disabled = working || !!m.busy;
  const results = m.results;
  return <Section><Button label="Katılımcı davetleri ve oylama" tone="secondary" disabled={disabled} onPress={()=>void run(async()=>{
    if (!open) setGroup(await m.api.group()); setOpen(!open);
  })}/>{open && <><Heading>Grup daveti</Heading>
    <Label secondary>Her kişiye yalnızca kendi bağlantısını gönderin. Bu bağlantıyla başlangıç noktası ve oy değiştirilebilir. Davet iki saat içinde kapanır.</Label>
    {!group ? <Button label={m.input.participants.length + ' kişilik davet oluştur'} disabled={disabled} onPress={()=>void run(async()=>setGroup(await m.api.createGroup(m.input.participants.length)))}/> : <>
      {group.seats.map((s,i)=><Button key={s.token} label={'Kişi '+(i+1)+' davetini paylaş ('+(s.ready?'konum eklendi':'bekleniyor')+')'} tone="secondary" disabled={disabled} onPress={()=>void run(async()=>{await Share.share({message:'https://ortak.web.tr/#davet='+s.token});})}/>)}
      <Button label="Başlangıç noktalarını kullan" disabled={disabled || m.hasScenario || !group.seats.every(s=>s.ready)} onPress={()=>void run(async()=>{
        const points=await m.api.groupLocations(); m.setParsed([]); m.setConsent(false);
        m.setInput(current=>({...current,participants:makeParticipants(points.length).map((p,i)=>({...p,value:points[i]!.lat+','+points[i]!.lng}))}));
        setNotice('Konumlar aktarıldı. Henüz arama yapılmadı.');
      })}/>
      {!group.choices.length && <Button label="Sonuçları oylamaya aç" disabled={disabled || !results || results.recommendations.length < 2 || m.resultsStale} onPress={()=>void run(async()=>{
        if(results) setGroup(await m.api.groupBallot(results.scenario.id,results.recommendations.slice(0,3).map(r=>r.candidate.id)));
      })}/>}
      {group.choices.length>0 && <View><Heading>Grup oyları</Heading><Label secondary>ORTAK sıralaması değişmez.</Label>{group.choices.map(c=><Label key={c.id}>{c.name}: {c.votes} oy</Label>)}
        {group.choices.some(c=>c.provider==='google') && <Label secondary>Google Maps</Label>}
        {group.choices.flatMap(c=>c.attributions || []).map((a,i)=><Label secondary key={i}>{a.provider}</Label>)}</View>}
      <Button label="Daveti kapat" tone="danger" disabled={disabled} onPress={()=>void run(async()=>{await m.api.closeGroup();setGroup(null);})}/></>}
    <Button label="Davet durumunu yenile" disabled={disabled} tone="secondary" onPress={()=>void run(async()=>setGroup(await m.api.group()))}/></>}
    {!!notice && <Notice>{notice}</Notice>}</Section>;
}
