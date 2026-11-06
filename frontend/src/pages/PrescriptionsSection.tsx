import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import type { Exercise } from "../api/exercises";
import {
  addPrescription,
  addSet,
  editSet,
  listWeekPrescriptions,
  removeSet,
  type ExercisePrescription,
  type Mesocycle,
  type SetPrescription,
  type SetPrescriptionInput,
} from "../api/mesocycles";
import { newEditableSet, SetsEditor, type EditableSet } from "../components/SetsEditor";

interface Slot {
  templateExerciseId: number;
  exerciseId: number;
  exerciseName: string;
  templateName: string;
}

// Both EditableSet rows and persisted SetPrescription responses carry these
// same five fields — one converter covers turning either into the shape
// the add/edit-set endpoints expect.
function toSetInput(s: {
  set_type: string;
  tempo: string;
  rep_range_min: number;
  rep_range_max: number;
  target_weight: number | null;
}): SetPrescriptionInput {
  return {
    set_type: s.set_type,
    tempo: s.tempo,
    rep_range_min: s.rep_range_min,
    rep_range_max: s.rep_range_max,
    target_weight: s.target_weight,
  };
}

function toEditable(prescription: ExercisePrescription | undefined): EditableSet[] {
  if (!prescription || prescription.sets.length === 0) return [newEditableSet()];
  return prescription.sets
    .slice()
    .sort((a, b) => a.set_number - b.set_number)
    .map((s) => ({
      id: s.id,
      set_type: s.set_type,
      tempo: s.tempo,
      rep_range_min: s.rep_range_min,
      rep_range_max: s.rep_range_max,
      target_weight: s.target_weight,
    }));
}

function summarize(prescription: ExercisePrescription | undefined): string {
  if (!prescription || prescription.sets.length === 0) return "Not planned yet";
  const sets = prescription.sets;
  const min = Math.min(...sets.map((s) => s.rep_range_min));
  const max = Math.max(...sets.map((s) => s.rep_range_max));
  return `${sets.length} set${sets.length === 1 ? "" : "s"} · ${min}-${max} reps`;
}

