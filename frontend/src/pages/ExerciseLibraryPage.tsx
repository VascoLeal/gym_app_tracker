import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import {
  createExercise,
  editExercise,
  listExercises,
  type Exercise,
  type ExerciseInput,
} from "../api/exercises";
import { MuscleContributionPicker } from "../components/MuscleContributionPicker";
import { EQUIPMENT, EXERCISE_TYPES, MOVEMENT_CATEGORIES, SET_TYPES, TEMPOS } from "../constants";

function exerciseToInput(exercise: Exercise): ExerciseInput {
  return {
    name: exercise.name,
    description: exercise.description,
    equipment_name: exercise.equipment_name,
    movement_category: exercise.movement_category,
    exercise_type: exercise.exercise_type,
    notes: exercise.notes,
    muscles: exercise.muscles.map((m) => ({
      muscle_name: m.muscle_name,
      contribution: m.contribution,
    })),
    supported_set_types: exercise.supported_set_types,
    supported_tempos: exercise.supported_tempos,
  };
}

function ExerciseForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial?: ExerciseInput;
  submitLabel: string;
  onSubmit: (input: ExerciseInput) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [equipmentName, setEquipmentName] = useState(initial?.equipment_name ?? EQUIPMENT[0]);
  const [movementCategory, setMovementCategory] = useState(
    initial?.movement_category ?? MOVEMENT_CATEGORIES[0]
  );
  const [exerciseType, setExerciseType] = useState(initial?.exercise_type ?? EXERCISE_TYPES[0]);
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [muscles, setMuscles] = useState<ExerciseInput["muscles"]>(initial?.muscles ?? []);
  const [setTypes, setSetTypes] = useState<string[]>(initial?.supported_set_types ?? []);
  const [tempos, setTempos] = useState<string[]>(initial?.supported_tempos ?? []);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canSubmit =
    name.trim() !== "" && muscles.length > 0 && setTypes.length > 0 && tempos.length > 0;

  function toggle(list: string[], setList: (v: string[]) => void, value: string) {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  }

  async function handleSubmit() {
    if (!canSubmit) return;
    setError(null);
    setIsSubmitting(true);
    try {
      await onSubmit({
        name,
        description,
        equipment_name: equipmentName,
        movement_category: movementCategory,
        exercise_type: exerciseType,
        notes,
        muscles,
        supported_set_types: setTypes,
        supported_tempos: tempos,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="exercise-form">
      {error && <p className="auth-error">{error}</p>}
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        Description
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <label>
        Equipment
        <select value={equipmentName} onChange={(e) => setEquipmentName(e.target.value)}>
          {EQUIPMENT.map((eq) => (
            <option key={eq} value={eq}>
              {eq}
            </option>
          ))}
        </select>
      </label>
      <label>
        Movement category
        <select value={movementCategory} onChange={(e) => setMovementCategory(e.target.value)}>
          {MOVEMENT_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </label>
      <label>
        Exercise type
        <select value={exerciseType} onChange={(e) => setExerciseType(e.target.value)}>
          {EXERCISE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
      <label>
        Notes
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>

      <p>Muscles worked</p>
      <MuscleContributionPicker selections={muscles} onChange={setMuscles} />

      <p>Supported set types</p>
      <div className="checkbox-list">
        {SET_TYPES.map((t) => (
          <label key={t} className="checkbox-row">
            <input
              type="checkbox"
              checked={setTypes.includes(t)}
              onChange={() => toggle(setTypes, setSetTypes, t)}
            />
            {t.replace(/_/g, " ")}
          </label>
        ))}
      </div>

      <p>Supported tempos</p>
      <div className="checkbox-list">
        {TEMPOS.map((t) => (
          <label key={t} className="checkbox-row">
            <input
              type="checkbox"
              checked={tempos.includes(t)}
              onChange={() => toggle(tempos, setTempos, t)}
            />
            {t}
          </label>
        ))}
      </div>

      <button type="button" disabled={!canSubmit || isSubmitting} onClick={handleSubmit}>
        {isSubmitting ? "Saving…" : submitLabel}
      </button>
      <button type="button" className="link-button" onClick={onCancel}>
        Cancel
      </button>
    </div>
  );
}

export function ExerciseLibraryPage({ onDone }: { onDone: () => void }) {
  const { token } = useAuth();
  const [exercises, setExercises] = useState<Exercise[] | null>(null);
  const [mode, setMode] = useState<"list" | "new" | number>("list");
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    if (!token) return;
    listExercises(token)
      .then(setExercises)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong."));
  }

  useEffect(refresh, [token]);

  if (!token || exercises === null) {
    return (
      <div className="builder-screen">
        {error ? <p className="auth-error">{error}</p> : <p>Loading…</p>}
      </div>
    );
  }

  if (mode === "new") {
    return (
      <div className="builder-screen">
        <h1>New exercise</h1>
        <ExerciseForm
          submitLabel="Create exercise"
          onSubmit={async (input) => {
            await createExercise(input, token);
            setMode("list");
            refresh();
          }}
          onCancel={() => setMode("list")}
        />
      </div>
    );
  }

  if (typeof mode === "number") {
    const exercise = exercises.find((e) => e.id === mode);
    if (!exercise) {
      return (
        <div className="builder-screen">
          <p className="auth-error">That exercise no longer exists.</p>
          <button type="button" className="link-button" onClick={() => setMode("list")}>
            Back to library
          </button>
        </div>
      );
    }
    return (
      <div className="builder-screen">
        <h1>Edit exercise</h1>
        <ExerciseForm
          initial={exerciseToInput(exercise)}
          submitLabel="Save changes"
          onSubmit={async (input) => {
            await editExercise(exercise.id, input, token);
            setMode("list");
            refresh();
          }}
          onCancel={() => setMode("list")}
        />
      </div>
    );
  }

  return (
    <div className="builder-screen">
      <h1>Exercise library</h1>
      {error && <p className="auth-error">{error}</p>}
      <button type="button" onClick={() => setMode("new")}>
        New exercise
      </button>
      {exercises.map((exercise) => (
        <div key={exercise.id} className="template-card">
          <h3>{exercise.name}</h3>
          <p className="exercise-picker-meta">
            {exercise.equipment_name} · {exercise.exercise_type} ·{" "}
            {exercise.movement_category.replace(/_/g, " ")}
          </p>
          <p>{exercise.muscles.map((m) => m.muscle_name).join(", ")}</p>
          <button type="button" className="link-button" onClick={() => setMode(exercise.id)}>
            Edit
          </button>
        </div>
      ))}
      <button type="button" className="link-button" onClick={onDone}>
        Back to Home
      </button>
    </div>
  );
}
