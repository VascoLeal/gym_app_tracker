import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { listExercises, type Exercise } from "../api/exercises";
import {
  addTemplateExercise,
  addWorkoutTemplate,
  createMesocycle,
  getMesocycle,
  removeTemplateExercise,
  removeWorkoutTemplate,
  startMesocycle,
  type Mesocycle,
} from "../api/mesocycles";
import { ExercisePicker } from "../components/ExercisePicker";
import { DELOAD_STRATEGIES } from "../constants";
import { PrescriptionsSection } from "./PrescriptionsSection";

// A plain <select> for adding one more exercise to an already-created
// template — deliberately not the checkbox ExercisePicker used elsewhere,
// since that one's multi-select semantics ("pick every exercise for a brand
// new training day at once") don't fit "add a single exercise to an
// existing day" well.
function AddExerciseDropdown({
  exercises,
  excludeIds,
  onAdd,
}: {
  exercises: Exercise[];
  excludeIds: number[];
  onAdd: (exerciseId: number) => void;
}) {
  const available = exercises.filter((e) => !excludeIds.includes(e.id));
  const [selected, setSelected] = useState<number | "">(available[0]?.id ?? "");

  if (available.length === 0) {
    return <p className="exercise-picker-meta">Every library exercise is already in this day.</p>;
  }

  return (
    <div className="add-exercise-row">
      <select value={selected} onChange={(e) => setSelected(Number(e.target.value))}>
        {available.map((e) => (
          <option key={e.id} value={e.id}>
            {e.name}
          </option>
        ))}
      </select>
      <button type="button" onClick={() => selected !== "" && onAdd(selected)}>
        Add
      </button>
    </div>
  );
}

function TemplatesSection({
  mesocycle,
  exercises,
  token,
  onChanged,
}: {
  mesocycle: Mesocycle;
  exercises: Exercise[];
  token: string;
  onChanged: (updated: Mesocycle) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [isAddingTemplate, setIsAddingTemplate] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState("");
  const [newTemplateExerciseIds, setNewTemplateExerciseIds] = useState<number[]>([]);
  const [addingExerciseToTemplateId, setAddingExerciseToTemplateId] = useState<number | null>(
    null
  );

  // Foundational-shape edits (which exercises, which days) are only allowed
  // before the mesocycle starts — per project-brief.md's restriction
  // matrix, since the rotation/RPE-ramp math is built around a fixed shape.
  const isLocked = mesocycle.status !== "draft";

  async function refresh() {
    onChanged(await getMesocycle(mesocycle.id, token));
  }

  async function withErrorHandling(action: () => Promise<void>) {
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  }

  async function handleAddTemplate() {
    if (!newTemplateName || newTemplateExerciseIds.length === 0) return;
    await withErrorHandling(async () => {
      await addWorkoutTemplate(
        mesocycle.id,
        {
          name: newTemplateName,
          order_in_split: mesocycle.workout_templates.length + 1,
          exercise_ids: newTemplateExerciseIds,
        },
        token
      );
      setNewTemplateName("");
      setNewTemplateExerciseIds([]);
      setIsAddingTemplate(false);
      await refresh();
    });
  }

  return (
    <div className="templates-section">
      {error && <p className="auth-error">{error}</p>}

      {mesocycle.workout_templates
        .slice()
        .sort((a, b) => a.order_in_split - b.order_in_split)
        .map((template) => (
          <div key={template.id} className="template-card">
            <h3>{template.name}</h3>
            <ul>
              {template.exercises
                .slice()
                .sort((a, b) => a.order_in_workout - b.order_in_workout)
                .map((te) => (
                  <li key={te.id}>
                    {te.exercise_name}
                    {!isLocked && (
                      <button
                        type="button"
                        className="link-button"
                        onClick={() =>
                          withErrorHandling(async () => {
                            await removeTemplateExercise(te.id, token);
                            await refresh();
                          })
                        }
                      >
                        Remove
                      </button>
                    )}
                  </li>
                ))}
            </ul>
            {!isLocked && (
              addingExerciseToTemplateId === template.id ? (
                <>
                  <AddExerciseDropdown
                    exercises={exercises}
                    excludeIds={template.exercises.map((te) => te.exercise_id)}
                    onAdd={(exerciseId) =>
                      withErrorHandling(async () => {
                        await addTemplateExercise(template.id, exerciseId, token);
                        setAddingExerciseToTemplateId(null);
                        await refresh();
                      })
                    }
                  />
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => setAddingExerciseToTemplateId(null)}
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setAddingExerciseToTemplateId(template.id)}
                >
                  + Add exercise
                </button>
              )
            )}
            {!isLocked && (
              <button
                type="button"
                className="link-button"
                onClick={() =>
                  withErrorHandling(async () => {
                    await removeWorkoutTemplate(template.id, token);
                    await refresh();
                  })
                }
              >
                Remove training day
              </button>
            )}
          </div>
        ))}

      {!isLocked &&
        (isAddingTemplate ? (
          <div className="template-card">
            <label>
              Training day name
              <input
                value={newTemplateName}
                onChange={(e) => setNewTemplateName(e.target.value)}
              />
            </label>
            <ExercisePicker
              exercises={exercises}
              selectedIds={newTemplateExerciseIds}
              onChange={setNewTemplateExerciseIds}
            />
            <button
              type="button"
              onClick={handleAddTemplate}
              disabled={!newTemplateName || newTemplateExerciseIds.length === 0}
            >
              Add training day
            </button>
            <button type="button" className="link-button" onClick={() => setIsAddingTemplate(false)}>
              Cancel
            </button>
          </div>
        ) : (
          <button type="button" onClick={() => setIsAddingTemplate(true)}>
            + Add training day
          </button>
        ))}
    </div>
  );
}

