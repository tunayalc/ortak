import { useEffect, useRef, useState } from 'react';
import { Alert, AppState, Share, View } from 'react-native';
import { DoorOpen, Save, Settings, Share2, Trash2, UserMinus } from 'lucide-react-native';
import { Button, Field, Heading, IconButton, Label, Notice, Stepper, styles } from './components';
import { makeParticipants, travelModes } from './domain';
import { ApiError } from './api';
import * as store from './roomStore';
import { roomLink, type SavedRoom } from './roomStore';
import { secureConsentStorage } from './secureConsentStorage';

const loadRooms = () => store.loadRooms(secureConsentStorage);
const rememberRoom = (room: SavedRoom) => store.rememberRoom(room, secureConsentStorage);
const renameRoom = (key: string, name: string) => store.renameRoom(key, name, secureConsentStorage);
const forgetRoom = (key: string) => store.forgetRoom(key, secureConsentStorage);
import type { Group, Participant } from './types';
import type { Meeting } from './useMeeting';

const modeName = (id?: string | null) => travelModes.find(m => m.id === id)?.label;

function confirm(title: string, message: string, action: string) {
  return new Promise<boolean>(resolve => Alert.alert(title, message, [
    { text: 'Vazgeç', style: 'cancel', onPress: () => resolve(false) },
    { text: action, style: 'destructive', onPress: () => resolve(true) },
  ]));
}

