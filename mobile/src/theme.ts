// "Deniz" palette: fresh teal with a warm yellow highlight. Text pairs meet WCAG AA (4.5:1),
// borders 3:1, in both modes.
export const light = {
  background: '#F4FBF9', surface: '#ffffff', text: '#0F2E2A', secondary: '#3E5E59',
  border: '#76948F', primary: '#0B7A6E', onPrimary: '#ffffff', tint: '#DDF3EE',
  accent: '#0A6B61', accentTint: '#E3F5F1', warning: '#76500a', warningTint: '#FFF1CC',
  error: '#9d2942', errorTint: '#fbe6eb', muted: '#54706B', divider: '#D5E7E3',
};
export const dark: typeof light = {
  background: '#0E1E1C', surface: '#132826', text: '#EAF7F4', secondary: '#B5D3CE',
  border: '#5E7F7A', primary: '#3CCFBC', onPrimary: '#062421', tint: '#1B3A36',
  accent: '#7FE0D2', accentTint: '#173B36', warning: '#FFD27A', warningTint: '#3E321A',
  error: '#ffb2c2', errorTint: '#452832', muted: '#8FB0AB', divider: '#24413D',
};
export type Theme = typeof light;
