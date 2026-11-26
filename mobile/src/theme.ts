// Red accents on white (light) or neutral near-black (dark). Text pairs meet WCAG AA (4.5:1), borders 3:1.
export const light = {
  background: '#FFFFFF', surface: '#ffffff', text: '#1A1A1A', secondary: '#4A4A4A',
  border: '#8A8A8A', primary: '#D90F1C', onPrimary: '#ffffff', tint: '#FDECEC',
  accent: '#B3101B', accentTint: '#F6F6F6', warning: '#76500a', warningTint: '#FFF1CC',
  error: '#9A0F18', errorTint: '#FDECEC', muted: '#5F5F5F', divider: '#E4E4E4',
};
export const dark: typeof light = {
  background: '#121212', surface: '#1E1E1E', text: '#F5F5F5', secondary: '#C8C8C8',
  border: '#6E6E6E', primary: '#FF5A5F', onPrimary: '#000000', tint: '#2C2C2C',
  accent: '#FF8A8E', accentTint: '#242424', warning: '#FFD27A', warningTint: '#3E321A',
  error: '#FFB3B6', errorTint: '#3A2224', muted: '#A0A0A0', divider: '#333333',
};
export type Theme = typeof light;
