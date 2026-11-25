import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { Guest, RoomGuest } from './GroupInvite'
import { Consented } from './ConsentGate'
import './styles.css'

const root = createRoot(document.getElementById('root'))
function render() {
const invite = /^#davet=([A-Za-z0-9_-]{43})$/.exec(location.hash)
const room = /^#oda=([A-Za-z0-9_-]{43})$/.exec(location.hash)
root.render(
  <React.StrictMode>
    <Consented>{room ? <RoomGuest key={room[1]} join={room[1]} /> : invite ? <Guest key={invite[1]} token={invite[1]} /> : <App />}</Consented>
  </React.StrictMode>,
)
}
render()
window.addEventListener('hashchange', render)

