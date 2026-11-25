// Saved rooms (name, owner key, join token) and joined-room seat tokens, kept in this browser only.
const ROOMS = 'ortak-rooms'
const SEATS = 'ortak-seats'

function read(key) {
  try { const value = JSON.parse(localStorage.getItem(key) || 'null'); return value && typeof value === 'object' ? value : null } catch { return null }
}
function write(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* Private mode: the room still works for this visit. */ }
}

export function savedRooms() {
  const rooms = read(ROOMS)
  return Array.isArray(rooms) ? rooms.filter(r => r && typeof r.key === 'string' && typeof r.name === 'string') : []
}
export function rememberRoom(room) {
  write(ROOMS, [room, ...savedRooms().filter(r => r.key !== room.key)].slice(0, 20))
}
export function renameSavedRoom(key, name) {
  write(ROOMS, savedRooms().map(r => r.key === key ? { ...r, name } : r))
}
export function forgetRoom(key) {
  write(ROOMS, savedRooms().filter(r => r.key !== key))
}

export function seatFor(join) { return read(SEATS)?.[join] || '' }
export function rememberSeat(join, token) { write(SEATS, { ...(read(SEATS) || {}), [join]: token }) }
export function forgetSeat(join) { const seats = { ...(read(SEATS) || {}) }; delete seats[join]; write(SEATS, seats) }

export function roomLink(join) { return `${location.origin}/#oda=${join}` }
