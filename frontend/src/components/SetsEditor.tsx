import { SET_TYPES, TEMPOS } from "../constants";

// A working copy of one set row. `id` is present only if this row already
// exists as a persisted SetPrescription — its absence is how the parent
// tells a new row apart from an edited existing one when saving.
export interface EditableSet {
  id?: number;
  set_type: string;
  tempo: string;
  rep_range_min: number;
  rep_range_max: number;
  target_weight: number | null;
}

export function newEditableSet(): EditableSet {
  return {
    set_type: "straight_set",
    tempo: "normal",
    rep_range_min: 8,
    rep_range_max: 12,
    target_weight: null,
  };
}

// Purely local editing — the parent owns persistence (it knows which rows
// are new vs. changed vs. removed, which this component doesn't track).
export function SetsEditor({
  sets,
  onChange,
  allowedSetTypes,
  allowedTempos,
}: {
  sets: EditableSet[];
  onChange: (sets: EditableSet[]) => void;
  allowedSetTypes?: string[];
  allowedTempos?: string[];
}) {
  const setTypeOptions = allowedSetTypes?.length ? allowedSetTypes : SET_TYPES;
  const tempoOptions = allowedTempos?.length ? allowedTempos : TEMPOS;

  function update(index: number, patch: Partial<EditableSet>) {
    onChange(sets.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  }

  function remove(index: number) {
    onChange(sets.filter((_, i) => i !== index));
  }

  return (
    <div className="sets-editor">
      {sets.map((set, index) => (
        <div key={set.id ?? `new-${index}`} className="sets-editor-row">
          <select
            value={set.set_type}
            onChange={(e) => update(index, { set_type: e.target.value })}
          >
            {setTypeOptions.map((t) => (
              <option key={t} value={t}>
                {t.replace("_", " ")}
              </option>
            ))}
          </select>
          <select value={set.tempo} onChange={(e) => update(index, { tempo: e.target.value })}>
            {tempoOptions.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <input
            type="number"
            inputMode="numeric"
            placeholder="min reps"
            value={set.rep_range_min}
            onChange={(e) => update(index, { rep_range_min: Number(e.target.value) })}
          />
          <input
            type="number"
            inputMode="numeric"
            placeholder="max reps"
            value={set.rep_range_max}
            onChange={(e) => update(index, { rep_range_max: Number(e.target.value) })}
          />
          <input
            type="number"
            inputMode="decimal"
            placeholder="kg (optional)"
            value={set.target_weight ?? ""}
            onChange={(e) =>
              update(index, {
                target_weight: e.target.value === "" ? null : Number(e.target.value),
              })
            }
          />
          <button type="button" className="link-button" onClick={() => remove(index)}>
            Remove
          </button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...sets, newEditableSet()])}>
        Add set
      </button>
    </div>
  );
}