function NewMesocycleForm({
  exercises,
  token,
  onCreated,
}: {
  exercises: Exercise[];
  token: string;
  onCreated: (mesocycle: Mesocycle) => void;
}) {
  const [name, setName] = useState("");
  const [numberOfWeeks, setNumberOfWeeks] = useState(8);
  const [deloadStrategy, setDeloadStrategy] = useState(DELOAD_STRATEGIES[0]);
  const [templateName, setTemplateName] = useState("Day 1");
  const [exerciseIds, setExerciseIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canSubmit = name.trim() !== "" && templateName.trim() !== "" && exerciseIds.length > 0;

  async function handleSubmit() {
    if (!canSubmit) return;
    setError(null);
    setIsSubmitting(true);
    try {
      const mesocycle = await createMesocycle(
        {
          name,
          number_of_weeks: numberOfWeeks,
          deload_strategy: deloadStrategy,
          workout_templates: [{ name: templateName, order_in_split: 1, exercise_ids: exerciseIds }],
        },
        token
      );
      onCreated(mesocycle);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="builder-screen">
      <h1>New mesocycle</h1>
      <p>
        A mesocycle needs at least one training day with at least one exercise to be created —
        you can add more of both right after.
      </p>
      {error && <p className="auth-error">{error}</p>}
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        Length (weeks)
        <input
          type="number"
          min={4}
          max={12}
          value={numberOfWeeks}
          onChange={(e) => setNumberOfWeeks(Number(e.target.value))}
        />
      </label>
      <label>
        Deload strategy
        <select value={deloadStrategy} onChange={(e) => setDeloadStrategy(e.target.value)}>
          {DELOAD_STRATEGIES.map((s) => (
            <option key={s} value={s}>
              {s.replace("_", " ")}
            </option>
          ))}
        </select>
      </label>
      <label>
        First training day name
        <input value={templateName} onChange={(e) => setTemplateName(e.target.value)} />
      </label>
      <p>Exercises for this day</p>
      <ExercisePicker exercises={exercises} selectedIds={exerciseIds} onChange={setExerciseIds} />
      <button type="button" disabled={!canSubmit || isSubmitting} onClick={handleSubmit}>
        {isSubmitting ? "Creating…" : "Create draft"}
      </button>
    </div>
  );
}

export function MesocycleBuilderPage({
  mesocycleId,
  onDone,
}: {
  mesocycleId: number | null;
  onDone: () => void;
}) {
  const { token } = useAuth();
  const [exercises, setExercises] = useState<Exercise[] | null>(null);
  const [mesocycle, setMesocycle] = useState<Mesocycle | null>(null);
  const [tab, setTab] = useState<"templates" | "prescriptions">("templates");
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  useEffect(() => {
    if (!token) return;
    listExercises(token)
      .then(setExercises)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong."));
  }, [token]);

  useEffect(() => {
    if (!token || mesocycleId === null) return;
    getMesocycle(mesocycleId, token)
      .then(setMesocycle)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong."));
  }, [token, mesocycleId]);

  async function handleStart() {
    if (!token || !mesocycle) return;
    setError(null);
    setIsStarting(true);
    try {
      await startMesocycle(mesocycle.id, token);
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsStarting(false);
    }
  }

  if (!token || exercises === null || (mesocycleId !== null && mesocycle === null)) {
    return (
      <div className="builder-screen">
        {error ? <p className="auth-error">{error}</p> : <p>Loading…</p>}
      </div>
    );
  }

  if (mesocycle === null) {
    return <NewMesocycleForm exercises={exercises} token={token} onCreated={setMesocycle} />;
  }

  return (
    <div className="builder-screen">
      <h1>{mesocycle.name}</h1>
      <p>
        {mesocycle.number_of_weeks} weeks · {mesocycle.deload_strategy.replace("_", " ")} deload ·{" "}
        {mesocycle.status}
      </p>
      {error && <p className="auth-error">{error}</p>}

      <div className="builder-tabs">
        <button
          type="button"
          className={tab === "templates" ? "" : "link-button"}
          onClick={() => setTab("templates")}
        >
          Training days
        </button>
        <button
          type="button"
          className={tab === "prescriptions" ? "" : "link-button"}
          onClick={() => setTab("prescriptions")}
        >
          Prescriptions
        </button>
      </div>

      {tab === "templates" ? (
        <TemplatesSection
          mesocycle={mesocycle}
          exercises={exercises}
          token={token}
          onChanged={setMesocycle}
        />
      ) : (
        <PrescriptionsSection mesocycle={mesocycle} exercises={exercises} token={token} />
      )}

      {mesocycle.status === "draft" && (
        <button type="button" onClick={handleStart} disabled={isStarting}>
          {isStarting ? "Starting…" : "Start mesocycle"}
        </button>
      )}

      <button type="button" className="link-button" onClick={onDone}>
        Back to Home
      </button>
    </div>
  );
}
