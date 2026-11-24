import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { Guest } from './GroupInvite'
import { Consented } from './ConsentGate'
import './styles.css'

const root = createRoot(document.getElementById('root'))
function render() {
const match = /^#davet=([A-Za-z0-9_-]{43})$/.exec(location.hash)
root.render(
  <React.StrictMode>
    <Consented>{match ? <Guest key={match[1]} token={match[1]} /> : <App />}</Consented>
  </React.StrictMode>,
)
}
render()
window.addEventListener('hashchange', render)