/** One shareable link: friends join with their own name and starting point; the host only sets weights. */
export function RoomHost({ m }: { m: Meeting }) {
  const [room, setRoom] = useState<Group | null>(null);
  const [rooms, setRooms] = useState<SavedRoom[]>([]);
  const [name, setName] = useState(''), [saveName, setSaveName] = useState('');
  const [openedKey, setOpenedKey] = useState('');
  const [working, setWorking] = useState(false), [notice, setNotice] = useState('');
  const [settings, setSettings] = useState(false);
  const busy = useRef(false), synced = useRef('');
  async function run(fn: () => Promise<void>) {
    if (busy.current || m.busy) return;
    busy.current = true; setWorking(true); setNotice('');
    try { await fn(); } catch (e) { setNotice(e instanceof Error ? e.message : 'Oda işlemi tamamlanamadı.'); }
    finally { busy.current = false; setWorking(false); }
  }
  useEffect(() => { void loadRooms().then(setRooms); void run(async () => { await m.api.connect(); const mine = await m.api.group(); setRoom(mine?.room ? mine : null); }); }, []);
  useEffect(() => {
    if (!room) return;
    const timer = setInterval(() => {
      if (busy.current || AppState.currentState !== 'active') return;
      m.api.group().then(next => setRoom(next?.room ? next : null)).catch(() => {});
    }, 5000);
    return () => clearInterval(timer);
  }, [Boolean(room)]);

  const disabled = working || !!m.busy;
  const join = room?.join || rooms.find(r => r.key === openedKey)?.join;
  const ready = room?.seats.filter(s => s.ready).length || 0;
  const results = m.results;
  const readySeats = room?.seats.filter(s => s.ready) || [];
  const signature = room ? readySeats.map(s => `${s.name}|${s.travel_mode || ''}`).join(';') : '';
  const outdated = Boolean(room && signature !== synced.current);
  const people = m.input.participants;

  async function sync() {
    const points = readySeats.length >= 2 ? await m.api.groupLocations() : [];
    synced.current = signature;
    m.setParsed([]);
    m.setInput(current => ({ ...current, participants: points.map((point, i): Participant => ({
      ...makeParticipants(points.length)[i]!, label: point.label || `Kişi ${i + 1}`, value: `${point.lat},${point.lng}`,
      travel_mode: point.travel_mode || '', place: '',
      delta_weight: current.participants.find(p => p.label === point.label)?.delta_weight ?? 1,
    })) }));
  }
  // Keep the search list in step with the room, but never swap locations under a running or finished search.
  useEffect(() => {
    if (!outdated || m.busy || m.hasScenario || busy.current) return;
    void run(sync);
  }, [signature, m.busy, m.hasScenario]);
  useEffect(() => {
    if (room) return;
    synced.current = '';
    m.setInput(current => current.participants.length ? { ...current, participants: [] } : current);
  }, [Boolean(room)]);

  async function share() {
    if (!join || !room) return;
    await Share.share({ message: `${room.name} odasına katıl, başlangıç noktanı ekle: ${roomLink(join)}` });
  }

  if (!room) return <View style={{ gap: 14 }}>
    <Label secondary>Bir bağlantı oluşturup grubunuzla WhatsApp, Telegram veya istediğiniz uygulamada paylaşın. Bağlantıyı açan herkes kendi adını ve başlangıç noktasını kendisi girer. Siz yalnızca kişilerin ağırlığını seçersiniz.</Label>
    <Field label="Oda adı" placeholder="Örn. Cuma ekibi" value={name} maxLength={40} editable={!disabled} onChangeText={setName} />
    <Button label="Oda kur" icon={DoorOpen} disabled={disabled} onPress={() => void run(async () => {
      await m.api.connect(); const created = await m.api.createRoom(name.trim() || 'Oda'); setOpenedKey(''); setRoom(created); setSaveName(created.name || '');
    })} />
    {rooms.length > 0 && <View style={{ gap: 8 }}><Heading>Kayıtlı odalarım</Heading>
      {rooms.map(r => <View key={r.key} style={[styles.between, { gap: 8 }]}>
        <View style={{ flex: 1 }}><Button label={`${r.name} odasını aç`} tone="secondary" disabled={disabled} onPress={() => void run(async () => {
          await m.api.connect(); const opened = await m.api.openRoom(r.key); setOpenedKey(r.key); setRoom(opened); setSaveName(opened.name || '');
        })} /></View>
        <IconButton label={`${r.name} kaydını sil`} icon={Trash2} disabled={disabled} onPress={() => void run(async () => {
          if (!(await confirm('Oda kaydı silinsin mi?', `"${r.name}" odası ve üye adları silinir. Bu geri alınamaz.`, 'Sil'))) return;
          try { await m.api.connect(); await m.api.forgetRoom(r.key); } catch (e) { if (!(e instanceof ApiError && e.status === 404)) throw e; }
          await forgetRoom(r.key); setRooms(await loadRooms()); setNotice('Oda kaydı silindi.');
        })} />
      </View>)}
    </View>}
    {!!notice && <Notice>{notice}</Notice>}
  </View>;

  return <View style={{ gap: 14 }}>
    <Heading>{room.name}{room.saved ? ' (kayıtlı)' : ''}</Heading>
    {join ? <Button label="Oda bağlantısını paylaş" icon={Share2} disabled={disabled} onPress={() => void run(share)} /> : <Notice error>Bu odanın bağlantısı bu cihazda yok.</Notice>}
    <Label secondary>Siz de bağlantıyı açıp kendi yerinizi ekleyebilirsiniz. Üyeler birbirinin konumunu görmez.</Label>
    <Label>{`Katılanlar (${room.seats.length}/${room.capacity || 8}), konum ekleyen: ${ready}`}</Label>
    {!room.seats.length && <Label secondary>Henüz kimse katılmadı.</Label>}
    {room.seats.map((s, i) => {
      const index = room.seats.slice(0, i + 1).filter(x => x.ready).length - 1;
      const person = s.ready && people[index]?.label === s.name ? people[index] : null;
      return <View key={i} style={{ gap: 4 }}><View style={[styles.between, { gap: 8 }]}>
        <View style={{ flex: 1 }}><Label>{s.name}</Label><Label secondary>{(s.ready ? 'Konum eklendi' : 'Konum bekleniyor') + (modeName(s.travel_mode) ? `, ${modeName(s.travel_mode)}` : '')}</Label></View>
        {!room.choices.length && <IconButton label={`${s.name} kişisini odadan çıkar`} icon={UserMinus} disabled={disabled} onPress={() => void run(async () => setRoom(await m.api.removeMember(i + 1)))} />}
      </View>
      {person && <Stepper label={`${s.name} ağırlığı`} min={0.5} max={2} step={0.5} suffix="×" value={person.delta_weight} disabled={disabled}
        onChange={delta_weight => m.setInput(current => ({ ...current, participants: current.participants.map((p, j) => j === index ? { ...p, delta_weight } : p) }))} />}
      </View>;
    })}
    {room.seats.length > 0 && <Label secondary>Ağırlığı yüksek kişiye yakın yerler öne çıkar.</Label>}
    {ready < 2 && room.seats.length > 0 && <Notice>Arama için en az iki kişinin konum eklemesi gerekiyor.</Notice>}
    {outdated && m.hasScenario && <><Notice>Odaya yeni konum eklendi. Güncel konumlarla aramak için önce mevcut buluşmayı silin.</Notice></>}
    {!room.choices.length && results && results.recommendations.length >= 2 && <Button label="Sonuçları odada oylamaya aç" tone="secondary" disabled={disabled || m.resultsStale} onPress={() => void run(async () => {
      setRoom(await m.api.groupBallot(results.scenario.id, results.recommendations.slice(0, 3).map(r => r.candidate.id)));
    })} />}
    {room.choices.length > 0 && <View style={{ gap: 6 }}><Heading>Grup oyları</Heading><Label secondary>ORTAK sıralaması değişmez.</Label>
      {room.choices.map(c => <Label key={c.id}>{c.name}: {c.votes} oy</Label>)}
      {room.choices.some(c => c.provider === 'google') && <Label secondary>Google Maps</Label>}
      {room.choices.flatMap(c => c.attributions || []).map((a, i) => <Label secondary key={i}>{a.provider}</Label>)}</View>}
    <Button label={settings ? 'Oda ayarlarını gizle' : 'Oda ayarları'} icon={Settings} tone="secondary" onPress={() => setSettings(!settings)} />
    {settings && <>
    {!room.saved ? <>
      <Field label="Sık buluşuyorsanız odayı kaydedin" placeholder="Oda adı" value={saveName} maxLength={40} editable={!disabled} onChangeText={setSaveName} />
      <Button label="Odayı kaydet" icon={Save} tone="secondary" disabled={disabled || !saveName.trim()} onPress={() => void run(async () => {
        const saved = await m.api.saveRoom(saveName.trim());
        if (saved.owner_key && (saved.join || join)) await rememberRoom({ name: saved.name || saveName.trim(), key: saved.owner_key, join: (saved.join || join)! });
        setRooms(await loadRooms()); setOpenedKey(saved.owner_key || ''); setRoom(saved);
        setNotice('Oda kaydedildi. Aynı bağlantı sonraki buluşmalarda da çalışır; konumlar her seferinde yeniden eklenir.');
      })} />
      <Label secondary>Kayıtta oda adı ile üyelerin adları ve ulaşım tercihleri tutulur; konumlar tutulmaz. 90 gün kullanılmazsa silinir.</Label>
    </> : <>
      <Field label="Oda adı" value={saveName} maxLength={40} editable={!disabled} onChangeText={setSaveName} />
      <Button label="Adı değiştir" tone="secondary" disabled={disabled || !saveName.trim() || saveName.trim() === room.name} onPress={() => void run(async () => {
        const renamed = await m.api.renameRoom(saveName.trim()); setRoom(renamed);
        if (openedKey) { await renameRoom(openedKey, renamed.name || saveName.trim()); setRooms(await loadRooms()); }
      })} />
    </>}
    <Button label={room.saved ? 'Bu buluşmayı bitir' : 'Odayı kapat'} tone="danger" disabled={disabled} onPress={() => void run(async () => {
      await m.api.closeGroup(); setRoom(null); setOpenedKey(''); setSettings(false); setNotice(room.saved ? 'Buluşma bitti; oda kayıtlı kalıyor.' : 'Oda kapatıldı.');
    })} />
    </>}
    {!!notice && <Notice>{notice}</Notice>}
  </View>;
}
