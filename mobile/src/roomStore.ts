import type { ConsentStorage } from './consentStore';

// Saved rooms (name, owner key, join token) stay on this device in the secure store.
export type SavedRoom = { name: string; key: string; join: string };
const KEY = 'ortak-rooms';
const MAX = 10;

function valid(room: unknown): room is SavedRoom {
  const r = room as SavedRoom;
  return !!r && typeof r.name === 'string' && /^[A-Za-z0-9_-]{43}$/.test(r.key) && /^[A-Za-z0-9_-]{43}$/.test(r.join);
}

export async function loadRooms(storage: ConsentStorage): Promise<SavedRoom[]> {
  try { const value = JSON.parse((await storage.get(KEY)) || '[]'); return Array.isArray(value) ? value.filter(valid) : []; } catch { return []; }
}

async function write(rooms: SavedRoom[], storage: ConsentStorage) {
  await storage.set(KEY, JSON.stringify(rooms.slice(0, MAX)));
}

export async function rememberRoom(room: SavedRoom, storage: ConsentStorage) {
  await write([room, ...(await loadRooms(storage)).filter(r => r.key !== room.key)], storage);
}
export async function renameRoom(key: string, name: string, storage: ConsentStorage) {
  await write((await loadRooms(storage)).map(r => r.key === key ? { ...r, name } : r), storage);
}
export async function forgetRoom(key: string, storage: ConsentStorage) {
  await write((await loadRooms(storage)).filter(r => r.key !== key), storage);
}
export const roomLink = (join: string) => `https://ortak.web.tr/#oda=${join}`;
