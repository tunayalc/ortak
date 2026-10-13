import {
  BarChart3,
  CheckCircle2,
  Clock3,
  DollarSign,
  ExternalLink,
  Filter,
  Info,
  Link as LinkIcon,
  Loader2,
  MapPin,
  Moon,
  Navigation,
  Play,
  RefreshCcw,
  Route,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Star,
  Sun,
  Target,
  Trash2,
  Users,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'

const categories = [
  { value: 'cafe', label: 'Kafe' },
  { value: 'restaurant', label: 'Restoran' },
  { value: 'library', label: 'Kütüphane' },
  { value: 'park', label: 'Park' },
  { value: 'museum', label: 'Müze' },
]

const modes = [
  { value: 'driving', label: 'Araç' },
  { value: 'walking', label: 'Yürüme' },
  { value: 'transit', label: 'Toplu taşıma' },
  { value: 'bicycling', label: 'Bisiklet' },
]

const criteriaProfiles = [
  { id: 'balanced', label: 'Dengeli', helper: 'Puan, fiyat ve yakınlık dengeli', weights: { rating: 34, cost: 33, proximity: 33 } },
  { id: 'rating', label: 'Puan öncelikli', helper: 'Mekân puanı daha etkili', weights: { rating: 60, cost: 20, proximity: 20 } },
  { id: 'cost', label: 'Fiyat öncelikli', helper: 'Düşük maliyet daha etkili', weights: { rating: 20, cost: 60, proximity: 20 } },
  { id: 'proximity', label: 'Yakınlık öncelikli', helper: 'Kişilere yakınlık daha etkili', weights: { rating: 20, cost: 20, proximity: 60 } },
]

const pipelineSteps = [
  { id: 'scenario', label: 'Senaryo' },
  { id: 'candidates', label: 'Adaylar' },
  { id: 'routes', label: 'Rotalar' },
  { id: 'recommend', label: 'Skor' },
]

const busyLabels = {
  scenario: 'Senaryo hazırlanıyor',
  candidates: 'Adaylar aranıyor',
  routes: 'Rotalar hesaplanıyor',
  recommend: 'Skorlanıyor',
  experiment: 'Deney çalışıyor',
  parse: 'Konumlar doğrulanıyor',
  interpret: 'Tercih yorumlanıyor',
}

const reportDraft = [
  'Kullanıcı Tercihi ve Ağırlıklandırma Mantığı: ORTAK ürün ekranında karar, mekân puanı, fiyat uygunluğu ve kişilere yakınlık kriterlerinin ayrı ağırlıklandırılmasıyla verilir. Kullanıcı bu üç kriteri doğrudan yönetir.',
  'Kişi Konumu Girişi: Kullanıcı kişi sayısı kadar Google Maps linki veya lat,lng koordinatı verebilir. Gerçek kişi konumları session-only tutulur; ham linkler ve rota metrikleri SQLite veritabanına yazılmaz.',
  'Kriter Bazlı Delta Modeli: final_score = w_rating * rating_norm + w_cost * cost_norm + w_proximity * proximity_norm formülü kullanılır. proximity_norm, kişi yakınlık deltalarıyla ağırlıklandırılmış kişi yakınlığı toplamıdır.',
  'Rapor Uyumu: λ modeli araştırma ve karşılaştırma katmanında korunur. Böylece rapordaki adalet-verim ekseni kaybolmaz; ancak ürün ekranında kullanıcının doğrudan seçim iradesi öne çıkar.',
  'Deney Planı: Model; rastgele seçim ortalaması, coğrafi merkez, minimum-toplam süre ve minimum-maksimum süre yaklaşımlarıyla karşılaştırılır. t_max, t_avg, t_sum ve varyans metrikleri birlikte raporlanır.',
  'Risk ve Tutarlılık: Link modunda gerçek kişi verisi kullanıcı tarafından açıkça sağlanmış kabul edilir; yine de ham link kalıcı depolanmaz. Yol tarifi linkleri etik kapsam gereği yalnızca hedef mekânı içerir.',
]

const initialScenario = {
  city: 'Ankara',
  category: 'cafe',
  group_size: 3,
  travel_mode: 'driving',
  radius_m: 2500,
  seed: 42,
}

const initialPriorityWeights = {
  report: 70,
  quality: 10,
  cost: 10,
  focus: 10,
}

const initialCriterionWeights = {
  rating: 34,
  cost: 33,
  proximity: 33,
}

const ALL_DELTA_FOCUS_ID = '__all_delta__'

const focusModeOptions = [
  { value: 'delta_weighted_participants', label: 'Delta ağırlıklı tüm kişiler' },
  { value: 'single_user', label: 'Tek kişiye yakın olsun' },
  { value: 'custom_location', label: 'Özel odak noktası' },
  { value: 'custom_location_and_delta', label: 'Odak noktası + delta' },
  { value: 'none', label: 'Yakınlık kullanma' },
]

function makeParticipantRows(count, current = []) {
  return Array.from({ length: count }, (_, index) => {
    const existing = current[index]
    return {
      label: existing?.label || `Katılımcı ${index + 1}`,
      value: existing?.value || '',
      delta_weight: existing?.delta_weight ?? 1,
    }
  })
}

function pct(value) {
  if (value === null || value === undefined) return '-'
  return `${value > 0 ? '+' : ''}${Number(value).toFixed(1)}%`
}

function formatWeight(value) {
  return `${Math.round((value || 0) * 100)}%`
}

function profileLabel(profileId) {
  if (profileId === 'custom') return 'Özel seçim'
  return criteriaProfiles.find((profile) => profile.id === profileId)?.label || profileId
}

function preferenceSourceLabel(source) {
  if (!source) return 'Profil hazır'
  if (source === 'lambda') return 'Doğrudan λ seçimi'
  if (source === 'advanced_lambda_weights') return 'Gelişmiş λ ağırlıkları'
  if (source.startsWith('profile:')) {
    const [, rest] = source.split(':')
    const [profileId] = rest.split('+')
    return `${profileLabel(profileId)} profili`
  }
  return source
}

function decisionModeLabel(mode) {
  if (mode === 'criteria_delta') return 'Kriter bazlı seçim'
  if (mode === 'advanced_priority') return 'Gelişmiş kullanıcı önceliği'
  if (mode === 'report_lambda') return 'Rapor modu'
  return mode || '-'
}

function costSourceLabel(source) {
  const labels = {
    manual: 'Manuel maliyet',
    google_price_level: 'Google fiyat seviyesi',
    unknown: 'Bilinmiyor; nötr kabul edildi',
    none: 'Maliyet kullanılmadı',
  }
  return labels[source] || source || 'Maliyet kullanılmadı'
}

function focusSourceLabel(source) {
  const labels = {
    none: 'Odak yakınlığı kullanılmadı',
    focus_location: 'Özel odak noktası',
    delta_weighted_participants: 'Delta ağırlıklı tüm kişiler',
    participant_delta: 'Kişi yakınlık ağırlıkları',
    focus_user: 'Seçili kişi',
    'focus_location+delta_weighted_participants': 'Özel odak noktası + delta ağırlıklı tüm kişiler',
    'focus_location+focus_user': 'Özel odak noktası + seçili kişi',
  }
  return labels[source] || source || 'Odak yakınlığı kullanılmadı'
}

function focusModeLabel(mode) {
  if (mode === 'participant_delta') return 'Kişi yakınlık ağırlıkları'
  return focusModeOptions.find((item) => item.value === mode)?.label || focusSourceLabel(mode)
}

function normalizeWeights(weights) {
  const total = Object.values(weights).reduce((sum, value) => sum + Number(value || 0), 0)
  if (total <= 0) {
    return Object.fromEntries(Object.keys(weights).map((key) => [key, 0]))
  }
  return Object.fromEntries(Object.entries(weights).map(([key, value]) => [key, Number(value || 0) / total]))
}

function focusModeDescription(mode, focusUserId, users) {
  if (mode === 'single_user') {
    const user = users.find((item) => item.id === focusUserId)
    return `${user?.label || 'Seçili kişi'} için yakın adaylar daha yüksek odak skoru alır.`
  }
  if (mode === 'custom_location') return 'Adaylar yalnızca girilen odak noktasına yakınlığa göre puanlanır.'
  if (mode === 'custom_location_and_delta') return 'Odak noktası ve katılımcıların delta ağırlıklı yakınlığı birlikte değerlendirilir.'
  if (mode === 'none') return 'Odak yakınlığı skora katılmaz; odak bileşeni nötr kalır.'
  return 'Aday uzaklığı tüm katılımcılar için delta katsayılarıyla ağırlıklı ortalama alınarak hesaplanır.'
}

function cleanNumberMap(values) {
  return Object.fromEntries(
    Object.entries(values)
      .filter(([, value]) => value !== '' && value !== null && value !== undefined)
      .map(([key, value]) => [key, Number(value)]),
  )
}

function StatusBadge({ health }) {
  const label = health?.google_configured
    ? health?.google_usage?.calls_enabled === false ? 'Google Maps: çağrılar kapalı' : 'Google Maps yapılandırıldı'
    : health?.osrm_base_url ? 'OSRM + sentetik' : 'Sentetik'
  return <span className="status">{label}</span>
}

function WeightBars({ weights }) {
  if (!weights) return null
  return (
    <div className="weight-bars">
      <span style={{ '--w': `${weights.fairness * 100}%` }}>Adalet {formatWeight(weights.fairness)}</span>
      <span style={{ '--w': `${weights.efficiency * 100}%` }}>Verim {formatWeight(weights.efficiency)}</span>
      <span style={{ '--w': `${weights.quality * 100}%` }}>Kalite {formatWeight(weights.quality)}</span>
    </div>
  )
}

function CriterionBars({ weights }) {
  if (!weights) return null
  return (
    <div className="weight-bars">
      <span style={{ '--w': `${weights.rating * 100}%` }}>Puan {formatWeight(weights.rating)}</span>
      <span style={{ '--w': `${weights.cost * 100}%` }}>Fiyat {formatWeight(weights.cost)}</span>
      <span style={{ '--w': `${weights.proximity * 100}%` }}>Yakınlık {formatWeight(weights.proximity)}</span>
    </div>
  )
}

function ScoreBar({ label, value }) {
  return (
    <div className="score-bar">
      <div>
        <span>{label}</span>
        <strong>{Number(value || 0).toFixed(2)}</strong>
      </div>
      <div className="score-track">
        <i style={{ width: `${Math.max(0, Math.min(1, value || 0)) * 100}%` }} />
      </div>
    </div>
  )
}

function ProgressRail({ busy, counts, response }) {
  const activeIndex = pipelineSteps.findIndex((step) => step.id === busy)
  const completed = {
    scenario: Boolean(response) || counts.candidates > 0 || counts.routes > 0,
    candidates: counts.candidates > 0,
    routes: counts.routes > 0,
    recommend: Boolean(response),
  }

  return (
    <div className="progress-rail" aria-label="Akış durumu">
      {pipelineSteps.map((step, index) => {
        const active = busy === step.id
        const done = completed[step.id] || (activeIndex > index && activeIndex !== -1)
        return (
          <span key={step.id} className={`${active ? 'active' : ''} ${done ? 'done' : ''}`}>
            {active ? <Loader2 size={14} className="spin" /> : done ? <CheckCircle2 size={14} /> : <span className="step-dot" />}
            {step.label}
          </span>
        )
      })}
    </div>
  )
}

function LocationPanel({
  inputMode,
  setInputMode,
  participantLocations,
  updateParticipant,
  balanceParticipants,
  parsedLocations,
  onParse,
  busy,
}) {
  return (
    <section className="location-panel">
      <div className="input-mode-control" role="group" aria-label="Konum girişi">
        <button className={inputMode === 'synthetic' ? 'active' : ''} onClick={() => setInputMode('synthetic')}>
          <MapPin size={16} />
          Sentetik konum
        </button>
        <button className={inputMode === 'link' ? 'active' : ''} onClick={() => setInputMode('link')}>
          <LinkIcon size={16} />
          Link ile kişi konumu
        </button>
      </div>
      <div className="participant-panel">
          <div className="panel-head">
            <div>
              <strong>{inputMode === 'link' ? 'Kişi konumları' : 'Kişi yakınlıkları'}</strong>
              {inputMode === 'link' && <span>Google Maps bağlantısı veya koordinat</span>}
            </div>
            <div className="panel-actions">
              <button className="secondary" onClick={balanceParticipants} disabled={Boolean(busy)}>
                <Users size={16} />
                Kişiler dengeli
              </button>
              {inputMode === 'link' && <button className="secondary" onClick={onParse} disabled={Boolean(busy)}>
                {busy === 'parse' ? <Loader2 size={16} className="spin" /> : <CheckCircle2 size={16} />}
                Konumları doğrula
              </button>}
            </div>
          </div>
          {inputMode === 'link' && <p className="privacy-note">Bu konumlar oturumluk tutulur; ham bağlantılar kalıcı veritabanına yazılmaz.</p>}
          <div className={`participant-list ${inputMode === 'synthetic' ? 'synthetic' : ''}`}>
            {participantLocations.map((participant, index) => {
              const parsed = parsedLocations[index]
              return (
                <div className={`participant-row ${inputMode === 'synthetic' ? 'synthetic' : ''}`} key={index}>
                  {inputMode === 'link' ? <label>
                    Kişi
                    <input value={participant.label} onChange={(event) => updateParticipant(index, 'label', event.target.value)} />
                  </label> : <strong className="participant-name">{participant.label}</strong>}
                  {inputMode === 'link' && <label className="location-input">
                    Link veya koordinat
                    <input
                      placeholder="https://maps.google.com/... veya 39.92,32.85"
                      value={participant.value}
                      onChange={(event) => updateParticipant(index, 'value', event.target.value)}
                    />
                  </label>}
                  <label className={inputMode === 'synthetic' ? 'synthetic-weight' : ''}>
                    {inputMode === 'link' && 'Yakınlık ağırlığı'}
                    <input
                      type="number"
                      min="0.5"
                      max="2"
                      step="0.1"
                      value={participant.delta_weight}
                      aria-label={`${participant.label} yakınlık ağırlığı`}
                      onChange={(event) => updateParticipant(index, 'delta_weight', Number(event.target.value))}
                    />
                  </label>
                  {inputMode === 'link' && <div className={`parse-status ${parsed?.error ? 'fail' : parsed?.lat ? 'pass' : ''}`}>
                    {parsed?.error ? parsed.error : parsed?.lat ? `${parsed.lat}, ${parsed.lng}` : 'Bekliyor'}
                  </div>}
                </div>
              )
            })}
          </div>
      </div>
    </section>
  )
}

function PreferenceAssistant({
  health,
  checkingConnection,
  onCheckConnection,
  text,
  setText,
  suggestion,
  onChangeSuggestion,
  participants,
  onInterpret,
  onApply,
  onApplyAndFind,
  canFind,
  reusesRoutes,
  googleConfigured,
  onDiscard,
  busy,
}) {
  const available = health?.ai_ready === true || health?.ai_status === 'configured'
  const modelName = {
    'qwen2.5:3b': 'Qwen 2.5 3B',
    'llama3:8b': 'Llama 3 8B',
  }[health?.ai_model] || health?.ai_model
  const connectionStatus = {
    ready: 'Hazır',
    configured: 'Anahtar tanımlı; bağlantı henüz doğrulanmadı',
    model_missing: 'Seçilen model Ollama’da bulunamadı',
    unreachable: 'Ollama bağlantısı kurulamadı',
    timeout: 'Bağlantı zaman aşımına uğradı',
    unconfigured: 'Model bağlantısı yapılandırılmamış',
    disabled: 'Yapay zekâ kapalı',
    backend_unreachable: 'Uygulama servisine ulaşılamadı',
  }[health?.ai_status] || 'Bağlantı kontrol ediliyor'
  const normalized = suggestion ? normalizeWeights(suggestion.criterion_weights) : null
  const criteriaTotal = suggestion ? Object.values(suggestion.criterion_weights).reduce((sum, value) => sum + Number(value || 0), 0) : 0
  const criteriaValid = suggestion && Object.values(suggestion.criterion_weights).every((value) => Number.isFinite(Number(value)) && value >= 0 && value <= 100)
  const personWeightsValid = suggestion && participants.every((participant) => {
    const weight = Number(suggestion.participant_proximity_weights[participant.id])
    return Number.isFinite(weight) && weight >= 0.5 && weight <= 2
  })
  const constraintsValid = suggestion && (
    (suggestion.min_rating === null || (suggestion.min_rating >= 0 && suggestion.min_rating <= 5)) &&
    (suggestion.max_duration_minutes === null || suggestion.max_duration_minutes >= 1)
  )
  const validSuggestion = criteriaTotal > 0 && criteriaValid && personWeightsValid && constraintsValid
  const updateCriterion = (key, value) => onChangeSuggestion((current) => ({
    ...current,
    criterion_weights: { ...current.criterion_weights, [key]: Number(value) },
  }))
  const updatePerson = (id, value) => onChangeSuggestion((current) => ({
    ...current,
    participant_proximity_weights: { ...current.participant_proximity_weights, [id]: Number(value) },
  }))
  return (
    <section className="assistant-panel">
      <div className="assistant-heading">
        <Sparkles size={19} />
        <div>
          <h2>Tercihini anlat</h2>
          <span role="status">{modelName && `${health.ai_provider === 'ollama' ? 'Yerel model' : 'Bulut modeli'}: ${modelName} · `}{connectionStatus}</span>
        </div>
        <button className="icon-button assistant-connection" title="Model bağlantısını yenile" aria-label="Model bağlantısını yenile" onClick={onCheckConnection} disabled={checkingConnection || Boolean(busy)}>
          {checkingConnection ? <Loader2 size={17} className="spin" /> : <RefreshCcw size={17} />}
        </button>
      </div>
      <div className="assistant-entry">
        <label>
          Seçim isteği
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Fiyat önemli olsun; Kişi 1'e iki kat yakın olsun, puanı en az 4 olsun."
            maxLength={500}
            disabled={!available || Boolean(busy)}
          />
        </label>
        <button className="secondary" onClick={onInterpret} disabled={!available || Boolean(busy) || text.trim().length < 5}>
          {busy === 'interpret' ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
          {busy === 'interpret' ? 'Yorumlanıyor' : 'Tercihi yorumla'}
        </button>
      </div>
      {suggestion && (
        <div className="assistant-review" aria-live="polite">
          <div className="review-title">
            <strong>Önerilen değerler</strong>
            <span>{suggestion.source === 'ollama' ? 'Yerel model' : 'Bulut modeli'}: {suggestion.model}</span>
            <span>{suggestion.explanation}</span>
          </div>
          <div className="review-fields">
            {[
              ['rating', 'Mekân puanı'],
              ['cost', 'Fiyat uygunluğu'],
              ['proximity', 'Kişilere yakınlık'],
            ].map(([key, label]) => (
              <label key={key}>
                {label} <span className="weight-hint">{formatWeight(normalized[key])}</span>
                <input type="number" min="0" max="100" step="1" value={suggestion.criterion_weights[key]} onChange={(event) => updateCriterion(key, event.target.value)} />
              </label>
            ))}
            {participants.map((participant) => (
              <label key={participant.id}>
                {participant.label} yakınlığı
                <input type="number" min="0.5" max="2" step="0.1" value={suggestion.participant_proximity_weights[participant.id]} onChange={(event) => updatePerson(participant.id, event.target.value)} />
              </label>
            ))}
            <label>
              En az puan
              <input type="number" min="0" max="5" step="0.1" placeholder="Yok" value={suggestion.min_rating ?? ''} onChange={(event) => onChangeSuggestion((current) => ({ ...current, min_rating: event.target.value === '' ? null : Number(event.target.value) }))} />
            </label>
            <label>
              En fazla süre (dk)
              <input type="number" min="1" step="1" placeholder="Yok" value={suggestion.max_duration_minutes ?? ''} onChange={(event) => onChangeSuggestion((current) => ({ ...current, max_duration_minutes: event.target.value === '' ? null : Number(event.target.value) }))} />
            </label>
          </div>
          {criteriaTotal <= 0 && <p className="review-warning">En az bir kriter ağırlığı sıfırdan büyük olmalıdır.</p>}
          {suggestion.warnings.map((warning, index) => <p className="review-warning" key={index}>{warning}</p>)}
          <div className="review-actions">
            <button className="primary" onClick={onApplyAndFind} disabled={Boolean(busy) || !validSuggestion || !canFind}><Play size={16} /> Uygula ve mekânları bul</button>
            <button className="secondary" onClick={onApply} disabled={Boolean(busy) || !validSuggestion}><CheckCircle2 size={16} /> Değerleri uygula</button>
            <button className="secondary" onClick={onDiscard} disabled={Boolean(busy)}>Vazgeç</button>
          </div>
          <p className="privacy-note">Konumlar modele gönderilmez. {reusesRoutes ? 'Mevcut rotalar kullanılır; yeni Google isteği gönderilmez.' : googleConfigured ? 'Yeni mekân ve rota araması Google API kullanım ücreti doğurabilir.' : 'Google bağlantısı doğrulanmadan gerçek Google sonucu gösterilmez.'}</p>
        </div>
      )}
    </section>
  )
}

function AdvancedPriorityPanel({
  advancedPriority,
  setAdvancedPriority,
  priorityWeights,
  updatePriorityWeight,
  useAdjustedDurations,
  setUseAdjustedDurations,
  focusLocationInput,
  setFocusLocationInput,
  parsedFocusLocation,
  focusUserId,
  setFocusUserId,
  focusMode,
  setFocusMode,
  users,
}) {
  const normalized = normalizeWeights(priorityWeights)
  const needsFocusLocation = focusMode === 'custom_location' || focusMode === 'custom_location_and_delta'
  const needsFocusUser = focusMode === 'single_user'
  const focusWeightActive = Number(priorityWeights.focus || 0) > 0
  const showNeutralFocusWarning = focusWeightActive && focusMode === 'none'
  const showMissingLocationWarning = focusWeightActive && needsFocusLocation && !focusLocationInput.trim()

  return (
    <section className={`advanced-priority ${advancedPriority ? 'active' : ''}`}>
      <label className="toggle-line">
        <input type="checkbox" checked={advancedPriority} onChange={(event) => setAdvancedPriority(event.target.checked)} />
        Gelişmiş öncelik katmanı
      </label>
      {advancedPriority && (
        <>
          <div className="advanced-note">
            <strong>Delta etkisi ayrımı</strong>
            <span>Süre deltası rota metriklerini etkiler. Yakınlık deltası ise odak yakınlığı skorunda kişilerin önemini belirler.</span>
          </div>
          <div className="advanced-grid">
            {[
              ['report', 'Rapor skoru'],
              ['quality', 'Mekân puanı'],
              ['cost', 'Fiyat uygunluğu'],
              ['focus', 'Odak yakınlığı'],
            ].map(([key, label]) => (
              <label key={key}>
                {label}: {priorityWeights[key]} <span className="weight-hint">etkin {formatWeight(normalized[key])}</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={priorityWeights[key]}
                  onChange={(event) => updatePriorityWeight(key, Number(event.target.value))}
                />
              </label>
            ))}
            <label className="toggle-line compact">
              <input type="checkbox" checked={useAdjustedDurations} onChange={(event) => setUseAdjustedDurations(event.target.checked)} />
              Kişisel delta süreleri rota metriklerine etki etsin
            </label>
            <label>
              Yakınlık hesabı
              <select value={focusMode} onChange={(event) => setFocusMode(event.target.value)}>
                {focusModeOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            {needsFocusUser && (
              <label>
                Odak kişi
                <select value={focusUserId} onChange={(event) => setFocusUserId(event.target.value)}>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>{user.label}</option>
                  ))}
                </select>
              </label>
            )}
            {needsFocusLocation && (
              <label>
                Odak noktası
                <input
                  placeholder="Google Maps linki veya lat,lng"
                  value={focusLocationInput}
                  onChange={(event) => setFocusLocationInput(event.target.value)}
                />
                <span className={parsedFocusLocation?.error ? 'inline-status fail' : 'inline-status'}>
                  {parsedFocusLocation?.error || (parsedFocusLocation?.lat ? `${parsedFocusLocation.lat}, ${parsedFocusLocation.lng}` : 'Gerekli')}
                </span>
              </label>
            )}
          </div>
          <div className={`focus-help ${showNeutralFocusWarning || showMissingLocationWarning ? 'warn' : ''}`}>
            {focusModeDescription(focusMode, focusUserId, users)}
            {showNeutralFocusWarning && ' Odak ağırlığı verilmiş olsa da yakınlık kapalı olduğu için bu bileşen nötr kalır.'}
            {showMissingLocationWarning && ' Odak noktası girilmeden bu mod çalıştırılamaz.'}
          </div>
        </>
      )}
    </section>
  )
}

