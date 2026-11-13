import { useContext, createContext, type ReactNode } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, Switch, Text as NativeText, TextInput, View, useWindowDimensions, type TextInputProps, type TextProps } from 'react-native';
import Slider from '@react-native-community/slider';
import { Check, Minus, Plus, type LucideIcon } from 'lucide-react-native';
import { light, type Theme } from './theme';

export const ThemeContext = createContext<Theme>(light);
export const useTheme = () => useContext(ThemeContext);
const fontFamily = Platform.select({ ios: 'Helvetica Neue', android: 'sans-serif', default: 'Helvetica Neue, Arial, sans-serif' });

export function Text({ style, ...props }: TextProps) {
  return <NativeText {...props} style={[{ fontFamily, letterSpacing: 0 }, style]} />;
}

export function Label({ children, secondary = false }: { children: ReactNode; secondary?: boolean }) {
  const t = useTheme();
  return <Text style={{ color: secondary ? t.secondary : t.text, fontSize: 14, lineHeight: 21, letterSpacing: 0 }}>{children}</Text>;
}
export function Heading({ children }: { children: ReactNode }) {
  const t = useTheme();
  return <Text accessibilityRole="header" style={{ fontSize: 21, lineHeight: 28, fontWeight: '500', color: t.text }}>{children}</Text>;
}
export function Section({ children }: { children: ReactNode }) {
  const t = useTheme();
  return <View style={{ paddingVertical: 24, gap: 18, borderBottomWidth: 1, borderBottomColor: t.divider }}>{children}</View>;
}
export function Button({ label, icon: Icon, onPress, disabled, tone = 'primary', loading = false }: {
  label: string; icon?: LucideIcon; onPress: () => void; disabled?: boolean; tone?: 'primary' | 'secondary' | 'danger'; loading?: boolean;
}) {
  const t = useTheme();
  const color = tone === 'primary' ? t.onPrimary : tone === 'danger' ? t.error : t.primary;
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled || loading, busy: loading }} aria-disabled={!!disabled || loading} aria-busy={loading}
    disabled={disabled || loading} onPress={onPress} style={({ pressed }) => ({ ...styles.button, borderWidth: 1, borderColor: tone === 'primary' ? t.primary : tone === 'danger' ? t.error : t.border, backgroundColor: tone === 'primary' ? t.primary : tone === 'danger' ? t.errorTint : pressed ? t.tint : t.surface, opacity: disabled ? 0.5 : pressed ? 0.85 : 1 })}>
    {loading ? <ActivityIndicator color={color} /> : Icon ? <Icon size={19} color={color} /> : null}
    <Text style={{ fontSize: 14, fontWeight: '500', color, flexShrink: 1, textAlign: 'center' }}>{label}</Text>
  </Pressable>;
}
export function IconButton({ label, icon: Icon, onPress, disabled }: { label: string; icon: LucideIcon; onPress: () => void; disabled?: boolean }) {
  const t = useTheme();
  return <Pressable accessibilityLabel={label} accessibilityRole="button" accessibilityState={{ disabled: !!disabled }} aria-disabled={!!disabled} disabled={disabled} onPress={onPress}
    style={({ pressed }) => ({ width: 44, height: 44, borderRadius: 2, alignItems: 'center', justifyContent: 'center', backgroundColor: pressed ? t.tint : 'transparent', opacity: disabled ? 0.4 : 1 })}>
    <Icon color={t.primary} size={21} strokeWidth={1.5} />
  </Pressable>;
}
export function Field({ label, ...props }: TextInputProps & { label: string }) {
  const t = useTheme();
  return <View style={{ gap: 6, flexGrow: 1, minWidth: 0 }}><Label>{label}</Label><TextInput accessibilityLabel={label} autoCorrect={false}
    placeholderTextColor={t.secondary} {...props} style={[styles.input, { color: t.text, backgroundColor: t.surface, borderColor: t.border, opacity: props.editable === false ? 0.65 : 1 }, props.style]} /></View>;
}
export function Notice({ children, error = false }: { children: ReactNode; error?: boolean }) {
  const t = useTheme();
  return <View accessibilityRole={error ? 'alert' : 'text'} accessibilityLiveRegion="polite" style={{ padding: 14, borderRadius: 2, backgroundColor: error ? t.errorTint : t.tint }}>
    <Text style={{ fontSize: 14, lineHeight: 21, color: error ? t.error : t.secondary }}>{children}</Text>
  </View>;
}
export function Segmented({ items, value, onChange, disabled }: { items: string[]; value: string; onChange: (value: string) => void; disabled?: boolean }) {
  const t = useTheme();
  const { width, fontScale } = useWindowDimensions();
  const itemWidth = Math.min((items.length > 4 ? 104 : 80) * Math.max(1, fontScale), Math.min(width, 760) - 40);
  return <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4 }} accessibilityRole="radiogroup">{items.map(item => <Pressable key={item}
    accessibilityRole="radio" accessibilityState={{ checked: item === value, disabled: !!disabled }} aria-checked={item === value} aria-disabled={!!disabled} disabled={disabled} onPress={() => onChange(item)}
    style={{ flexGrow: 1, flexBasis: itemWidth, minWidth: itemWidth, minHeight: 44, borderRadius: 2, justifyContent: 'center', alignItems: 'center', padding: 8, backgroundColor: item === value ? t.primary : t.surface, borderWidth: 1, borderColor: item === value ? t.primary : t.border }}>
    <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.85} style={{ color: item === value ? t.onPrimary : t.text, textAlign: 'center', fontSize: 14, fontWeight: item === value ? '500' : '400' }}>{item}</Text>
  </Pressable>)}</View>;
}
export function WeightSlider({ label, value, onChange, disabled, suffix = '' }: { label: string; value: number; onChange: (n: number) => void; disabled?: boolean; suffix?: string }) {
  const t = useTheme();
  return <View style={{ gap: 2 }}><View style={styles.between}><Label>{label}</Label><Text style={{ color: t.primary, fontWeight: '700', fontVariant: ['tabular-nums'] }}>{Math.round(value)}{suffix}</Text></View>
    <Slider accessibilityLabel={label} accessibilityValue={{ min: 0, max: 100, now: value, text: `${Math.round(value)} ağırlık` }} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value} aria-valuetext={`${Math.round(value)} ağırlık`} minimumValue={0} maximumValue={100} step={1}
      value={value} onValueChange={onChange} disabled={disabled} minimumTrackTintColor={t.primary} maximumTrackTintColor={t.border} thumbTintColor={t.primary} style={{ height: 44, width: '100%' }} />
  </View>;
}
export function Stepper({ label, value, onChange, min, max, step = 1, disabled, suffix = '' }: { label: string; value: number; onChange: (n: number) => void; min: number; max: number; step?: number; disabled?: boolean; suffix?: string }) {
  const t = useTheme();
  return <View style={styles.between}><View style={{ flex: 1 }}><Label>{label}</Label></View><View style={{ flexDirection: 'row', alignItems: 'center' }}>
    <IconButton label={`${label}: azalt`} icon={Minus} onPress={() => onChange(Math.max(min, value - step))} disabled={disabled || value <= min} />
    <Text accessibilityLabel={`${label}: ${value}${suffix}`} style={{ width: 49, textAlign: 'center', fontSize: 16, color: t.text, fontWeight: '700', fontVariant: ['tabular-nums'] }}>{value.toLocaleString('tr-TR')}{suffix}</Text>
    <IconButton label={`${label}: artır`} icon={Plus} onPress={() => onChange(Math.min(max, value + step))} disabled={disabled || value >= max} />
  </View></View>;
}
export function Consent({ label, checked, onChange, disabled }: { label: string; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  const t = useTheme();
  return <Pressable accessibilityRole="checkbox" accessibilityLabel={label} accessibilityState={{ checked, disabled: !!disabled }} aria-checked={checked} aria-disabled={!!disabled} disabled={disabled} onPress={() => onChange(!checked)} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, minHeight: 44, paddingVertical: 8 }}>
    <View style={{ marginTop: 2, height: 24, width: 24, borderRadius: 4, borderWidth: 1, borderColor: t.primary, backgroundColor: checked ? t.primary : t.surface, alignItems: 'center', justifyContent: 'center' }}>{checked ? <Check size={18} color={t.onPrimary} /> : null}</View>
    <Text style={{ flex: 1, color: t.secondary, fontSize: 14, lineHeight: 21 }}>{label}</Text>
  </Pressable>;
}
export function Toggle({ label, value, onChange, disabled }: { label: string; value: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  const t = useTheme();
  return <View style={styles.between}><View style={{ flex: 1 }}><Label>{label}</Label></View><Switch accessibilityLabel={label} value={value} onValueChange={onChange} disabled={disabled} trackColor={{ true: t.primary, false: t.border }} /></View>;
}
export const styles = StyleSheet.create({
  between: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  button: { minHeight: 48, paddingHorizontal: 16, paddingVertical: 12, borderRadius: 2, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  input: { minHeight: 48, borderRadius: 2, borderWidth: 1, padding: 12, fontSize: 16, fontFamily, letterSpacing: 0 },
});
