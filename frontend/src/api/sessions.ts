import { apiFetch } from "./client";

// Mirrors app/api/schemas.py — PrescribedSetResponse / SetPerformanceResponse /
// PerformedExerciseResponse / WorkoutSessionResponse.
export interface PrescribedSet {
  id: number;
  set_number: number;
  set_type: string;
  tempo: string;
  rep_range_min: number;
  rep_range_max: number;
  target_rpe: number | null;
  target_weight: number | null;
}

export interface SetPerformance {
  id: number;
  set_prescription_id: number | null;
  set_number: number;
  actual_weight: number | null;
  actual_reps: number | null;
  actual_rpe: number | null;
  notes: string | null;
}

export interface PerformedExercise {
  id: number;
  template_exercise_id: number | null;
  exercise_id: number;
  exercise_name: string;
  order_performed: number;
  prescribed_sets: PrescribedSet[];
  performed_sets: SetPerformance[];
}

export interface WorkoutSession {
  id: number;
  mesocycle_id: number;
  week_id: number;
  workout_template_id: number;
  status: "in_progress" | "completed" | "abandoned";
  started_at: string;
  completed_at: string | null;
  performed_exercises: PerformedExercise[];
}

export interface LogSetInput {
  set_prescription_id?: number | null;
  actual_weight?: number | null;
  actual_reps?: number | null;
  actual_rpe?: number | null;
  notes?: string | null;
}

export function startSession(mesocycleId: number, token: string): Promise<WorkoutSession> {
  return apiFetch<WorkoutSession>(`/mesocycles/${mesocycleId}/sessions/start`, {
    method: "POST",
    token,
  });
}

export function getSession(sessionId: number, token: string): Promise<WorkoutSession> {
  return apiFetch<WorkoutSession>(`/workout-sessions/${sessionId}`, { token });
}

export function logSet(
  performedExerciseId: number,
  body: LogSetInput,
  token: string
): Promise<SetPerformance> {
  return apiFetch<SetPerformance>(`/performed-exercises/${performedExerciseId}/sets`, {
    method: "POST",
    body,
    token,
  });
}

export function completeSession(sessionId: number, token: string): Promise<WorkoutSession> {
  return apiFetch<WorkoutSession>(`/workout-sessions/${sessionId}/complete`, {
    method: "POST",
    token,
  });
}

export function abandonSession(sessionId: number, token: string): Promise<WorkoutSession> {
  return apiFetch<WorkoutSession>(`/workout-sessions/${sessionId}/abandon`, {
    method: "POST",
    token,
  });
}
