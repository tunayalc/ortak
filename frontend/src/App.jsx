import {
  BarChart3,
  CheckCircle2,
  Clock3,
  DollarSign,
  ExternalLink,
  Filter,
  Info,
  Link as LinkIcon,
  DoorOpen,
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
import MeetingPlanner from './MeetingPlanner'
import PlaceComparison from './PlaceComparison'
import { RoomHost } from './GroupInvite'
import { PlacePicker, WeightSelect } from './LocationTools'
import { ConditionsEditor, ConditionsSummary, emptyConditions, StatusNotice, WorkflowNav } from './ui'
import { checkedConditions, planSearchInput, rebalanceWeights, travelModes } from './planner'
import { categories, MAX_CATEGORIES } from './catalog'

const modeNames = Object.fromEntries(travelModes.map(mode => [mode.value, mode.label]))
const categoryGroups = [...new Set(categories.map(item => item.group))]

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
  categories: ['cafe'],
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
      travel_mode: existing?.travel_mode || '',
      place: existing?.place || '',
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
    synthetic_price_level: 'Sentetik fiyat seviyesi',
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
  travelMode,
  setTravelMode,
  inputMode,
  chooseMode,
  roomMode,
  roomPanel,
  participantLocations,
  updateParticipant,
  groupSize,
  setGroupSize,
  maxParticipants,
  parsedLocations,
  busy,
}) {
  const manual = inputMode === 'link' && !roomMode
  const modes = [
    { id: 'manual', active: manual, icon: LinkIcon, title: 'Konumları ben gireyim', helper: 'Herkesin adını ve yerini siz yazarsınız.' },
    ...(roomPanel !== null ? [{ id: 'room', active: roomMode, icon: DoorOpen, title: 'Oda kur', helper: 'Bağlantıyı paylaşın; herkes kendi adını ve yerini girer.' }] : []),
  ]
  return (
    <div className="location-panel">
      <div className="mode-cards" role="group" aria-label="Konum girişi">
        {modes.map(({ id, active, icon: Icon, title, helper }) => (
          <button key={id} type="button" className={active ? 'active' : ''} aria-pressed={active} aria-label={title} aria-describedby={`mode-${id}`} onClick={() => chooseMode(id)} disabled={Boolean(busy)}>
            <Icon size={20} aria-hidden="true" />
            <strong>{title}</strong>
            <small id={`mode-${id}`}>{helper}</small>
          </button>
        ))}
      </div>
      {roomMode && roomPanel}
      {!roomMode && <>
        <div className="people-toolbar">
          <label className="people-count">
            Kişi sayısı
            <input type="number" min="2" max={maxParticipants} value={groupSize} disabled={Boolean(busy)} onChange={(event) => setGroupSize(Math.min(maxParticipants, Math.max(2, Number(event.target.value))))} />
          </label>
          <label className="transport-select">
            {manual ? 'Varsayılan ulaşım' : 'Ulaşım'}
            <select value={travelMode} onChange={(event) => setTravelMode(event.target.value)} disabled={Boolean(busy)}>
              {travelModes.map((mode) => <option key={mode.value} value={mode.value}>{mode.label}</option>)}
            </select>
          </label>
        </div>
        {inputMode === 'synthetic' && <p className="sample-note">Örnek kişiler şehirde rastgele yerlere yerleştirilir. Gerçek buluşma için yukarıdan bir seçenek seçin.</p>}
        <div className={`participant-list ${manual ? '' : 'synthetic'}`}>
          {participantLocations.map((participant, index) => {
            const parsed = parsedLocations[index]
            return (
              <div className={`participant-row ${manual ? '' : 'synthetic'}`} key={index}>
                <div className="person-head">
                  <span className="person-num" aria-hidden="true">{index + 1}</span>
                  {manual ? <label className="person-name">
                    Ad
                    <input value={participant.label} maxLength={80} onChange={(event) => updateParticipant(index, 'label', event.target.value)} />
                  </label> : <strong className="participant-name">{participant.label}</strong>}
                  {!manual && <WeightSelect name={participant.label} value={participant.delta_weight} disabled={Boolean(busy)} onChange={(value) => updateParticipant(index, 'delta_weight', value)} />}
                </div>
                {manual && <PlacePicker
                  label="Yer adı, link veya koordinat"
                  value={participant.value}
                  place={participant.place}
                  disabled={Boolean(busy)}
                  onChange={(value) => { updateParticipant(index, 'value', value); updateParticipant(index, 'place', '') }}
                  onPick={(item) => { updateParticipant(index, 'value', `${item.lat},${item.lng}`); updateParticipant(index, 'place', item.address ? `${item.name} (${item.address})` : item.name) }}
                />}
                {manual && <div className="person-options">
                  <label className="transport-select">
                    Ulaşım
                    <select value={participant.travel_mode || ''} onChange={(event) => updateParticipant(index, 'travel_mode', event.target.value)} disabled={Boolean(busy)}>
                      <option value="">Varsayılan ({modeNames[travelMode]})</option>
                      {travelModes.map((mode) => <option key={mode.value} value={mode.value}>{mode.label}</option>)}
                    </select>
                  </label>
                  <WeightSelect name={participant.label} value={participant.delta_weight} disabled={Boolean(busy)} onChange={(value) => updateParticipant(index, 'delta_weight', value)} />
                </div>}
                {manual && parsed?.error && <div className="parse-status fail">{parsed.error}</div>}
              </div>
            )
          })}
        </div>
        {manual && <p className="privacy-note">Ağırlığı yüksek kişiye yakın yerler öne çıkar. Konumlar yalnızca bu arama için kullanılır, kalıcı kaydedilmez.</p>}
        <button type="button" className="link-button" onClick={() => chooseMode(inputMode === 'synthetic' ? 'manual' : 'sample')} disabled={Boolean(busy)}>
          {inputMode === 'synthetic' ? 'Kendi konumlarımı gireceğim' : 'Örnek konumlarla dene'}
        </button>
      </>}
    </div>
  )
}

