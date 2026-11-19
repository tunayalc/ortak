import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'

export const emptyConditions = () => ({ budget_limit: null, excluded_categories: [], required_features: [] })
export const categoryNames = { cafe: 'Kafe', restaurant: 'Restoran', park: 'Park', museum: 'Müze', library: 'Kütüphane' }
const featureNames = { quiet: 'Sessizlik', accessible: 'Erişilebilirlik', alcohol_free: 'Alkolsüz mekân' }

export function StatusNotice({ kind = 'info', children }) {
  const Icon = kind === 'loading' ? Loader2 : kind === 'success' ? CheckCircle2 : AlertCircle
  return <div className={`status-notice status-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
    <Icon size={18} aria-hidden="true" className={kind === 'loading' ? 'spin' : ''} /><div>{children}</div>
  </div>
}

export function WorkflowNav({ steps, current }) {
  return <nav className="workflow-nav" aria-label="İşlem aşamaları">{steps.map(([id, title], index) =>
    <a key={id} href={`#${id}`} aria-current={current === index ? 'step' : undefined}
      onClick={event => { event.preventDefault(); const target = document.getElementById(id); target?.focus({ preventScroll: true }); target?.scrollIntoView({ block: 'start' }) }}>
      <span>{index + 1}</span>{title}
    </a>)}
  </nav>
}

export function ConditionsSummary({ value = emptyConditions() }) {
  const budget = value.budget_limit
  return <div className="condition-summary">
    {budget && <p><strong>{budget.scope === 'group' ? 'Tüm grup için toplam' : 'Kişi başına'} {Number(budget.amount).toLocaleString('tr-TR')} TL</strong> - Fiyat verisiyle doğrulanması gerekiyor.</p>}
    {value.excluded_categories?.length > 0 && <p>Hariç: {value.excluded_categories.map(id => categoryNames[id]).join(', ')}</p>}
    {value.required_features?.length > 0 && <p>Zorunlu: {value.required_features.map(id => featureNames[id]).join(', ')}. Kaynakta doğrulanamıyor.</p>}
  </div>
}

export function ConditionsEditor({ value = emptyConditions(), onChange, prefix = '', disabled = false }) {
  const change = patch => onChange({ ...emptyConditions(), ...value, ...patch })
  const budget = value.budget_limit
  return <fieldset className="conditions-editor" disabled={disabled}>
    <legend>{prefix}Kesin koşullar</legend>
    <div className="conditions-money">
      <label>{prefix}TL bütçesi<input type="number" min="1" max="10000000" placeholder="Sınır yok" value={budget?.amount ?? ''}
        onChange={e => change({ budget_limit: e.target.value === '' ? null : { amount: Number(e.target.value), scope: budget?.scope || 'group', currency: 'TRY' } })} /></label>
      <label>{prefix}Bütçenin kapsamı<select aria-label={`${prefix}Bütçenin kapsamı`} value={budget?.scope || 'group'} disabled={!budget || disabled}
        onChange={e => change({ budget_limit: { ...budget, scope: e.target.value } })}>
        <option value="group">Tüm grup için toplam</option><option value="per_person">Kişi başına</option>
      </select></label>
    </div>
    <div className="condition-options" role="group" aria-label={`${prefix}Hariç tutulan mekânlar`}>{Object.entries(categoryNames).map(([id, name]) =>
      <label key={id}><input type="checkbox" checked={value.excluded_categories?.includes(id) || false}
        onChange={e => change({ excluded_categories: e.target.checked ? [...value.excluded_categories, id] : value.excluded_categories.filter(item => item !== id) })} />{name} olmasın</label>)}</div>
    {value.required_features?.map(id => <label className="condition-feature" key={id}><input type="checkbox" checked
      onChange={() => change({ required_features: value.required_features.filter(item => item !== id) })} />{featureNames[id]} zorunlu</label>)}
    <ConditionsSummary value={value} />
  </fieldset>
}
