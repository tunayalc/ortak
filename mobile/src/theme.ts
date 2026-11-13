export const light = {
  background: '#ffffff', surface: '#ffffff', text: '#232427', secondary: '#55565a',
  border: '#939499', primary: '#232427', onPrimary: '#ffffff', tint: '#f0f0f1',
  accent: '#246249', accentTint: '#edf5f0', warning: '#76500a', warningTint: '#fff0cf',
  error: '#9d2942', errorTint: '#fbe6eb', muted: '#96979b', divider: '#dedee0',
};
export const dark: typeof light = {
  background: '#151517', surface: '#151517', text: '#f5f5f5', secondary: '#c2c2c7',
  border: '#77777f', primary: '#f5f5f5', onPrimary: '#151517', tint: '#28282c',
  accent: '#98dace', accentTint: '#1c3a34', warning: '#f8d488', warningTint: '#42351d',
  error: '#ffb2c2', errorTint: '#452832', muted: '#83838a', divider: '#3d3d42',
};
export type Theme = typeof light;
