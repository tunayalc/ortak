import { useState } from 'react';
import { Linking, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ShieldCheck } from 'lucide-react-native';
import { Button, Consent, Heading, Label, Notice, Text, useTheme } from './components';
import { consentSections } from './consent';

// Shown before the app makes any network request; the approval is remembered via consentStore.
export function ConsentScreen({ onAccept }: { onAccept: () => void }) {
  const t = useTheme();
  const [checked, setChecked] = useState(false);
  const [declined, setDeclined] = useState(false);
  return <SafeAreaView style={{ flex: 1, backgroundColor: t.background }} edges={['top', 'bottom', 'left', 'right']}>
    <View style={{ flex: 1, width: '100%', maxWidth: 760, alignSelf: 'center' }}>
      <View style={{ padding: 20, gap: 4, borderBottomWidth: 1, borderBottomColor: t.divider }}>
        <Text style={{ color: t.text, fontSize: 28 }}>ORTAK'a hoş geldiniz</Text>
        <Label secondary>Başlamadan önce verilerinizin nasıl işlendiğini okuyun.</Label>
      </View>
      <ScrollView contentContainerStyle={{ padding: 20, gap: 20 }} accessibilityLabel="Veri işleme bildirimi">
        {consentSections.map(section => <View key={section.id} style={{ gap: 8 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><ShieldCheck size={18} color={t.accent} /><View style={{ flex: 1 }}><Heading>{section.title}</Heading></View></View>
          {section.items.map(item => <Label key={item}>{`\u2022 ${item}`}</Label>)}
        </View>)}
        <Button label="Gizlilik politikası" tone="secondary" onPress={() => void Linking.openURL('https://ortak.web.tr/mobile-privacy.html')} />
        <Button label="Kullanım koşulları" tone="secondary" onPress={() => void Linking.openURL('https://ortak.web.tr/mobile-terms.html')} />
        <Button label="Google gizlilik politikası" tone="secondary" onPress={() => void Linking.openURL('https://policies.google.com/privacy')} />
      </ScrollView>
      <View style={{ padding: 20, gap: 12, borderTopWidth: 1, borderTopColor: t.divider, backgroundColor: t.surface }}>
        <Consent label="Yukarıdaki bildirimin tamamını okudum, anladım ve verilerimin bu şekilde işlenmesini onaylıyorum." checked={checked} onChange={setChecked} />
        {declined ? <Notice>Onay vermeden ORTAK kullanılamaz; hiçbir konum veya tercih gönderilmedi.</Notice> : null}
        <Button label="Kabul et ve devam et" disabled={!checked} onPress={onAccept} />
        <Button label="Kabul etmiyorum" tone="secondary" onPress={() => setDeclined(true)} />
      </View>
    </View>
  </SafeAreaView>;
}
