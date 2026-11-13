import sharp from 'sharp';
import { mkdir } from 'node:fs/promises';

const assets = new URL('../assets/', import.meta.url);
await mkdir(assets, { recursive: true });
const source = new URL('../../frontend/public/favicon.svg', import.meta.url);
// Reuse the existing ORTAK brand, rasterized for native app stores.
await sharp(source.pathname).resize(1024, 1024).flatten({ background: '#232427' }).png().toFile(new URL('icon.png', assets).pathname);
await sharp(source.pathname).resize(256, 256).png().toFile(new URL('splash-icon.png', assets).pathname);
const foreground = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108"><g transform="translate(22 22)"><circle cx="32" cy="32" r="18" fill="none" stroke="#fff" stroke-width="4"/><path d="m19 45 26-26" fill="none" stroke="#fff" stroke-width="3"/><circle cx="32" cy="32" r="5" fill="#fff"/></g></svg>');
for (const name of ['adaptive-icon.png', 'monochrome-icon.png']) await sharp(foreground).resize(1024, 1024).png().toFile(new URL(name, assets).pathname);
