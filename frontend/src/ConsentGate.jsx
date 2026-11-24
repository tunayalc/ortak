import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { CONSENT_VERSION, consentSections } from './consent'

const KEY = 'ortak-consent'

export function readConsent() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(KEY) || 'null')
    return saved?.version === CONSENT_VERSION
  } catch {
    return false
  }
}

function saveConsent() {
  try {
    window.localStorage.setItem(KEY, JSON.stringify({ version: CONSENT_VERSION, accepted_at: new Date().toISOString() }))
  } catch {
    // Storage may be blocked; the notice is then shown again on the next visit.
  }
}

export function Consented({ children }) {
  const [accepted, setAccepted] = useState(readConsent)
  return accepted ? children : <ConsentGate onAccept={() => setAccepted(true)} />
}

export default function ConsentGate({ onAccept }) {
  const [checked, setChecked] = useState(false)
  const [declined, setDeclined] = useState(false)
  return (
    <main className="consent-gate" aria-labelledby="consent-title">
      <div className="consent-card">
        <div className="brand-mark">
          <img className="brand-symbol" src="/favicon.svg" alt="" />
          <div><h1 id="consent-title">ORTAK'a hoş geldiniz</h1><span>Başlamadan önce verilerinizin nasıl işlendiğini okuyun.</span></div>
        </div>
        <div className="consent-scroll" tabIndex={0} role="region" aria-label="Veri işleme bildirimi">
          {consentSections.map(section => (
            <section key={section.id}>
              <h2><ShieldCheck size={16} aria-hidden="true" /> {section.title}</h2>
              <ul>{section.items.map(item => <li key={item}>{item}</li>)}</ul>
            </section>
          ))}
          <p><a href="/privacy.html" target="_blank" rel="noreferrer">Gizlilik</a> · <a href="/terms.html" target="_blank" rel="noreferrer">Kullanım koşulları</a> · <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">Google Gizlilik Politikası</a></p>
        </div>
        <label className="consent-check">
          <input type="checkbox" checked={checked} onChange={event => setChecked(event.target.checked)} />
          Yukarıdaki bildirimin tamamını okudum, anladım ve verilerimin bu şekilde işlenmesini onaylıyorum.
        </label>
        {declined && <p className="privacy-note" role="status">Onay vermeden ORTAK kullanılamaz; hiçbir konum veya tercih gönderilmedi. Fikrinizi değiştirirseniz kutuyu işaretleyip devam edebilirsiniz.</p>}
        <div className="action-row">
          <button className="primary" disabled={!checked} onClick={() => { saveConsent(); onAccept() }}>Kabul et ve devam et</button>
          <button className="secondary" onClick={() => setDeclined(true)}>Kabul etmiyorum</button>
        </div>
      </div>
    </main>
  )
}