function SelectionCriteriaPanel({
  criteriaProfile,
  chooseCriteriaProfile,
  criterionWeights,
  updateCriterionWeight,
  disabled,
}) {
  const normalized = normalizeWeights(criterionWeights)
  return (
    <section className="criteria-band">
      <div className="section-label">
        <SlidersHorizontal size={18} />
        <div>
          <strong>Seçim kriterleri</strong>
          <span>Puan, fiyat ve kişilere yakınlık ayrı ağırlıklarla hesaplanır.</span>
        </div>
      </div>
      <div className="profile-control" role="group" aria-label="Seçim kriteri profili">
        {criteriaProfiles.map((profile) => (
          <button
            key={profile.id}
            className={criteriaProfile === profile.id ? 'active' : ''}
            onClick={() => chooseCriteriaProfile(profile.id)}
            disabled={disabled}
          >
            <strong>{profile.label}</strong>
            <span>{profile.helper}</span>
          </button>
        ))}
      </div>
      <div className="criteria-sliders">
        {[
          ['rating', 'Mekân puanı'],
          ['cost', 'Fiyat uygunluğu'],
          ['proximity', 'Kişilere yakınlık'],
        ].map(([key, label]) => (
          <label key={key}>
            {label}: {criterionWeights[key]} <span className="weight-hint">etkin {formatWeight(normalized[key])}</span>
            <input
              type="range"
              min="0"
              max="100"
              value={criterionWeights[key]}
              onChange={(event) => updateCriterionWeight(key, Number(event.target.value))}
            />
          </label>
        ))}
      </div>
    </section>
  )
}

