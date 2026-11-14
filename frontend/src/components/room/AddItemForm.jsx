import { Field } from '../common';

export default function AddItemForm({ library, form, newMat, actions, onAdd }) {
  const ok = form.qty >= 1 && +form.l > 0 && +form.w > 0 && +form.h > 0;
  const set = (key) => (e) => actions.setFormField(key, e.target.value);

  return (
    <div className="col gap-8">
      <div className="eyebrow">ADD TO THIS SPACE</div>

      <select className="input" value={form.lib} onChange={set('lib')}>
        {library.groups().map((g) => (
          <optgroup key={g.label} label={g.label}>
            {g.options.map((o) => (
              <option key={o.key} value={o.key}>
                {o.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>

      <div className="grid-4">
        <Field label="Qty" small>
          <input className="input input--sm mono" type="number" min="1" value={form.qty} onChange={(e) => actions.setFormField('qty', parseInt(e.target.value) || '')} />
        </Field>
        {[
          ['l', 'L cm'],
          ['w', 'W cm'],
          ['h', 'H cm'],
        ].map(([k, label]) => (
          <Field key={k} label={label} small>
            <input className="input input--sm mono" type="number" min="0" placeholder="—" value={form[k]} onChange={set(k)} />
          </Field>
        ))}
      </div>

      <div className="row gap-10">
        <button className="btn btn--amber" disabled={!ok} onClick={onAdd}>
          Add item
        </button>
        <button className="link-btn" onClick={actions.toggleNewMaterial}>
          + Add a new material
        </button>
        <span className="text-xs faint push-right">All fields required</span>
      </div>

      {newMat && (
        <div className="new-material">
          <Field label="Material name" small className="flex-1">
            <input
              className="input input--sm"
              placeholder="e.g. Kapton tape"
              value={newMat.name}
              onChange={(e) => actions.setNewMaterialField('name', e.target.value)}
            />
          </Field>
          <Field label="Flammability" small>
            <select className="input input--sm" value={newMat.flam} onChange={(e) => actions.setNewMaterialField('flam', e.target.value)}>
              <option value="1">Low</option>
              <option value="2">Moderate</option>
              <option value="3">High</option>
            </select>
          </Field>
          <button className="btn btn--dark btn--sm-h" onClick={actions.saveNewMaterial}>
            Save
          </button>
        </div>
      )}
    </div>
  );
}
