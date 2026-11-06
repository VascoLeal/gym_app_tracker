import { apiFetch } from "./client";

// Mirrors app/api/schemas.py — WeekResponse / TemplateExerciseResponse /
// WorkoutTemplateResponse / MesocycleResponse. Hand-mirrored like auth.ts;
// same "nothing enforces this stays in sync" caveat applies.
export interface Week {
  id: number;
  week_number: number;
  is_deload: boolean;
  target_rpe: number | null;
}

export interface TemplateExercise {
  id: number;
  exercise_id: number;
  exercise_name: string;
  order_in_workout: number;
}

export interface WorkoutTemplate {
  id: number;
  name: string;
  order_in_split: number;
  exercises: TemplateExercise[];
}

export interface Mesocycle {
  id: number;
  athlete_id: number;
  name: string;
  number_of_weeks: number;
  deload_strategy: string;
  status: "draft" | "active" | "completed" | "abandoned";
  sessions_completed: number;
  current_week_number: number;
  next_workout_template_id: number | null;
  in_progress_session_id: number | null;
  weeks: Week[];
  workout_templates: WorkoutTemplate[];
}

export interface SetPrescription {
  id: number;
  set_number: number;
  set_type: string;
  tempo: string;
  rep_range_min: number;
  rep_range_max: number;
  target_rpe: number | null;
  target_weight: number | null;
}

export interface ExercisePrescription {
  id: number;
  template_exercise_id: number;
  week_id: number;
  notes: string;
  sets: SetPrescription[];
}

export interface WorkoutTemplateInput {
  name: string;
  order_in_split: number;
  exercise_ids: number[];
}

export interface SetPrescriptionInput {
  set_type: string;
  tempo: string;
  rep_range_min: number;
  rep_range_max: number;
  target_weight?: number | null;
}

export function listMyMesocycles(token: string): Promise<Mesocycle[]> {
  return apiFetch<Mesocycle[]>("/me/mesocycles", { token });
}

export function getMesocycle(mesocycleId: number, token: string): Promise<Mesocycle> {
  return apiFetch<Mesocycle>(`/mesocycles/${mesocycleId}`, { token });
}

export function createMesocycle(
  body: {
    name: string;
    number_of_weeks: number;
    deload_strategy: string;
    workout_templates: WorkoutTemplateInput[];
  },
  token: string
): Promise<Mesocycle> {
  return apiFetch<Mesocycle>("/mesocycles", { method: "POST", body, token });
}

export function editMesocycle(
  mesocycleId: number,
  body: { name?: string; number_of_weeks?: number; deload_strategy?: string },
  token: string
): Promise<Mesocycle> {
  return apiFetch<Mesocycle>(`/mesocycles/${mesocycleId}`, { method: "PATCH", body, token });
}

export function startMesocycle(mesocycleId: number, token: string): Promise<Mesocycle> {
  return apiFetch<Mesocycle>(`/mesocycles/${mesocycleId}/start`, { method: "POST", token });
}

export function addWorkoutTemplate(
  mesocycleId: number,
  body: { name: string; order_in_split: number; exercise_ids: number[] },
  token: string
): Promise<WorkoutTemplate> {
  return apiFetch<WorkoutTemplate>(`/mesocycles/${mesocycleId}/workout-templates`, {
    method: "POST",
    body,
    token,
  });
}

export function editWorkoutTemplate(
  workoutTemplateId: number,
  body: { name: string },
  token: string
): Promise<WorkoutTemplate> {
  return apiFetch<WorkoutTemplate>(`/workout-templates/${workoutTemplateId}`, {
    method: "PATCH",
    body,
    token,
  });
}

export function reorderWorkoutTemplate(
  workoutTemplateId: number,
  newPosition: number,
  token: string
): Promise<WorkoutTemplate[]> {
  return apiFetch<WorkoutTemplate[]>(`/workout-templates/${workoutTemplateId}/order`, {
    method: "PATCH",
    body: { new_position: newPosition },
    token,
  });
}

export function removeWorkoutTemplate(workoutTemplateId: number, token: string): Promise<void> {
  return apiFetch<void>(`/workout-templates/${workoutTemplateId}`, {
    method: "DELETE",
    token,
  });
}

export function addTemplateExercise(
  workoutTemplateId: number,
  exerciseId: number,
  token: string
): Promise<TemplateExercise> {
  return apiFetch<TemplateExercise>(`/workout-templates/${workoutTemplateId}/exercises`, {
    method: "POST",
    body: { exercise_id: exerciseId },
    token,
  });
}

export function editTemplateExercise(
  templateExerciseId: number,
  exerciseId: number,
  token: string
): Promise<TemplateExercise> {
  return apiFetch<TemplateExercise>(`/template-exercises/${templateExerciseId}`, {
    method: "PATCH",
    body: { exercise_id: exerciseId },
    token,
  });
}

export function reorderTemplateExercise(
  templateExerciseId: number,
  newPosition: number,
  token: string
): Promise<TemplateExercise[]> {
  return apiFetch<TemplateExercise[]>(`/template-exercises/${templateExerciseId}/order`, {
    method: "PATCH",
    body: { new_position: newPosition },
    token,
  });
}

export function removeTemplateExercise(templateExerciseId: number, token: string): Promise<void> {
  return apiFetch<void>(`/template-exercises/${templateExerciseId}`, {
    method: "DELETE",
    token,
  });
}

export function addPrescription(
  templateExerciseId: number,
  body: { week_id: number; notes?: string; sets: SetPrescriptionInput[] },
  token: string
): Promise<ExercisePrescription> {
  return apiFetch<ExercisePrescription>(`/template-exercises/${templateExerciseId}/prescriptions`, {
    method: "POST",
    body,
    token,
  });
}

export function editPrescriptionNotes(
  exercisePrescriptionId: number,
  notes: string,
  token: string
): Promise<ExercisePrescription> {
  return apiFetch<ExercisePrescription>(`/exercise-prescriptions/${exercisePrescriptionId}`, {
    method: "PATCH",
    body: { notes },
    token,
  });
}

export function removePrescription(exercisePrescriptionId: number, token: string): Promise<void> {
  return apiFetch<void>(`/exercise-prescriptions/${exercisePrescriptionId}`, {
    method: "DELETE",
    token,
  });
}

export function addSet(
  exercisePrescriptionId: number,
  body: SetPrescriptionInput,
  token: string
): Promise<SetPrescription> {
  return apiFetch<SetPrescription>(`/exercise-prescriptions/${exercisePrescriptionId}/sets`, {
    method: "POST",
    body,
    token,
  });
}

export function editSet(
  setPrescriptionId: number,
  body: Partial<SetPrescriptionInput> & { clear_target_weight?: boolean },
  token: string
): Promise<SetPrescription> {
  return apiFetch<SetPrescription>(`/set-prescriptions/${setPrescriptionId}`, {
    method: "PATCH",
    body,
    token,
  });
}

export function removeSet(setPrescriptionId: number, token: string): Promise<void> {
  return apiFetch<void>(`/set-prescriptions/${setPrescriptionId}`, {
    method: "DELETE",
    token,
  });
}

export function listWeekPrescriptions(
  weekId: number,
  token: string
): Promise<ExercisePrescription[]> {
  return apiFetch<ExercisePrescription[]>(`/weeks/${weekId}/prescriptions`, { token });
}