function RecommendationCard({ item, selected, onSelect, manualCost, onManualCostChange }) {
  const breakdown = item.score_breakdown
  const costLabel = item.candidate.manual_cost ?? item.candidate.price_level ?? 'Nötr'
  const costSource = costSourceLabel(item.cost_source)
  const cardLabel = [
    `#${item.rank} ${item.candidate.name}`,
    `${item.candidate.rating.toFixed(1)} puan`,
    `ortalama ${item.t_avg_minutes.toFixed(1)} dakika`,
    `maksimum ${item.t_max_minutes.toFixed(1)} dakika`,
    `skor ${item.score.toFixed(3)}`,
  ].join(', ')

  return (
    <article className={`recommendation-card ${selected ? 'selected' : ''}`}>
      <button
        className="card-main"
        onClick={() => onSelect(item)}
        aria-label={cardLabel}
        aria-pressed={selected}
      >
        <div className="card-rank">#{item.rank}</div>
        <div className="card-copy">
          <div className="place-line">
            <h3>{item.candidate.name}</h3>
            <span>{item.candidate.rating.toFixed(1)} puan</span>
          </div>
          <p>{item.candidate.address}</p>
          <div className="metric-row">
            <span title={costSource}><DollarSign size={15} /> Fiyat {costLabel}</span>
            <span><Star size={15} /> Puan {breakdown.rating_norm.toFixed(2)}</span>
            <span><Users size={15} /> Yakınlık {breakdown.proximity_norm.toFixed(2)}</span>
            <span><Clock3 size={15} /> Ort. {item.t_avg_minutes.toFixed(1)} dk</span>
          </div>
        </div>
        <div className="score-pill">{item.score.toFixed(3)}</div>
      </button>
      <div className="card-footer">
        <div className="mini-breakdown">
          <span>Puan etkisi {breakdown.rating_component.toFixed(2)}</span>
          <span>Fiyat etkisi {breakdown.cost_component.toFixed(2)}</span>
          <span>Yakınlık etkisi {breakdown.proximity_component.toFixed(2)}</span>
        </div>
        <label className="manual-cost" onClick={(event) => event.stopPropagation()}>
          Maliyet gir
          <input
            type="number"
            min="0"
            step="0.5"
            placeholder="Ops."
            value={manualCost ?? ''}
            onChange={(event) => onManualCostChange(item.candidate.id, event.target.value)}
          />
        </label>
        <a href={item.directions_url} target="_blank" rel="noreferrer">
          <ExternalLink size={16} />
          Yol tarifi
        </a>
      </div>
      <GoogleAttribution candidate={item.candidate} />
    </article>
  )
}

