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

export function listMyMesocycles(token: string): Promise<Mesocycle[]> {
  return apiFetch<Mesocycle[]>("/me/mesocycles", { token });
}
