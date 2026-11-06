import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import {
  abandonSession,
  completeSession,
  getSession,
  logSet,
  type PerformedExercise,
  type PrescribedSet,
  type SetPerformance,
  type WorkoutSession,
} from "../api/sessions";

// One row per set: either the read-only result of an already-logged set,
// or an input form for the next one. Weight is pre-filled from the
// prescription's target_weight (decided before lifting); reps/RPE are only
// known after, so they start blank — matches the 2026-09-02 design note
// this screen is finally implementing for real.
function SetRow({
  setNumber,
  prescribed,
  performed,
  onLog,
}: {
  setNumber: number;
  prescribed: PrescribedSet | null;
  performed: SetPerformance | null;
  onLog: (weight: number | null, reps: number | null, rpe: number | null, notes: string) => Promise<void>;
}) {
  const [weight, setWeight] = useState(prescribed?.target_weight?.toString() ?? "");
  const [reps, setReps] = useState("");
  const [rpe, setRpe] = useState("");
  const [notes, setNotes] = useState("");
  const [isLogging, setIsLogging] = useState(false);

  if (performed) {
    return (
      <div className="set-row set-row-done">
        <span className="set-label">Set {setNumber}</span>
        <span>
          {performed.actual_weight ?? "–"}kg × {performed.actual_reps ?? "–"} @ RPE{" "}
          {performed.actual_rpe ?? "–"}
        </span>
        {performed.notes && <span className="set-note">{performed.notes}</span>}
      </div>
    );
  }

  const target = prescribed
    ? `${prescribed.rep_range_min}-${prescribed.rep_range_max} reps${
        prescribed.target_rpe != null ? ` @ RPE ${prescribed.target_rpe}` : ""
      }`
    : "extra set";

  return (
    <div className="set-row">
      <span className="set-label">
        Set {setNumber} <span className="set-target">({target})</span>
      </span>
      <div className="set-inputs">
        <input
          type="number"
          inputMode="decimal"
          placeholder="kg"
          value={weight}
          onChange={(e) => setWeight(e.target.value)}
        />
        <input
          type="number"
          inputMode="numeric"
          placeholder="reps"
          value={reps}
          onChange={(e) => setReps(e.target.value)}
        />
        <input
          type="number"
          inputMode="decimal"
          placeholder="RPE"
          value={rpe}
          onChange={(e) => setRpe(e.target.value)}
        />
      </div>
      <input
        type="text"
        placeholder="Note (optional)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        className="set-note-input"
      />
      <button
        type="button"
        disabled={isLogging}
        onClick={async () => {
          setIsLogging(true);
          try {
            await onLog(
              weight ? Number(weight) : null,
              reps ? Number(reps) : null,
              rpe ? Number(rpe) : null,
              notes
            );
          } finally {
            setIsLogging(false);
          }
        }}
      >
        {isLogging ? "Logging…" : "Log set"}
      </button>
    </div>
  );
}

function ExerciseCard({
  exercise,
  token,
  onLogged,
}: {
  exercise: PerformedExercise;
  token: string;
  onLogged: () => void;
}) {
  const nextIndex = exercise.performed_sets.length;
  const rows = exercise.performed_sets.map((performed, i) => ({
    setNumber: i + 1,
    prescribed: exercise.prescribed_sets[i] ?? null,
    performed,
  }));
  // One extra row for the next set to log: the matching prescribed set if
  // there is one, otherwise an unprescribed "extra set" row.
  const hasMoreToLog =
    nextIndex < exercise.prescribed_sets.length || exercise.prescribed_sets.length === 0;

  async function handleLog(
    weight: number | null,
    reps: number | null,
    rpe: number | null,
    notes: string
  ) {
    const nextPrescribed = exercise.prescribed_sets[nextIndex] ?? null;
    await logSet(
      exercise.id,
      {
        set_prescription_id: nextPrescribed?.id ?? null,
        actual_weight: weight,
        actual_reps: reps,
        actual_rpe: rpe,
        notes: notes || null,
      },
      token
    );
    onLogged();
  }

  return (
    <div className="exercise-card">
      <h2>{exercise.exercise_name}</h2>
      {rows.map((row) => (
        <SetRow
          key={row.setNumber}
          setNumber={row.setNumber}
          prescribed={row.prescribed}
          performed={row.performed}
          onLog={handleLog}
        />
      ))}
      {hasMoreToLog && (
        <SetRow
          setNumber={nextIndex + 1}
          prescribed={exercise.prescribed_sets[nextIndex] ?? null}
          performed={null}
          onLog={handleLog}
        />
      )}
    </div>
  );
}

export function WorkoutPage({
  sessionId,
  onExit,
}: {
  sessionId: number;
  onExit: () => void;
}) {
  const { token } = useAuth();
  const [session, setSession] = useState<WorkoutSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isFinishing, setIsFinishing] = useState(false);

  function refresh() {
    if (!token) return;
    getSession(sessionId, token)
      .then(setSession)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong."));
  }

  useEffect(refresh, [sessionId, token]);

  async function handleComplete() {
    if (!token) return;
    setIsFinishing(true);
    try {
      await completeSession(sessionId, token);
      onExit();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsFinishing(false);
    }
  }

  async function handleAbandon() {
    if (!token) return;
    setIsFinishing(true);
    try {
      await abandonSession(sessionId, token);
      onExit();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsFinishing(false);
    }
  }

  if (!session) {
    return (
      <div className="workout-screen">
        {error ? <p className="auth-error">{error}</p> : <p>Loading…</p>}
      </div>
    );
  }

  return (
    <div className="workout-screen">
      <h1>Workout</h1>
      {error && <p className="auth-error">{error}</p>}

      {session.performed_exercises
        .slice()
        .sort((a, b) => a.order_performed - b.order_performed)
        .map((exercise) => (
          <ExerciseCard
            key={exercise.id}
            exercise={exercise}
            token={token!}
            onLogged={refresh}
          />
        ))}

      <div className="workout-actions">
        <button type="button" onClick={handleComplete} disabled={isFinishing}>
          {isFinishing ? "Saving…" : "Complete Workout"}
        </button>
        <button
          type="button"
          className="link-button"
          onClick={handleAbandon}
          disabled={isFinishing}
        >
          Abandon workout
        </button>
      </div>
    </div>
  );
}