function Step({ number, id, title, hint, children, label }) {
  return (
    <section className="step" id={id} tabIndex={id ? -1 : undefined} aria-label={label}>
      <div className="step-head">
        <span className="step-num" aria-hidden="true">{number}</span>
        <div>
          <h3>{title}</h3>
          {hint && <p>{hint}</p>}
        </div>
      </div>
      {children}
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
  interpreting,
  contextMode,
  setContextMode,
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
  const validSuggestion = criteriaTotal > 0 && criteriaValid && personWeightsValid && constraintsValid && !suggestion?.questions?.length
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
          <h4>Ya da isteğinizi yazın</h4>
          <span role="status">{modelName && `${health.ai_provider === 'ollama' ? 'Yerel model' : 'Bulut modeli'}: ${modelName} - `}{connectionStatus}</span>
        </div>
        <button className="icon-button assistant-connection" title="Model bağlantısını yenile" aria-label="Model bağlantısını yenile" onClick={onCheckConnection} disabled={checkingConnection || Boolean(busy)}>
          {checkingConnection ? <Loader2 size={17} className="spin" /> : <RefreshCcw size={17} />}
        </button>
      </div>
      <div className="assistant-entry">
        <label>Tercih bağlamı<select value={contextMode} onChange={e => setContextMode(e.target.value)}>
          <option value="continue">Mevcut koşulları koru</option><option value="new">Yeni tercih isteği</option></select></label>
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
        <button className="secondary" onClick={onInterpret} disabled={!available || Boolean(busy) || interpreting || text.trim().length < 5}>
          {interpreting ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
          {interpreting ? 'Yorumlanıyor' : 'Tercihi yorumla'}
        </button>
      </div>
      {interpreting && <StatusNotice kind="loading">Tercih yorumlanıyor; mevcut ayarlar korunuyor.</StatusNotice>}
      {suggestion && (
        <div className="assistant-review" aria-live="polite">
          <div className="review-title">
            <strong>Önerilen değerler</strong>
            <span>{suggestion.source === 'ollama' ? 'Yerel model' : 'Bulut modeli'}: {suggestion.model}</span>
            <span>{suggestion.explanation}</span>
          </div>
          <ConditionsEditor prefix="Önerilen " value={suggestion.conditions} onChange={conditions => onChangeSuggestion(current => ({ ...current, conditions }))} />
          {suggestion.questions?.map(question => <StatusNotice key={question}>{question}</StatusNotice>)}
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
  children,
}) {
  const normalized = normalizeWeights(criterionWeights)
  return (
    <div className="criteria-band">
      <div className="profile-control" role="group" aria-label="Seçim kriteri profili">
        {criteriaProfiles.map((profile) => (
          <button
            key={profile.id}
            className={criteriaProfile === profile.id ? 'active' : ''}
            aria-pressed={criteriaProfile === profile.id}
            onClick={() => chooseCriteriaProfile(profile.id)}
            disabled={disabled}
          >
            <strong>{profile.label}</strong>
            <span>{profile.helper}</span>
          </button>
        ))}
      </div>
      <details className="more-options">
        <summary>Ayrıntılı ayarlar</summary>
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
        {children}
      </details>
    </div>
  )
}

function RecommendationCard({ item, selected, onSelect }) {
  const costLabel = item.candidate.manual_cost != null ? `${item.candidate.manual_cost} TL/kişi (girilen)` : item.candidate.price_level != null ? ['Ücretsiz', 'Ucuz', 'Orta', 'Pahalı', 'Çok pahalı'][item.candidate.price_level] || `seviye ${item.candidate.price_level}/4` : 'Fiyat bilinmiyor'
  const ratingLabel = item.candidate.rating > 0 ? `${item.candidate.rating.toFixed(1)} puan` : 'Puan bilinmiyor'
  const cardLabel = [
    `#${item.rank} ${item.candidate.name}`,
    ratingLabel,
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
        <div className="card-rank">{item.rank}</div>
        <div className="card-copy">
          <h3>{item.candidate.name}</h3>
          <p>{item.candidate.address}</p>
          <div className="metric-row">
            <span><Star size={15} /> {ratingLabel}</span>
            <span title={costSourceLabel(item.cost_source)}><DollarSign size={15} /> {costLabel}</span>
            <span><Clock3 size={15} /> Ortalama {item.t_avg_minutes.toFixed(0)} dk, en uzun {item.t_max_minutes.toFixed(0)} dk</span>
          </div>
        </div>
        <div className="score-pill" title="Tercihlerinize uyum">%{Math.round(item.score * 100)}<small>uyum</small></div>
      </button>
      <div className="card-footer">
        <span className="card-hint">{selected ? 'Ayrıntılar yanda' : 'Ayrıntı için seçin'}</span>
        <a className="button secondary" href={item.directions_url} target="_blank" rel="noreferrer">
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
  if (!selected) return null
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
        <span>{selected.rank}. öneri</span>
        <h2>{selected.candidate.name}</h2>
        <p>{selected.explanation}</p>
      </div>

      <section className="detail-section">
        <h3>Kim ne kadar yol gider?</h3>
        <div className="person-list">
          {selected.per_user.map((user) => (
            <div key={user.user_id}>
              <span>{user.label}{user.travel_mode ? ` (${modeNames[user.travel_mode] || user.travel_mode})` : ''}</span>
              <strong>
                {user.raw_duration_minutes.toFixed(0)} dk
                {user.delta_weight !== 1 ? ` · ağırlık ${user.delta_weight.toFixed(1)}×` : ''}
              </strong>
            </div>
          ))}
        </div>
        <p className="source-note">{selected.directions_note}</p>
      </section>

      <section className="detail-section">
        <h3>Neden bu mekân?</h3>
        <ScoreBar label="Puan etkisi" value={criteriaMode ? breakdown.rating_component : breakdown.quality_norm} />
        <ScoreBar label="Fiyat uygunluğu" value={breakdown.cost_norm} />
        <ScoreBar label="Kişilere yakınlık" value={criteriaMode ? breakdown.proximity_norm : breakdown.focus_norm} />
        {!criteriaMode && <ScoreBar label="Rapor skoru" value={breakdown.report_score} />}
        {costWeightUsed && costSource.includes('nötr') && <p className="source-note">Fiyat verisi bulunmadığı için maliyet bileşeni bu adayda 0.50 kabul edildi.</p>}
      </section>

      <details className="detail-section detail-more">
        <summary>Teknik ayrıntılar</summary>
        {criteriaMode ? (
          <CriterionBars weights={selected.criterion_weights || response?.criterion_weights} />
        ) : (
          <WeightBars weights={selected.effective_weights || response?.effective_weights} />
        )}
        <div className="quality-grid">
          <span>Karar modu <strong>{decisionModeLabel(selected.decision_mode)}</strong></span>
          <span>Fiyat kaynağı <strong>{costSource}</strong></span>
          <span>Yakınlık kaynağı <strong>{focusSource}</strong></span>
          <span>Yakınlık modu <strong>{focusModeLabel(selected.focus_mode)}</strong></span>
        </div>
        {criteriaMode && (
          <div className="person-list">
            {breakdown.proximity_contributions.map((person) => (
              <div key={person.user_id}>
                <span>{person.label}</span>
                <strong>{formatWeight(person.weight)} / {person.distance_km.toFixed(1)} km</strong>
              </div>
            ))}
          </div>
        )}
      </details>
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
  const [engine, setEngine] = useState('places')
  const [transferringPlan, setTransferringPlan] = useState(false)
  const [planNotice, setPlanNotice] = useState('')
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
  const [inputMode, setInputMode] = useState(() => {
    try { return window.localStorage.getItem('ortak-input-mode') === 'synthetic' ? 'synthetic' : 'link' } catch { return 'link' }
  })
  const [roomMode, setRoomMode] = useState(false)
  const [participantLocations, setParticipantLocations] = useState(() => makeParticipantRows(initialScenario.group_size))
  const [parsedLocations, setParsedLocations] = useState([])
  const parsedLocationValues = useRef('')
  const [routeRecovery, setRouteRecovery] = useState(null)
  const [criteriaProfile, setCriteriaProfile] = useState('balanced')
  const [criterionWeights, setCriterionWeights] = useState(initialCriterionWeights)
  const [intentText, setIntentText] = useState('')
  const [intentSuggestion, setIntentSuggestion] = useState(null)
  const [conditions, setConditions] = useState(emptyConditions)
  const [contextMode, setContextMode] = useState('continue')
  const [interpreting, setInterpreting] = useState(false)
  const recommendationVersion = useRef(0)
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
  const [candidateOptions, setCandidateOptions] = useState([])
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
  const [resultPreferenceKey, setResultPreferenceKey] = useState('')
  const [scenarioExpiresAt, setScenarioExpiresAt] = useState(0)

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
    participants: inputMode === 'link' ? participantLocations.map(({ label, value, travel_mode }) => ({ label, value, travel_mode })) : null,
  })
  const currentSearchContext = useRef(searchContext)
  currentSearchContext.current = searchContext
  const canReuseRoutes = Boolean(scenario && response && scenarioContext === searchContext)
  const selectedCapacity = runtimeConfig?.google_search_capacity?.[inputMode === 'link' ? 'resolved_coordinates' : 'synthetic']?.[scenarioForm.group_size]
  const canStartSearch = Boolean(runtimeConfig && (
    (runtimeConfig.google_available && selectedCapacity?.available !== false) || (!runtimeConfig.production && health?.google_configured === false)
  ))
  const canResumeRoutes = Boolean(scenario && routeRecovery?.scenarioId === scenario.id && routeRecovery.context === searchContext)

  useEffect(() => { setCandidateOptions([]) }, [scenario?.id, searchContext])

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

  const intentContextKey = JSON.stringify({ participantLocations, criterionWeights, minRating, maxDuration, intentText, conditions, contextMode })
  const currentIntentKey = useRef(intentContextKey)
  currentIntentKey.current = intentContextKey
  function preferenceKey(overrides = {}) {
    return JSON.stringify({ weights: overrides.criterionWeights ?? criterionWeights,
      people: overrides.participantWeights ?? Object.fromEntries(intentParticipants.map(person => [person.id, person.delta_weight])),
      min: overrides.minRating ?? minRating, max: overrides.maxDuration ?? maxDuration, k, manualCosts,
      conditions: overrides.conditions ?? conditions })
  }
  const activePreferenceKey = useRef('')
  activePreferenceKey.current = preferenceKey()
  useEffect(() => { setExperiment(null) }, [activePreferenceKey.current])
  useEffect(() => {
    if (!scenarioExpiresAt) return
    const timer = setTimeout(() => {
      intentVersion.current += 1; recommendationVersion.current += 1
      setScenario(null); setScenarioContext(null); setResponse(null); setExperiment(null); setSelectedId(null)
      setRouteRecovery(null); setParsedLocations([]); parsedLocationValues.current = ''
      setParticipantLocations(makeParticipantRows(initialScenario.group_size)); setScenarioForm(initialScenario)
      setIntentText(''); setIntentSuggestion(null); setConditions(emptyConditions()); setManualCosts({})
      setCriterionWeights(initialCriterionWeights); setMinRating(''); setMaxDuration(''); setScenarioExpiresAt(0)
      setCounts({ candidates: 0, routes: 0 }); setError('Oturum süresi doldu; konumlar ve sonuçlar temizlendi. Yeni bir buluşma oluşturabilirsiniz.')
    }, Math.max(0, scenarioExpiresAt - Date.now()))
    return () => clearTimeout(timer)
  }, [scenarioExpiresAt])
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

  function checkSearchCapacity(config, activeConditions = conditions) {
    const safe = checkedConditions(activeConditions)
    if ((safe.budget_limit || safe.excluded_categories.length || safe.required_features.length) && !config.capabilities?.conditions_v1) throw new Error('Sunucu kesin koşulları henüz desteklemiyor; yeni arama başlatılmadı.')
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
    setPlanNotice('')
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
    setCriterionWeights((current) => rebalanceWeights(current, key, value))
    setCriteriaProfile('custom')
    setIntentSuggestion(null)
    setAiApplied(false)
  }


  async function interpretIntent() {
    if (interpreting) return
    const version = intentVersion.current
    const key = intentContextKey
    setError('')
    setIntentSuggestion(null)
    try {
      setInterpreting(true)
      const result = await api.interpretPreferences({
        text: intentText.trim(),
        participants: intentParticipants,
        criterion_weights: criterionWeights,
        min_rating: minRating === '' ? null : Number(minRating),
        max_duration_minutes: maxDuration === '' ? null : Number(maxDuration),
        conditions, context_mode: contextMode, context_revision: String(version),
      })
      if (version === intentVersion.current && key === currentIntentKey.current) setIntentSuggestion(result)
    } catch (err) {
      if (version === intentVersion.current && key === currentIntentKey.current) setError(err.message)
      refreshAiStatus()
    } finally {
      setInterpreting(false)
    }
  }

  async function applyIntentSuggestion(findPlaces = false) {
    if (!intentSuggestion || intentSuggestion.questions?.length) return
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
    setConditions(intentSuggestion.conditions || emptyConditions())
    setContextMode('continue')
    setAiApplied(true)
    setIntentSuggestion(null)
    const overrides = {
      criterionWeights: nextWeights,
      participantWeights: nextPersonWeights,
      minRating: nextMinRating,
      maxDuration: nextMaxDuration,
      conditions: intentSuggestion.conditions || emptyConditions(),
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
      category: scenarioForm.categories[0],
      categories: scenarioForm.categories,
      conditions: overrides.conditions ?? conditions,
      ...preferencePayload(overrides),
      ...(await advancedPriorityPayload(activeScenario, overrides)),
    }
  }

  async function buildScenarioPayload(overrides = {}) {
    if (inputMode !== 'link') {
      return {
        ...scenarioForm,
        category: scenarioForm.categories[0],
        input_mode: 'synthetic',
        session_only: false,
      }
    }
    const parsed = await parseParticipantLocations()
    return {
      ...scenarioForm,
      category: scenarioForm.categories[0],
      group_size: participantLocations.length,
      input_mode: 'link',
      session_only: true,
      participant_locations: participantLocations.map((person, index) => ({
        ...person,
        value: `${parsed[index].lat},${parsed[index].lng}`,
        delta_weight: overrides.participantWeights?.[`user-${index + 1}`] ?? person.delta_weight,
        travel_mode: person.travel_mode || null,
      })),
    }
  }

  async function runPipeline(overrides = {}) {
    if ((!canStartSearch && !canResumeRoutes) || busy || pipelineInFlight.current) return
    setPlanNotice('')
    pipelineInFlight.current = true
    const revision = ++recommendationVersion.current
    const preferences = preferenceKey(overrides)
    const ensureUnchangedInputs = () => {
      if (currentSearchContext.current !== searchContext || revision !== recommendationVersion.current) {
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
        checkSearchCapacity(config, overrides.conditions ?? conditions)
        const payload = await buildScenarioPayload(overrides)
        ensureUnchangedInputs()
        checkSearchCapacity(await refreshRuntimeConfig(), overrides.conditions ?? conditions)
        if (scenario?.session_only) await api.deleteScenario(scenario.id).catch(() => {})
        setRouteRecovery(null)
        setBusy('scenario')
        created = await api.createScenario(payload)
        if (revision !== recommendationVersion.current) return
        setScenarioExpiresAt(Date.now() + Math.min(config.session_ttl_seconds || 7200, 7200) * 1000)
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
        setCandidateOptions(candidates.map(({ id, name }) => ({ id, name })))
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
      if (revision !== recommendationVersion.current || preferences !== activePreferenceKey.current) throw new Error('Tercihler değişti. Rotalar korundu; güncel tercihlerle yeniden hesaplayın.')
      setResponse(result)
      setResultPreferenceKey(preferences)
      setSelectedId(result.recommendations[0]?.candidate.id || null)
      setRouteRecovery(null)
    } catch (err) {
      if (step === 'routes' && created && err.status !== 422 && currentSearchContext.current === searchContext) setRouteRecovery({ scenarioId: created.id, context: searchContext })
      setError(err.message)
    } finally {
      await refreshRuntimeConfig().catch(() => {})
      pipelineInFlight.current = false
      setBusy('')
    }
  }

  async function refreshRecommendations(overrides = {}) {
    if (!canReuseRoutes) return
    const revision = ++recommendationVersion.current
    const preferences = preferenceKey(overrides)
    setError('')
    try {
      setBusy('recommend')
      const result = await api.recommend(await recommendationPayload(scenario.id, overrides))
      if (revision !== recommendationVersion.current || preferences !== activePreferenceKey.current) return
      if (currentSearchContext.current !== searchContext) {
        throw new Error('Konumlar veya arama alanları değişti; eski rotalarla sonuç gösterilmedi. Güncel bilgilerle yeniden arayın.')
      }
      setResponse(result)
      setResultPreferenceKey(preferences)
      setSelectedId(result.recommendations[0]?.candidate.id || null)
    } catch (err) {
      if (revision === recommendationVersion.current && preferences === activePreferenceKey.current) setError(err.message)
    } finally {
      if (revision === recommendationVersion.current) setBusy('')
    }
  }

  async function runExperiment() {
    if (!canReuseRoutes) return
    const key = activePreferenceKey.current
    setError('')
    try {
      setBusy('experiment')
      const result = await api.runExperiment({
        scenario_id: scenario.id,
        k,
        conditions, min_rating: minRating === '' ? null : Number(minRating),
        max_duration_minutes: maxDuration === '' ? null : Number(maxDuration), category: scenarioForm.categories[0], categories: scenarioForm.categories,
        ...preferencePayload(),
        ...(await advancedPriorityPayload(scenario)),
      })
      if (key !== activePreferenceKey.current) return
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
      setIntentSuggestion(null); intentVersion.current += 1; setScenarioExpiresAt(0)
      setConditions(emptyConditions()); setManualCosts({})
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  async function transferPlan(plan) {
    if (busy || pipelineInFlight.current || transferringPlan) throw new Error('Mevcut işlemin tamamlanmasını bekleyin.')
    const next = planSearchInput(plan.handoff, runtimeConfig?.max_participants || 8)
    setTransferringPlan(true)
    try {
      if (scenario?.session_only) {
        try { await api.deleteScenario(scenario.id) }
        catch (cause) { if (cause.status !== 404) throw cause }
      }
      setScenario(null); setScenarioContext(null); setResponse(null); setSelectedId(null)
      setRouteRecovery(null); setExperiment(null); setCounts({ candidates: 0, routes: 0 }); setScenarioExpiresAt(0)
      setScenarioForm({ ...initialScenario, city: next.city, categories: [next.category], group_size: next.group_size })
      setInputMode('link'); setParticipantLocations(next.participants); setParsedLocations([]); parsedLocationValues.current = ''
      setCriterionWeights(next.weights); setCriteriaProfile(next.weights.cost === 60 ? 'cost' : 'balanced')
      setConditions(next.conditions); setContextMode('continue'); intentVersion.current += 1
      setIntentText(''); setIntentSuggestion(null); setAiApplied(false); setMinRating(''); setMaxDuration(''); setManualCosts({})
      setAdvancedPriority(false); setUseAdjustedDurations(false); setParsedFocusLocation(null); setFocusLocationInput('')
      setFocusMode('delta_weighted_participants'); setFocusUserId(ALL_DELTA_FOCUS_ID); setError('')
      setPlanNotice(`${plan.title} aktarıldı. Kişi konumlarını girdikten sonra mekân arayabilirsiniz.`)
      setEngine('places')
    } finally { setTransferringPlan(false) }
  }

  function chooseMode(mode) {
    const next = mode === 'sample' ? 'synthetic' : 'link'
    setInputMode(next); setRoomMode(mode === 'room'); setIntentSuggestion(null)
    try { window.localStorage.setItem('ortak-input-mode', next) } catch { /* optional */ }
    if (mode !== 'room' && participantLocations.length < 2) updateForm('group_size', initialScenario.group_size)
  }

  function syncRoom(points) {
    const list = points || []
    setParsedLocations([]); parsedLocationValues.current = ''
    setParticipantLocations((current) => list.map((point, index) => ({
      label: point.label || `Katılımcı ${index + 1}`,
      value: `${point.lat},${point.lng}`,
      delta_weight: current.find((row) => row.label === point.label)?.delta_weight ?? 1,
      travel_mode: point.travel_mode || '',
      place: '',
    })))
    setScenarioForm((current) => ({ ...current, group_size: list.length }))
  }

  const maxParticipants = runtimeConfig?.max_participants || 8
  const roomWaiting = roomMode && participantLocations.length < 2
  const venueNames = scenarioForm.categories.map(id => categories.find(item => item.id === id)?.label).join(', ')

  return (
    <main className="product-shell">
      <header className="app-header">
        <div className="brand-mark">
          <img className="brand-symbol" src="/favicon.svg" alt="" />
          <div>
            <h1>ORTAK</h1>
            <span>Buluşacağımız yer</span>
          </div>
        </div>
        <div className="header-actions">
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
      <nav className="engine-nav" aria-label="ORTAK bölümleri">
        <button aria-current={engine === 'places' ? 'page' : undefined} onClick={() => setEngine('places')}><MapPin size={18} />Mekân bul</button>
        <button aria-current={engine === 'plans' ? 'page' : undefined} onClick={() => setEngine('plans')}><Sparkles size={18} />Buluşma planı</button>
      </nav>
      <MeetingPlanner active={engine === 'plans'} maxParticipants={maxParticipants} available={health?.ai_ready === true}
        onTransfer={transferPlan} transferring={transferringPlan || Boolean(busy)} />
      <div hidden={engine !== 'places'} className="places-engine">
      <div className="page-intro">
        <h2>Mekân bul</h2>
        <p>Herkese uygun buluşma yerini üç adımda bulun. Ne yapacağınıza karar vermediyseniz <button type="button" className="link-button inline" onClick={() => setEngine('plans')}>Buluşma planı oluştur</button>.</p>
      </div>
      {planNotice && <StatusNotice kind="success">{planNotice}</StatusNotice>}

      <Step number={1} id="place-input" title="Nerede, ne yapacaksınız?">
        <div className="where-grid">
          <label>
            Şehir
            <input maxLength={80} value={scenarioForm.city} onChange={(event) => updateForm('city', event.target.value)} />
          </label>
          <details className="venue-picker">
            <summary><span className="summary-label">Mekân türü ({scenarioForm.categories.length}/{MAX_CATEGORIES})</span><span className="summary-value">{venueNames}</span><span className="summary-action">Değiştir</span></summary>
            <p className="privacy-note">Birden fazla tür seçebilirsiniz (en fazla {MAX_CATEGORIES}). Arama hepsini birlikte kapsar.</p>
            {categoryGroups.map(group => (
              <fieldset key={group}>
                <legend>{group}</legend>
                <div className="chips">
                  {categories.filter(item => item.group === group).map(item => {
                    const checked = scenarioForm.categories.includes(item.id)
                    return (
                      <label key={item.id}>
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={Boolean(busy) || (!checked && scenarioForm.categories.length >= MAX_CATEGORIES)}
                          onChange={() => updateForm('categories', checked
                            ? (scenarioForm.categories.length > 1 ? scenarioForm.categories.filter(id => id !== item.id) : scenarioForm.categories)
                            : [...scenarioForm.categories, item.id])}
                        />
                        {item.label}
                      </label>
                    )
                  })}
                </div>
              </fieldset>
            ))}
          </details>
        </div>
      </Step>

      <Step number={2} title="Kimler geliyor?" hint={roomMode ? 'Herkes kendi adını ve yerini girer, siz ağırlıkları seçersiniz.' : 'Herkesin nereden geleceğini girin.'}>
        <LocationPanel
          travelMode={scenarioForm.travel_mode}
          setTravelMode={(mode) => updateForm('travel_mode', mode)}
          inputMode={inputMode}
          chooseMode={chooseMode}
          roomMode={roomMode}
          roomPanel={runtimeConfig?.capabilities?.rooms_v1 ? <RoomHost result={response} people={participantLocations} disabled={Boolean(busy)} onSync={syncRoom}
            onWeight={(index, value) => updateParticipant(index, 'delta_weight', value)} /> : null}
          participantLocations={participantLocations}
          updateParticipant={updateParticipant}
          groupSize={scenarioForm.group_size}
          setGroupSize={(value) => updateForm('group_size', value)}
          maxParticipants={maxParticipants}
          parsedLocations={parsedLocations}
          busy={busy}
        />
      </Step>

      <Step number={3} id="place-preferences" label="Mekân tercihleri" title="Neye önem veriyorsunuz?" hint="Bir seçenek seçin ya da isteğinizi kendi cümlenizle yazın.">
        <SelectionCriteriaPanel
          criteriaProfile={criteriaProfile}
          chooseCriteriaProfile={chooseCriteriaProfile}
          criterionWeights={criterionWeights}
          updateCriterionWeight={updateCriterionWeight}
          disabled={Boolean(busy)}
        >
          <div className="result-filters" role="group" aria-label="Sonuç filtreleri">
            <label>
              En az puan
              <input type="number" min="0" max="5" step="0.1" placeholder="Sınır yok" value={minRating} onChange={(event) => setMinRating(event.target.value)} />
            </label>
            <label>
              En fazla süre (dk)
              <input type="number" min="1" step="1" placeholder="Sınır yok" value={maxDuration} onChange={(event) => setMaxDuration(event.target.value)} />
            </label>
            <label>
              Öneri sayısı
              <input type="number" min="1" max={runtimeConfig?.max_k || 3} value={k} onChange={(event) => setK(Math.min(runtimeConfig?.max_k || 3, Math.max(1, Number(event.target.value))))} />
            </label>
          </div>
          <details className="secondary-options"><summary>Kesin koşullar ve TL bütçesi</summary>
            <ConditionsEditor value={conditions} onChange={setConditions} disabled={Boolean(busy)} />
            {conditions.budget_limit && candidateOptions.length > 0 && <fieldset className="conditions-editor" disabled={Boolean(busy)}>
              <legend>Adayların kişi başı maliyeti</legend>
              <p>Google fiyat seviyesi TL tutarı değildir. Girdiğiniz tutarlar kullanıcı beyanıdır; gerçek fiyat doğrulaması sayılmaz.</p>
              <div className="conditions-money">{candidateOptions.map(candidate => <label key={candidate.id}>{candidate.name} (TL/kişi)
                <input aria-label={`${candidate.name} kişi başı TL`} type="number" min="0" max="10000000" placeholder="Bilinmiyor"
                  value={manualCosts[candidate.id] ?? ''} onChange={e => setManualCosts(current => ({ ...current, [candidate.id]: e.target.value }))} />
              </label>)}</div>
            </fieldset>}
          </details>
        </SelectionCriteriaPanel>
        <ConditionsSummary value={conditions} />
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
          interpreting={interpreting}
          contextMode={contextMode}
          setContextMode={setContextMode}
        />
      </Step>

      <div className="search-bar">
        <button className="primary search-button" onClick={() => runPipeline()} disabled={Boolean(busy) || roomWaiting || (!canStartSearch && !canResumeRoutes)}>
          {busy ? <Loader2 size={20} className="spin" /> : <Play size={20} />}
          {busy ? busyLabels[busy] || 'Çalışıyor' : canResumeRoutes ? 'Rotaları tamamla' : 'Buluşma yerini bul'}
        </button>
        {scenario?.session_only && <button className="secondary" onClick={deleteCurrentScenario} disabled={Boolean(busy)} title="Bu aramayı ve konumlarını sil"><Trash2 size={18} /> Aramayı sil</button>}
        {roomWaiting && <p className="privacy-note">Odada en az iki kişinin konum eklemesi bekleniyor.</p>}
        {busy && <ProgressRail busy={busy} counts={counts} response={response} />}
        {runtimeConfig && !canStartSearch && <p className="error" role="status">{selectedCapacity?.reason || runtimeConfig.google_unavailable_reason || 'Google kullanımı şu anda kapalı veya bağlantı doğrulanmadı.'}{canReuseRoutes && ' Mevcut önerilerin tercihlerini güncelleyebilirsiniz.'}</p>}
      </div>

      {error && <StatusNotice kind="error">{error}</StatusNotice>}

      <section className="result-layout" id="place-results" tabIndex={-1}>
        <div className="results-column">
          <div className="result-toolbar">
            <div>
              <h2>Önerilen yerler</h2>
              <span>{response ? `${recommendations.length} öneri · ${counts.candidates} aday arasından` : 'Arama yapınca öneriler burada görünür.'}</span>
            </div>
            <button className="secondary" onClick={() => refreshRecommendations()} disabled={!canReuseRoutes || Boolean(busy)}>
              <RefreshCcw size={16} />
              Güncelle
            </button>
          </div>
          <div className="recommendation-list">
            {recommendations.some(item => item.candidate.provider !== 'google') && <StatusNotice>Yerel test verisi: mekânlar ve süreler gerçek Google sonuçları değildir.</StatusNotice>}
            {response && resultPreferenceKey !== activePreferenceKey.current && <StatusNotice>Tercihler değişti. Gösterilen sonuçlar önceki hesaplamaya ait; Güncelle ile mevcut rotaları yeniden değerlendirin.</StatusNotice>}
            {response?.warnings?.map(warning => <StatusNotice key={warning}>{warning}</StatusNotice>)}
            <PlaceComparison key={response?.scenario?.id} items={recommendations} />
            {recommendations.length ? (
              recommendations.map((item) => (
                <RecommendationCard
                  key={item.candidate.id}
                  item={item}
                  selected={selected?.candidate.id === item.candidate.id}
                  onSelect={(next) => setSelectedId(next.candidate.id)}
                />
              ))
            ) : response ? (
              <div className="empty-results">
                <Route size={30} />
                <strong>Kısıtlara uygun mekân bulunamadı</strong>
                <span>Koşullarınız korundu. Fiyat veya zorunlu özellikler doğrulanamıyorsa uygunluk iddia edilmez.</span>
              </div>
            ) : null}
          </div>
        </div>
        {response && <DetailPanel selected={selected} response={response} />}
      </section>

      <details className="research-tools">
        <summary>Araştırma ayrıntıları (model, karşılaştırma, rapor)</summary>
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
                <p>{response ? `Bu sonuçların karar modu: ${decisionModeLabel(response.decision_mode)}. Aşağıdaki ağırlıklar sonuçla birlikte hesaplandı.` : 'Henüz sonuç yok.'}</p>
                {(scenario?.input_mode || inputMode) === 'link' && <p className="source-note">Bu senaryo oturumluk tutulur; ham kişi linkleri ve rota metrikleri kalıcı veritabanına yazılmaz.</p>}
                <CriterionBars weights={response?.criterion_weights} />
              </section>
            </div>
          )}
          {activeTab === 'compare' && <ExperimentPanel experiment={experiment} />}
          {activeTab === 'model' && <ModelDetail response={response} />}
          {activeTab === 'report' && <ReportDraft />}
        </div>
      </details>
      </div>
      <footer className="app-footer">
        <a href="/privacy.html" target="_blank" rel="noreferrer">Gizlilik</a>
        <a href="/terms.html" target="_blank" rel="noreferrer">Kullanım koşulları</a>
        <span translate="no">Built with Meta Llama 3</span>
      </footer>
    </main>
  )
}
