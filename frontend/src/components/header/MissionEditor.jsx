import { ATMOSPHERES, BODIES } from '../../domain/constants';
import { Field } from '../common';

const toInt = (e) => Math.max(0, parseInt(e.target.value) || 0);

export default function MissionEditor({ mission: M, onChange }) {
  return (
    <div className="mission-editor">
      <div className="container mission-editor__inner">
        <div className="text-md muted">Every score below is checked against both phases. A placement is safe only if it passes both.</div>

        <div className="mission-editor__cards">
          {/* Cruise */}
          <div className="card card--pad mission-card" style={{ flex: '1 1 300px' }}>
            <div className="row between">
              <div className="card-title">In-space cruise</div>
              <span className="tag mono">MICROGRAVITY</span>
            </div>
            <div className="grid-2">
              <div className="stat">
                <span className="text-sm muted">Gravity</span>
                <span className="mono stat__value">0 g</span>
              </div>
              <div className="stat">
                <span className="text-sm muted">Cabin atmosphere</span>
                <span className="mono stat__value">14.7 psia · 21% O₂</span>
              </div>
              <Field label="Ventilation">
                <select className="input" value={M.preVent} onChange={(e) => onChange('preVent', e.target.value)}>
                  <option value="normal">Normal</option>
                  <option value="reduced">Reduced</option>
                </select>
              </Field>
              <Field label="Cruise (days)">
                <input className="input mono" type="number" min="0" value={M.pad} onChange={(e) => onChange('pad', toInt(e))} />
              </Field>
            </div>
          </div>

          {/* Surface */}
          <div className="card card--pad mission-card" style={{ flex: '1 1 420px' }}>
            <div className="card-title">Surface</div>
            <div className="row gap-8">
              {Object.entries(BODIES).map(([key, b]) => (
                <button key={key} className={`body-option ${M.body === key ? 'is-active' : ''}`} onClick={() => onChange('body', key)}>
                  <span className="body-option__name">{b.name}</span>
                  <span className="mono text-sm muted">{b.gl}</span>
                </button>
              ))}
            </div>
            <div className="grid-2">
              <Field label="Cabin atmosphere" className="span-2">
                <select className="input" value={M.atm} onChange={(e) => onChange('atm', e.target.value)}>
                  {Object.keys(ATMOSPHERES).map((key) => (
                    <option key={key} value={key}>
                      {M.atmosphereName(key)} · {ATMOSPHERES[key].label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Surface stay (days)">
                <input className="input mono" type="number" min="0" value={M.stay} onChange={(e) => onChange('stay', toInt(e))} />
              </Field>
              <Field label="EVA-prep periods (high O₂)">
                <input className="input mono" type="number" min="0" value={M.eva} onChange={(e) => onChange('eva', toInt(e))} />
              </Field>
            </div>
          </div>
        </div>

        <label className={`confirm ${M.confirmed ? '' : 'is-pending'}`}>
          <input type="checkbox" checked={M.confirmed} onChange={(e) => onChange('confirmed', e.target.checked)} />
          <span className="confirm__title">These conditions are right for this mission</span>
          <span className="text-help">{M.confirmed ? 'Confirmed. Scores below use these conditions.' : 'Confirm before trusting the scores below.'}</span>
        </label>
      </div>
    </div>
  );
}