function GoogleAttribution({ candidate }) {
  if (candidate.provider !== 'google') return null
  return (
    <div className="google-attribution">
      <span translate="no">Google Maps</span>
      {(candidate.attributions || []).map((attribution, index) => (
        /^https:\/\//.test(attribution.providerUri || '')
          ? <a key={index} href={attribution.providerUri} target="_blank" rel="noreferrer">{attribution.provider}</a>
          : <span key={index}>{attribution.provider}</span>
      ))}
    </div>
  )
}

function DetailPanel({ selected, response }) {
  if (!selected) {
    return (
      <aside className="detail-panel empty-detail">
        <Info size={22} />
        <strong>Bir öneri seç</strong>
        <span>Skor kırılımı ve kişi bazlı süreler burada görünür.</span>
      </aside>
    )
  }

  const breakdown = selected.score_breakdown
  const criteriaMode = selected.decision_mode === 'criteria_delta'
  const costSource = costSourceLabel(selected.cost_source)
  const focusSource = focusSourceLabel(selected.focus_source)
  const costWeightUsed = criteriaMode
    ? Number(selected.criterion_weights?.cost || 0) > 0
    : Number(selected.priority_weights?.cost || 0) > 0
  return (
    <aside className="detail-panel">
      <div className="detail-head">
        <span>{decisionModeLabel(selected.decision_mode)}</span>
        <h2>{selected.candidate.name}</h2>
        <p>{selected.explanation}</p>
        <p>{selected.directions_note}</p>
      </div>

      {criteriaMode ? (
        <CriterionBars weights={selected.criterion_weights || response?.criterion_weights} />
      ) : (
        <WeightBars weights={selected.effective_weights || response?.effective_weights} />
      )}

      <section className="detail-section">
        <h3>Neden bu mekân?</h3>
        <ScoreBar label="Puan etkisi" value={criteriaMode ? breakdown.rating_component : breakdown.quality_norm} />
        <ScoreBar label="Fiyat uygunluğu" value={breakdown.cost_norm} />
        <ScoreBar label="Kişilere yakınlık" value={criteriaMode ? breakdown.proximity_norm : breakdown.focus_norm} />
        {!criteriaMode && <ScoreBar label="Rapor skoru" value={breakdown.report_score} />}
      </section>

      <section className="detail-section">
        <h3>Skor kırılımı</h3>
        <div className="quality-grid">
          <span>Karar modu <strong>{decisionModeLabel(selected.decision_mode)}</strong></span>
          <span>Fiyat kaynağı <strong>{costSource}</strong></span>
          <span>Yakınlık kaynağı <strong>{focusSource}</strong></span>
          <span>Yakınlık modu <strong>{focusModeLabel(selected.focus_mode)}</strong></span>
        </div>
        {costWeightUsed && costSource.includes('nötr') && <p className="source-note">Fiyat verisi bulunmadığı için maliyet bileşeni bu adayda 0.50 kabul edildi.</p>}
      </section>

      {criteriaMode && (
        <section className="detail-section">
          <h3>Kişi yakınlık katkısı</h3>
          <div className="person-list">
            {breakdown.proximity_contributions.map((person) => (
              <div key={person.user_id}>
                <span>{person.label}</span>
                <strong>{formatWeight(person.weight)} / {person.distance_km.toFixed(1)} km</strong>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="detail-section">
        <h3>Kişi bazlı süreler</h3>
        <div className="person-list">
          {selected.per_user.map((user) => (
            <div key={user.user_id}>
              <span>{user.label}</span>
              <strong>
                {user.raw_duration_minutes.toFixed(1)} dk
                {user.delta_weight !== 1 ? ` -> ${user.adjusted_duration_minutes.toFixed(1)} dk (delta ${user.delta_weight.toFixed(1)})` : ''}
              </strong>
            </div>
          ))}
        </div>
      </section>
    </aside>
  )
}

function ExperimentPanel({ experiment }) {
  if (!experiment) {
    return <div className="tab-empty">Karşılaştırma çalıştırıldığında temel yöntem sonuçları burada görünür.</div>
  }

  const targetByMethod = Object.fromEntries((experiment.target_checks || []).map((row) => [row.baseline_method, row]))
  return (
    <div className="comparison-view">
      <div className="comparison-summary">
        <strong>{experiment.selected_model_candidate}</strong>
        <span>{experiment.summary}</span>
        <WeightBars weights={experiment.effective_weights} />
      </div>
      <div className="baseline-table">
        {experiment.baselines.map((row) => {
          const targets = targetByMethod[row.method]
          return (
            <div className="baseline-card" key={row.method}>
              <div className="baseline-head">
                <strong>{row.method}</strong>
                {' '}
                <span>{row.candidate_name}{row.repeat_count ? ` (${row.repeat_count} tekrar)` : ''}</span>
              </div>
              <div className="baseline-metrics">
                <span>Ort. {row.t_avg_minutes.toFixed(1)} dk</span>
                <span>Toplam {row.t_sum_minutes.toFixed(1)} dk</span>
                <span>Maks. {row.t_max_minutes.toFixed(1)} dk</span>
                <span>Var. {row.variance_minutes.toFixed(1)}</span>
              </div>
              <div className="delta-row">
                <span className={row.delta_t_max_pct && row.delta_t_max_pct < 0 ? 'good' : 'warn'}>maks. {pct(row.delta_t_max_pct)}</span>
                <span>ort. {pct(row.delta_t_avg_pct)}</span>
                <span>var. {pct(row.delta_variance_pct)}</span>
              </div>
              {targets && (
                <div className="target-row">
                  <span className={targets.max_duration_target_met ? 'pass' : 'fail'}>maks. hedefi</span>
                  <span className={targets.average_duration_target_met ? 'pass' : 'fail'}>ort. hedefi</span>
                  <span className={targets.variance_target_met ? 'pass' : 'fail'}>varyans hedefi</span>
                </div>
              )}
            </div>
          )
        })}
      </div>
      <div className="stats-grid">
        {experiment.statistics.map((stat) => (
          <div className="stat-card" key={stat.baseline_method}>
            <strong>{stat.baseline_method}</strong>
            <span>{stat.interpretation}</span>
            <div className="stat-metrics">
              <span>W: {stat.wilcoxon_w ?? '-'}</span>
              <span>p: {stat.approximate_p_value ?? '-'}</span>
              <span>d: {stat.effect_size_dz ?? '-'}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ModelDetail({ response }) {
  return (
    <div className="model-view">
      <section>
        <h3>Karar sırası</h3>
        <ol>
          <li>Şehir, mekân türü, kişi sayısı ve Top-K ile aday havuzu hazırlanır.</li>
          <li>Mekân puanı, fiyat uygunluğu ve kişilere yakınlık ayrı ayrı normalize edilir.</li>
          <li>Kişi yakınlığı, her kişinin yakınlık deltasıyla kendi içinde ağırlıklandırılır.</li>
          <li>Rapor uyumlu λ modeli karşılaştırma ve model detayı katmanında korunur.</li>
        </ol>
      </section>
      <section>
        <h3>Seçim ağırlıkları</h3>
        <CriterionBars weights={response?.criterion_weights} />
        <p>Kaynak: {response ? decisionModeLabel(response.decision_mode) : 'Profil henüz çalışmadı'}</p>
        <p>Karar modu: {decisionModeLabel(response?.decision_mode)}</p>
        <p>Rapor λ değeri: {response?.lambda_value ?? '-'}</p>
      </section>
      <section>
        <h3>Formül</h3>
        <code>final_score = w_rating * rating_norm + w_cost * cost_norm + w_proximity * proximity_norm; proximity_norm = sum(person_weight_i * closeness_norm_i)</code>
      </section>
    </div>
  )
}

function ReportDraft() {
  return (
    <div className="report-view">
      {reportDraft.map((paragraph, index) => (
        <p key={index}>{paragraph}</p>
      ))}
    </div>
  )
}

export default function App() {
  const [theme, setTheme] = useState(() => {
    try {
      const saved = window.localStorage.getItem('ortak-theme')
      if (saved === 'light' || saved === 'dark') return saved
    } catch {
      // Browser storage may be unavailable.
    }
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })
  const [health, setHealth] = useState(null)
  const [runtimeConfig, setRuntimeConfig] = useState(null)
  const [checkingAi, setCheckingAi] = useState(false)
  const intentVersion = useRef(0)
  const pipelineInFlight = useRef(false)
  const [scenarioForm, setScenarioForm] = useState(initialScenario)
  const [scenario, setScenario] = useState(null)
  const [scenarioContext, setScenarioContext] = useState(null)
  const [inputMode, setInputMode] = useState('synthetic')
  const [participantLocations, setParticipantLocations] = useState(() => makeParticipantRows(initialScenario.group_size))
  const [parsedLocations, setParsedLocations] = useState([])
  const parsedLocationValues = useRef('')
  const [routeRecovery, setRouteRecovery] = useState(null)
  const [criteriaProfile, setCriteriaProfile] = useState('balanced')
  const [criterionWeights, setCriterionWeights] = useState(initialCriterionWeights)
  const [intentText, setIntentText] = useState('')
  const [intentSuggestion, setIntentSuggestion] = useState(null)
  const [aiApplied, setAiApplied] = useState(false)
  const [priorityProfile, setPriorityProfile] = useState('balanced')
  const [lambdaValue, setLambdaValue] = useState(0.5)
  const [customLambda, setCustomLambda] = useState(false)
  const [advancedPriority, setAdvancedPriority] = useState(false)
  const [priorityWeights, setPriorityWeights] = useState(initialPriorityWeights)
  const [useAdjustedDurations, setUseAdjustedDurations] = useState(false)
  const [focusLocationInput, setFocusLocationInput] = useState('')
  const [parsedFocusLocation, setParsedFocusLocation] = useState(null)
  const [focusUserId, setFocusUserId] = useState(ALL_DELTA_FOCUS_ID)
  const [focusMode, setFocusMode] = useState('delta_weighted_participants')
  const [manualCosts, setManualCosts] = useState({})
  const [k, setK] = useState(3)
  const [maxDuration, setMaxDuration] = useState('')
  const [minRating, setMinRating] = useState('')
  const [response, setResponse] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [experiment, setExperiment] = useState(null)
  const [activeTab, setActiveTab] = useState('recommendations')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [counts, setCounts] = useState({ candidates: 0, routes: 0 })

  const recommendations = response?.recommendations || []
  const selected = recommendations.find((item) => item.candidate.id === selectedId) || recommendations[0]
  const focusUsers = scenario?.users || participantLocations.map((participant, index) => ({ id: `user-${index + 1}`, label: participant.label || `Katılımcı ${index + 1}` }))
  const intentParticipants = participantLocations.map((participant, index) => ({
    id: `user-${index + 1}`,
    label: participant.label || `Katılımcı ${index + 1}`,
    delta_weight: Number(participant.delta_weight),
  }))
  // Preference edits can reuse routes; changed locations or search inputs cannot.
  const searchContext = JSON.stringify({
    scenarioForm,
    inputMode,
    participants: inputMode === 'link' ? participantLocations.map(({ label, value }) => ({ label, value })) : null,
  })
  const currentSearchContext = useRef(searchContext)
  currentSearchContext.current = searchContext
  const canReuseRoutes = Boolean(scenario && response && scenarioContext === searchContext)
  const selectedCapacity = runtimeConfig?.google_search_capacity?.[inputMode === 'link' ? 'resolved_coordinates' : 'synthetic']?.[scenarioForm.group_size]
  const canStartSearch = Boolean(runtimeConfig && (
    (runtimeConfig.google_available && selectedCapacity?.available !== false) || (!runtimeConfig.production && health?.google_configured === false)
  ))
  const canResumeRoutes = Boolean(scenario && routeRecovery?.scenarioId === scenario.id && routeRecovery.context === searchContext)

  useEffect(() => {
    if (scenarioContext !== null && scenarioContext !== searchContext) {
      setResponse(null)
      setSelectedId(null)
      setExperiment(null)
      setCounts({ candidates: 0, routes: 0 })
      setRouteRecovery(null)
    }
  }, [scenarioContext, searchContext])

  useEffect(() => {
    refreshAiStatus()
  }, [])

  const intentContextKey = JSON.stringify({ participantLocations, criterionWeights, minRating, maxDuration, intentText })
  useEffect(() => {
    intentVersion.current += 1
    setIntentSuggestion(null)
  }, [intentContextKey])

  async function refreshAiStatus() {
    setCheckingAi(true)
    try {
      await refreshRuntimeConfig()
      setHealth(await api.health())
    } catch {
      setHealth((current) => ({ ...current, ai_ready: false, ai_status: 'backend_unreachable' }))
    } finally {
      setCheckingAi(false)
    }
  }

  async function refreshRuntimeConfig() {
    const config = await api.runtimeConfig()
    setRuntimeConfig(config)
    return config
  }

  function checkSearchCapacity(config) {
    if (!config.production && health?.google_configured === false) return
    const capacity = config.google_search_capacity?.[inputMode === 'link' ? 'resolved_coordinates' : 'synthetic']?.[scenarioForm.group_size]
    if (!config.google_available || capacity?.available === false) {
      throw new Error(capacity?.reason || config.google_unavailable_reason || 'Bu arama için yeterli Google kapasitesi yok.')
    }
  }

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      window.localStorage.setItem('ortak-theme', theme)
    } catch {
      // Theme still works for the current session.
    }
  }, [theme])

  useEffect(() => {
    setParticipantLocations((current) => makeParticipantRows(scenarioForm.group_size, current))
    setParsedLocations([])
    setIntentSuggestion(null)
  }, [scenarioForm.group_size])

  function updateForm(key, value) {
    setScenarioForm((current) => ({ ...current, [key]: value }))
  }

  function updateParticipant(index, key, value) {
    setParticipantLocations((current) => current.map((item, itemIndex) => (
      itemIndex === index ? { ...item, [key]: value } : item
    )))
    if (key === 'value') setParsedLocations([])
    setIntentSuggestion(null)
    if (key === 'delta_weight') setAiApplied(false)
  }

  function updatePriorityWeight(key, value) {
    setPriorityWeights((current) => ({ ...current, [key]: value }))
  }

  function updateCriterionWeight(key, value) {
    setCriterionWeights((current) => ({ ...current, [key]: value }))
    setCriteriaProfile('custom')
    setIntentSuggestion(null)
    setAiApplied(false)
  }

  function updateManualCost(candidateId, value) {
    setManualCosts((current) => ({ ...current, [candidateId]: value }))
  }

  function balanceParticipants() {
    setParticipantLocations((current) => current.map((item) => ({ ...item, delta_weight: 1 })))
    setIntentSuggestion(null)
    setAiApplied(false)
    if (canReuseRoutes) {
      refreshRecommendations({ participantWeights: Object.fromEntries(scenario.users.map((user) => [user.id, 1])) })
    }
  }

  async function interpretIntent() {
    const version = intentVersion.current
    setError('')
    setIntentSuggestion(null)
    try {
      setBusy('interpret')
      const result = await api.interpretPreferences({
        text: intentText.trim(),
        participants: intentParticipants,
        criterion_weights: criterionWeights,
        min_rating: minRating === '' ? null : Number(minRating),
        max_duration_minutes: maxDuration === '' ? null : Number(maxDuration),
      })
      if (version === intentVersion.current) setIntentSuggestion(result)
    } catch (err) {
      setError(err.message)
      refreshAiStatus()
    } finally {
      setBusy('')
    }
  }

  async function applyIntentSuggestion(findPlaces = false) {
    if (!intentSuggestion) return
    const nextWeights = intentSuggestion.criterion_weights
    const nextPersonWeights = intentSuggestion.participant_proximity_weights
    const nextMinRating = intentSuggestion.min_rating ?? ''
    const nextMaxDuration = intentSuggestion.max_duration_minutes ?? ''
    setCriterionWeights(nextWeights)
    setParticipantLocations((current) => current.map((item, index) => ({
      ...item,
      delta_weight: nextPersonWeights[`user-${index + 1}`],
    })))
    setCriteriaProfile('custom')
    setMinRating(nextMinRating)
    setMaxDuration(nextMaxDuration)
    setAiApplied(true)
    setIntentSuggestion(null)
    const overrides = {
      criterionWeights: nextWeights,
      participantWeights: nextPersonWeights,
      minRating: nextMinRating,
      maxDuration: nextMaxDuration,
    }
    if (canReuseRoutes) {
      await refreshRecommendations(overrides)
    } else if (findPlaces && canStartSearch) {
      await runPipeline(overrides)
    }
  }

  function updateFocusMode(nextMode) {
    setFocusMode(nextMode)
    setParsedFocusLocation(null)
    if (nextMode === 'single_user' && focusUserId === ALL_DELTA_FOCUS_ID && focusUsers[0]) {
      setFocusUserId(focusUsers[0].id)
    }
  }

  async function parseParticipantLocations() {
    if (inputMode !== 'link') return []
    const values = JSON.stringify(participantLocations.map((person) => person.value))
    if (parsedLocationValues.current === values && parsedLocations.length === participantLocations.length && parsedLocations.every((item) => !item.error && Number.isFinite(item.lat) && Number.isFinite(item.lng))) return parsedLocations
    setBusy('parse')
    try {
      const result = await api.parseLocations({ items: participantLocations })
      setParsedLocations(result)
      parsedLocationValues.current = values
      const failed = result.filter((item) => item.error)
      if (failed.length) {
        throw new Error('Bazı kişi konumları çözülemedi. Lütfen satırları kontrol edin.')
      }
      return result
    } finally {
      if (!pipelineInFlight.current) setBusy('')
    }
  }

  async function handleParseLocations() {
    setError('')
    try {
      await parseParticipantLocations()
    } catch (err) {
      setError(err.message)
    }
  }

  async function parseFocusLocation(activeFocusMode = focusMode) {
    const value = focusLocationInput.trim()
    const needsFocusLocation = activeFocusMode === 'custom_location' || activeFocusMode === 'custom_location_and_delta'
    if (!advancedPriority || !needsFocusLocation) {
      setParsedFocusLocation(null)
      return null
    }
    if (!value) {
      throw new Error('Odak yakınlığı için Google Maps linki veya lat,lng koordinatı girilmelidir.')
    }
    const [result] = await api.parseLocations({
      items: [{ label: 'Odak noktası', value, delta_weight: 1 }],
    })
    setParsedFocusLocation(result)
    if (result.error) {
      throw new Error(`Odak noktası çözülemedi: ${result.error}`)
    }
    return { lat: result.lat, lng: result.lng }
  }

  function preferencePayload(overrides = {}) {
    return {
      scoring_mode: 'criteria_delta',
      priority_profile: 'balanced',
      lambda_value: null,
      advanced_preferences_enabled: false,
      fairness_weight: null,
      efficiency_weight: null,
      quality_weight: null,
      criterion_weights: overrides.criterionWeights ?? criterionWeights,
    }
  }

  function participantProximityPayload(activeScenario = scenario, overrides = null) {
    const users = activeScenario?.users || participantLocations.map((participant, index) => ({
      id: `user-${index + 1}`,
      delta_weight: participant.delta_weight,
    }))
    return Object.fromEntries(users.map((user, index) => [
      user.id,
      Number(overrides?.[user.id] ?? participantLocations[index]?.delta_weight ?? user.delta_weight ?? 1),
    ]))
  }

  async function advancedPriorityPayload(activeScenario = scenario, overrides = {}) {
    return {
      advanced_priority_enabled: false,
      priority_weights: initialPriorityWeights,
      criterion_weights: overrides.criterionWeights ?? criterionWeights,
      participant_proximity_weights: participantProximityPayload(activeScenario, overrides.participantWeights),
      manual_candidate_costs: cleanNumberMap(manualCosts),
      focus_location: null,
      focus_user_id: null,
      focus_mode: null,
      use_adjusted_durations: false,
    }
  }

  async function recommendationPayload(scenarioId, overrides = {}, activeScenario = scenario) {
    return {
      scenario_id: scenarioId,
      k,
      max_duration_minutes: (overrides.maxDuration ?? maxDuration) === '' ? null : Number(overrides.maxDuration ?? maxDuration),
      min_rating: (overrides.minRating ?? minRating) === '' ? null : Number(overrides.minRating ?? minRating),
      category: scenarioForm.category,
      ...preferencePayload(overrides),
      ...(await advancedPriorityPayload(activeScenario, overrides)),
    }
  }

  async function buildScenarioPayload(overrides = {}) {
    if (inputMode !== 'link') {
      return {
        ...scenarioForm,
        input_mode: 'synthetic',
        session_only: false,
      }
    }
    const parsed = await parseParticipantLocations()
    return {
      ...scenarioForm,
      group_size: participantLocations.length,
      input_mode: 'link',
      session_only: true,
      participant_locations: participantLocations.map((person, index) => ({
        ...person,
        value: `${parsed[index].lat},${parsed[index].lng}`,
        delta_weight: overrides.participantWeights?.[`user-${index + 1}`] ?? person.delta_weight,
      })),
    }
  }

  async function runPipeline(overrides = {}) {
    if ((!canStartSearch && !canResumeRoutes) || busy || pipelineInFlight.current) return
    pipelineInFlight.current = true
    const ensureUnchangedInputs = () => {
      if (currentSearchContext.current !== searchContext) {
        throw new Error('Konumlar veya arama alanları değişti; işlem durduruldu. Güncel bilgilerle yeniden arayın.')
      }
    }
    setError('')
    setExperiment(null)
    setResponse(null)
    setSelectedId(null)
    if (!canResumeRoutes) setCounts({ candidates: 0, routes: 0 })
    let created = canResumeRoutes ? scenario : null
    let step = canResumeRoutes ? 'routes' : 'scenario'
    try {
      setBusy('scenario')
      const config = await refreshRuntimeConfig()
      if (!canResumeRoutes) {
        checkSearchCapacity(config)
        const payload = await buildScenarioPayload(overrides)
        ensureUnchangedInputs()
        checkSearchCapacity(await refreshRuntimeConfig())
        if (scenario?.session_only) await api.deleteScenario(scenario.id).catch(() => {})
        setRouteRecovery(null)
        setBusy('scenario')
        created = await api.createScenario(payload)
        setScenario(created)
        setScenarioContext(searchContext)
        ensureUnchangedInputs()
        step = 'candidates'
        setBusy('candidates')
        const candidates = await api.searchCandidates({
          scenario_id: created.id,
          max_results: config.max_candidates || 3,
          radius_m: scenarioForm.radius_m,
        })
        setCounts((current) => ({ ...current, candidates: candidates.length }))
        if (!candidates.length) throw new Error('Bu bölgede uygun mekân bulunamadı. Arama bilgilerini değiştirebilirsiniz.')
      }

      ensureUnchangedInputs()
      step = 'routes'
      setBusy('routes')
      const routes = await api.buildRoutes({ scenario_id: created.id, provider: health?.google_configured ? 'google' : 'auto' })
      setCounts((current) => ({ ...current, routes: routes.length }))

      ensureUnchangedInputs()
      setBusy('recommend')
      const result = await api.recommend(await recommendationPayload(created.id, overrides, created))
      ensureUnchangedInputs()
      setResponse(result)
      setSelectedId(result.recommendations[0]?.candidate.id || null)
      setRouteRecovery(null)
    } catch (err) {
      if (step === 'routes' && created && currentSearchContext.current === searchContext) setRouteRecovery({ scenarioId: created.id, context: searchContext })
      setError(err.message)
    } finally {
      await refreshRuntimeConfig().catch(() => {})
      pipelineInFlight.current = false
      setBusy('')
    }
  }

  async function refreshRecommendations(overrides = {}) {
    if (!canReuseRoutes) return
    setError('')
    try {
      setBusy('recommend')
      const result = await api.recommend(await recommendationPayload(scenario.id, overrides))
      if (currentSearchContext.current !== searchContext) {
        throw new Error('Konumlar veya arama alanları değişti; eski rotalarla sonuç gösterilmedi. Güncel bilgilerle yeniden arayın.')
      }
      setResponse(result)
      setSelectedId(result.recommendations[0]?.candidate.id || null)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  async function runExperiment() {
    if (!canReuseRoutes) return
    setError('')
    try {
      setBusy('experiment')
      const result = await api.runExperiment({
        scenario_id: scenario.id,
        k,
        ...preferencePayload(),
        ...(await advancedPriorityPayload(scenario)),
      })
      setExperiment(result)
      setActiveTab('compare')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  function chooseCriteriaProfile(profileId) {
    const profile = criteriaProfiles.find((item) => item.id === profileId)
    if (!profile) return
    setCriteriaProfile(profileId)
    setCriterionWeights(profile.weights)
    setIntentSuggestion(null)
    setAiApplied(false)
    if (canReuseRoutes) refreshRecommendations({ criterionWeights: profile.weights })
  }

  function chooseProfile(profileId) {
    chooseCriteriaProfile(profileId)
  }

  function updateLambda(value) {
    const nextLambda = Number(value)
    setLambdaValue(nextLambda)
    setCustomLambda(true)
  }

  async function deleteCurrentScenario() {
    if (!scenario) return
    setBusy('delete')
    try {
      await api.deleteScenario(scenario.id)
      setScenario(null)
      setScenarioContext(null)
      setRouteRecovery(null)
      setResponse(null)
      setExperiment(null)
      setCounts({ candidates: 0, routes: 0 })
      setParsedLocations([])
      setParticipantLocations(makeParticipantRows(scenarioForm.group_size))
      setIntentText('')
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  return (
    <main className="product-shell">
      <header className="app-header">
        <div className="brand-mark">
          <Route size={26} />
          <div>
            <h1>ORTAK</h1>
            <span>Optimum rota tabanlı adil kesişim</span>
          </div>
        </div>
        <div className="header-actions">
          <StatusBadge health={health} />
          <button
            className="theme-toggle"
            onClick={() => setTheme((current) => current === 'dark' ? 'light' : 'dark')}
            title={theme === 'dark' ? 'Açık temaya geç' : 'Koyu temaya geç'}
            aria-label={theme === 'dark' ? 'Açık temaya geç' : 'Koyu temaya geç'}
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </header>

      <section className="control-band">
        <div className="control-grid simple-control-grid">
          <label>
            Şehir
            <input maxLength={80} value={scenarioForm.city} onChange={(event) => updateForm('city', event.target.value)} />
          </label>
          <label>
            Mekân türü
            <select value={scenarioForm.category} onChange={(event) => updateForm('category', event.target.value)}>
              {categories.map((category) => (
                <option key={category.value} value={category.value}>{category.label}</option>
              ))}
            </select>
          </label>
          <label>
            Grup
            <input type="number" min="2" max={runtimeConfig?.max_participants || 8} value={scenarioForm.group_size} onChange={(event) => updateForm('group_size', Math.min(runtimeConfig?.max_participants || 8, Math.max(2, Number(event.target.value))))} />
          </label>
          <label>
            Top-K
            <input type="number" min="1" max={runtimeConfig?.max_k || 3} value={k} onChange={(event) => setK(Math.min(runtimeConfig?.max_k || 3, Math.max(1, Number(event.target.value))))} />
          </label>
        </div>
        <LocationPanel
          inputMode={inputMode}
          setInputMode={(mode) => { setInputMode(mode); setIntentSuggestion(null) }}
          participantLocations={participantLocations}
          updateParticipant={updateParticipant}
          balanceParticipants={balanceParticipants}
          parsedLocations={parsedLocations}
          onParse={handleParseLocations}
          busy={busy}
        />
        <div className="action-row">
          <button className="primary" onClick={() => runPipeline()} disabled={Boolean(busy) || (!canStartSearch && !canResumeRoutes)}>
            {busy ? <Loader2 size={18} className="spin" /> : <Play size={18} />}
            {busy ? busyLabels[busy] || 'Çalışıyor' : canResumeRoutes ? 'Rotaları tamamla' : 'Öneri üret'}
          </button>
          {scenario?.session_only && <button className="secondary" onClick={deleteCurrentScenario} disabled={Boolean(busy)} title="Senaryoyu ve konumlarını sil"><Trash2 size={18} /> Senaryoyu sil</button>}
        </div>
        {runtimeConfig?.production && <p className="privacy-note">Senaryolar oluşturulduktan en geç iki saat sonra silinir. Konumlar ve ham tercihler kalıcı veritabanına yazılmaz.</p>}
        {runtimeConfig && !canStartSearch && <p className="error" role="status">{selectedCapacity?.reason || runtimeConfig.google_unavailable_reason || 'Google kullanımı şu anda kapalı veya bağlantı doğrulanmadı.'}{canReuseRoutes && ' Mevcut önerilerin tercihlerini güncelleyebilirsiniz.'}</p>}
        <ProgressRail busy={busy} counts={counts} response={response} />
      </section>

      <PreferenceAssistant
        health={health}
        checkingConnection={checkingAi}
        onCheckConnection={refreshAiStatus}
        text={intentText}
        setText={(value) => { setIntentText(value); setIntentSuggestion(null) }}
        suggestion={intentSuggestion}
        onChangeSuggestion={setIntentSuggestion}
        participants={intentParticipants}
        onInterpret={interpretIntent}
        onApply={() => applyIntentSuggestion()}
        onApplyAndFind={() => applyIntentSuggestion(true)}
        canFind={canReuseRoutes || canStartSearch}
        reusesRoutes={canReuseRoutes}
        googleConfigured={health?.google_configured === true}
        onDiscard={() => setIntentSuggestion(null)}
        busy={busy}
      />

      <SelectionCriteriaPanel
        criteriaProfile={criteriaProfile}
        chooseCriteriaProfile={chooseCriteriaProfile}
        criterionWeights={criterionWeights}
        updateCriterionWeight={updateCriterionWeight}
        disabled={Boolean(busy)}
      />

      <div className="result-filters" role="group" aria-label="Sonuç filtreleri">
        <label>
          En az puan
          <input type="number" min="0" max="5" step="0.1" placeholder="Sınır yok" value={minRating} onChange={(event) => setMinRating(event.target.value)} />
        </label>
        <label>
          En fazla süre (dk)
          <input type="number" min="1" step="1" placeholder="Sınır yok" value={maxDuration} onChange={(event) => setMaxDuration(event.target.value)} />
        </label>
      </div>

      {error && <div className="error" role="alert">{error}</div>}

      <section className="summary-strip">
        <div><MapPin size={17} /> {scenario?.city || scenarioForm.city}</div>
        <div><Users size={17} /> {scenario?.group_size || scenarioForm.group_size} katılımcı</div>
        <div><Filter size={17} /> {counts.candidates} aday</div>
        <div><Navigation size={17} /> {counts.routes} rota</div>
        <div><ShieldCheck size={17} /> {aiApplied ? 'Onaylanan tercih' : profileLabel(criteriaProfile)}</div>
        <div><Target size={17} /> Kriter bazlı seçim</div>
        {(scenario?.input_mode || inputMode) === 'link' && <div><ShieldCheck size={17} /> Oturumluk konum</div>}
        <div><CheckCircle2 size={17} /> {response ? decisionModeLabel(response.decision_mode) : 'Profil hazır'}</div>
      </section>

      <section className="result-layout">
        <div className="results-column">
          <div className="result-toolbar">
            <div>
              <h2>Öneriler</h2>
              <span>{response ? `${response.valid_alternatives} geçerli alternatif, ${recommendations.length} öneri` : 'Henüz sonuç yok'}</span>
            </div>
            <button className="secondary" onClick={() => refreshRecommendations()} disabled={!canReuseRoutes || Boolean(busy)}>
              <RefreshCcw size={16} />
              Güncelle
            </button>
          </div>
          <div className="recommendation-list">
            {recommendations.length ? (
              recommendations.map((item) => (
                <RecommendationCard
                  key={item.candidate.id}
                  item={item}
                  selected={selected?.candidate.id === item.candidate.id}
                  onSelect={(next) => setSelectedId(next.candidate.id)}
                  manualCost={manualCosts[item.candidate.id]}
                  onManualCostChange={updateManualCost}
                />
              ))
            ) : (
              <div className="empty-results">
                <Route size={30} />
                <strong>{response ? 'Kısıtlara uygun mekân bulunamadı' : 'Senaryo hazır'}</strong>
                <span>{response ? 'Puan veya süre sınırını değiştirin.' : 'Öneri üretildiğinde mekân kartları burada listelenir.'}</span>
              </div>
            )}
          </div>
        </div>
        <DetailPanel selected={selected} response={response} />
      </section>

      <section className="tabs-section">
        <div className="tabs">
          {[
            ['recommendations', 'Öneri özeti'],
            ['compare', 'Karşılaştır'],
            ['model', 'Model detayı'],
            ['report', 'Rapor taslağı'],
          ].map(([id, label]) => (
            <button key={id} className={activeTab === id ? 'active' : ''} onClick={() => setActiveTab(id)}>{label}</button>
          ))}
          <button className="secondary compare-action" onClick={runExperiment} disabled={!recommendations.length || Boolean(busy)}>
            {busy === 'experiment' ? <Loader2 size={16} className="spin" /> : <BarChart3 size={16} />}
            Deney
          </button>
        </div>
        <div className="tab-body">
          {activeTab === 'recommendations' && (
            <div className="model-view">
              <section>
                <h3>Tercih sonucu</h3>
                <p>{response ? `${profileLabel(criteriaProfile)} kriter profili uygulandı. Karar modu: ${decisionModeLabel(response.decision_mode)}.` : 'Öneri üretildiğinde kriter profili burada görünür.'}</p>
                {(scenario?.input_mode || inputMode) === 'link' && <p className="source-note">Bu senaryo oturumluk tutulur; ham kişi linkleri ve rota metrikleri kalıcı veritabanına yazılmaz.</p>}
                <CriterionBars weights={response?.criterion_weights} />
              </section>
            </div>
          )}
          {activeTab === 'compare' && <ExperimentPanel experiment={experiment} />}
          {activeTab === 'model' && <ModelDetail response={response} />}
          {activeTab === 'report' && <ReportDraft />}
        </div>
      </section>
      <footer className="app-footer">
        <a href="/privacy.html" target="_blank" rel="noreferrer">Gizlilik</a>
        <a href="/terms.html" target="_blank" rel="noreferrer">Kullanım koşulları</a>
        <span translate="no">Built with Meta Llama 3</span>
      </footer>
    </main>
  )
}