export function PrescriptionsSection({
  mesocycle,
  exercises,
  token,
}: {
  mesocycle: Mesocycle;
  exercises: Exercise[];
  token: string;
}) {
  const exercisesById = new Map(exercises.map((e) => [e.id, e]));
  const slots: Slot[] = mesocycle.workout_templates.flatMap((template) =>
    template.exercises.map((te) => ({
      templateExerciseId: te.id,
      exerciseId: te.exercise_id,
      exerciseName: te.exercise_name,
      templateName: template.name,
    }))
  );
  const weeks = mesocycle.weeks.slice().sort((a, b) => a.week_number - b.week_number);
  const firstWeek = weeks[0];

  const [byWeek, setByWeek] = useState<Record<number, ExercisePrescription[]> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<{ slot: Slot; weekId: number } | null>(null);
  const [localSets, setLocalSets] = useState<EditableSet[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [copyingSlotId, setCopyingSlotId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all(weeks.map((w) => listWeekPrescriptions(w.id, token)))
      .then((results) => {
        if (cancelled) return;
        const map: Record<number, ExercisePrescription[]> = {};
        weeks.forEach((w, i) => {
          map[w.id] = results[i];
        });
        setByWeek(map);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong."));
    return () => {
      cancelled = true;
    };
    // Re-fetch only when the mesocycle's own identity changes — refreshWeek()
    // below patches individual weeks into state after a save instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mesocycle.id, token]);

  function prescriptionFor(weekId: number, templateExerciseId: number) {
    return byWeek?.[weekId]?.find((p) => p.template_exercise_id === templateExerciseId);
  }

  async function refreshWeek(weekId: number) {
    const prescriptions = await listWeekPrescriptions(weekId, token);
    setByWeek((prev) => (prev ? { ...prev, [weekId]: prescriptions } : prev));
  }

  function openEditor(slot: Slot, weekId: number) {
    setExpanded({ slot, weekId });
    setLocalSets(toEditable(prescriptionFor(weekId, slot.templateExerciseId)));
    setError(null);
  }

  async function handleSave() {
    if (!expanded) return;
    setIsSaving(true);
    setError(null);
    try {
      const existing = prescriptionFor(expanded.weekId, expanded.slot.templateExerciseId);
      if (!existing) {
        await addPrescription(
          expanded.slot.templateExerciseId,
          { week_id: expanded.weekId, sets: localSets.map(toSetInput) },
          token
        );
      } else {
        const remainingExisting = new Map<number, SetPrescription>(
          existing.sets.map((s) => [s.id, s])
        );
        for (const row of localSets) {
          if (row.id === undefined) {
            await addSet(existing.id, toSetInput(row), token);
            continue;
          }
          const before = remainingExisting.get(row.id);
          remainingExisting.delete(row.id);
          const changed =
            !before ||
            before.set_type !== row.set_type ||
            before.tempo !== row.tempo ||
            before.rep_range_min !== row.rep_range_min ||
            before.rep_range_max !== row.rep_range_max ||
            before.target_weight !== row.target_weight;
          if (changed) {
            await editSet(
              row.id,
              {
                ...toSetInput(row),
                target_weight: row.target_weight ?? undefined,
                clear_target_weight: row.target_weight === null,
              },
              token
            );
          }
        }
        // Anything left here was removed from the editor by the user.
        for (const removed of remainingExisting.values()) {
          await removeSet(removed.id, token);
        }
      }
      await refreshWeek(expanded.weekId);
      setExpanded(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCopyToAllWeeks(slot: Slot) {
    const week1 = prescriptionFor(firstWeek.id, slot.templateExerciseId);
    if (!week1 || week1.sets.length === 0) return;
    setCopyingSlotId(slot.templateExerciseId);
    setError(null);
    try {
      const sets = week1.sets.map(toSetInput);
      for (const week of weeks) {
        if (week.id === firstWeek.id) continue;
        // Skip weeks that already have their own prescription for this slot
        // so a re-run of "copy forward" never clobbers a week you already
        // customized — only fills in the still-blank ones.
        if (prescriptionFor(week.id, slot.templateExerciseId)) continue;
        await addPrescription(slot.templateExerciseId, { week_id: week.id, sets }, token);
      }
      await Promise.all(weeks.map((w) => refreshWeek(w.id)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setCopyingSlotId(null);
    }
  }

  if (byWeek === null) {
    return <p>Loading prescriptions…</p>;
  }

  return (
    <div className="prescriptions-section">
      {error && <p className="auth-error">{error}</p>}
      {slots.map((slot) => {
        const exercise = exercisesById.get(slot.exerciseId);
        const week1 = prescriptionFor(firstWeek.id, slot.templateExerciseId);
        const canCopy = !!week1 && week1.sets.length > 0 && weeks.length > 1;
        return (
          <div key={slot.templateExerciseId} className="prescription-slot">
            <h3>
              {slot.exerciseName} <span className="exercise-picker-meta">({slot.templateName})</span>
            </h3>
            {canCopy && (
              <button
                type="button"
                className="link-button"
                disabled={copyingSlotId === slot.templateExerciseId}
                onClick={() => handleCopyToAllWeeks(slot)}
              >
                {copyingSlotId === slot.templateExerciseId
                  ? "Copying…"
                  : "Copy week 1 to all still-unplanned weeks"}
              </button>
            )}
            <table className="prescription-week-table">
              <tbody>
                {weeks.map((week) => {
                  const prescription = prescriptionFor(week.id, slot.templateExerciseId);
                  const isExpanded =
                    expanded?.slot.templateExerciseId === slot.templateExerciseId &&
                    expanded.weekId === week.id;
                  return (
                    <tr key={week.id}>
                      <td>
                        Week {week.week_number}
                        {week.is_deload ? " (deload)" : ""}
                        {week.target_rpe != null ? ` · target RPE ${week.target_rpe}` : ""}
                      </td>
                      {isExpanded ? (
                        <td>
                          <SetsEditor
                            sets={localSets}
                            onChange={setLocalSets}
                            allowedSetTypes={exercise?.supported_set_types}
                            allowedTempos={exercise?.supported_tempos}
                          />
                          <button type="button" onClick={handleSave} disabled={isSaving}>
                            {isSaving ? "Saving…" : "Save"}
                          </button>
                          <button
                            type="button"
                            className="link-button"
                            onClick={() => setExpanded(null)}
                          >
                            Cancel
                          </button>
                        </td>
                      ) : (
                        <td>
                          {summarize(prescription)}{" "}
                          <button
                            type="button"
                            className="link-button"
                            onClick={() => openEditor(slot, week.id)}
                          >
                            {prescription ? "Edit" : "Plan"}
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
