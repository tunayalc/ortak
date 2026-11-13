import test from 'node:test';
import assert from 'node:assert/strict';
import { light, dark } from '../src/theme';

function luminance(hex: string) {
  const channels = hex.slice(1).match(/../g)!.map(value => parseInt(value, 16) / 255)
    .map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return channels[0]! * 0.2126 + channels[1]! * 0.7152 + channels[2]! * 0.0722;
}

function contrast(foreground: string, background: string) {
  const a = luminance(foreground), b = luminance(background);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

for (const [name, t] of Object.entries({ light, dark })) {
  test(`${name}: text and button colors meet normal text contrast`, () => {
    for (const [fg, bg] of [[t.text, t.background], [t.secondary, t.surface], [t.onPrimary, t.primary],
      [t.secondary, t.tint], [t.error, t.errorTint], [t.accent, t.accentTint], [t.warning, t.warningTint]]) {
      assert.ok(contrast(fg!, bg!) >= 4.5, `${fg} on ${bg}`);
    }
  });
  test(`${name}: input borders remain distinguishable`, () => {
    assert.ok(contrast(t.border, t.surface) >= 3);
  });
}
