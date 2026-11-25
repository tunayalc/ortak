import { useState } from 'react';
import { View } from 'react-native';
import { Search } from 'lucide-react-native';
import { Button, Label, Notice } from './components';
import type { MobileApi } from './api';
import type { PlaceResult } from './types';

/** Search a typed place name ("Mogan Gölü") and pick one of Google's matches. */
export function PlaceSearch({ query, api, disabled, onPick }: { query: string; api: MobileApi; disabled?: boolean; onPick: (place: PlaceResult) => void }) {
  const [results, setResults] = useState<PlaceResult[] | null>(null);
  const [working, setWorking] = useState(false), [notice, setNotice] = useState('');
  async function search() {
    setWorking(true); setNotice(''); setResults(null);
    try {
      await api.connect();
      const found = await api.searchPlaces(query);
      setResults(found);
      if (!found.length) setNotice('Sonuç bulunamadı. Daha ayrıntılı yazmayı deneyin (ör. "Mogan Gölü, Gölbaşı").');
    } catch (e) { setNotice(e instanceof Error ? e.message : 'Yer arama tamamlanamadı.'); }
    finally { setWorking(false); }
  }
  return <View style={{ gap: 8 }}>
    <Button label="Yer adıyla ara" icon={Search} tone="secondary" loading={working} disabled={disabled || working || query.trim().length < 2 || query.includes('://')} onPress={() => void search()} />
    {results?.map((place, i) => <Button key={i} tone="secondary" label={place.address && place.address !== place.name ? `${place.name}, ${place.address}` : place.name}
      onPress={() => { setResults(null); onPick(place); }} />)}
    {results?.length ? <Label secondary>Google Maps</Label> : null}
    {!!notice && <Notice>{notice}</Notice>}
  </View>;
}
