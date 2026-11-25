import assert from 'node:assert/strict';
import test from 'node:test';
import type { ConsentStorage } from '../src/consentStore';
import { forgetRoom, loadRooms, rememberRoom, renameRoom, roomLink } from '../src/roomStore';

const memory = (): ConsentStorage & { data: Map<string, string> } => {
  const data = new Map<string, string>();
  return { data, get: async k => data.get(k) ?? null, set: async (k, v) => { data.set(k, v); } };
};
const key = (c: string) => c.repeat(43);

test('saved rooms keep only name, owner key and join link, newest first, at most ten', async () => {
  const store = memory();
  assert.deepEqual(await loadRooms(store), []);
  await rememberRoom({ name: 'Cuma ekibi', key: key('a'), join: key('b') }, store);
  await rememberRoom({ name: 'Okul', key: key('c'), join: key('d') }, store);
  assert.deepEqual((await loadRooms(store)).map(r => r.name), ['Okul', 'Cuma ekibi']);
  await renameRoom(key('a'), 'Cumartesi', store);
  assert.equal((await loadRooms(store))[1]!.name, 'Cumartesi');
  await forgetRoom(key('c'), store);
  assert.deepEqual(Object.keys(JSON.parse(store.data.get('ortak-rooms')!)[0]).sort(), ['join', 'key', 'name']);
  for (let i = 0; i < 12; i++) await rememberRoom({ name: `R${i}`, key: `${i}`.padStart(43, 'x'), join: key('j') }, store);
  assert.equal((await loadRooms(store)).length, 10);
  assert.equal(roomLink(key('b')), `https://ortak.web.tr/#oda=${key('b')}`);
});

test('broken or tampered storage is ignored', async () => {
  const store = memory();
  store.data.set('ortak-rooms', '{not json');
  assert.deepEqual(await loadRooms(store), []);
  store.data.set('ortak-rooms', JSON.stringify([{ name: 'X', key: 'short', join: key('b') }, { name: 'Y', key: key('a'), join: key('b') }]));
  assert.deepEqual((await loadRooms(store)).map(r => r.name), ['Y']);
});
