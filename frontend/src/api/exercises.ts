import { apiFetch } from "./client";

// Mirrors app/api/schemas.py — MuscleContributionResponse / ExerciseResponse.
export interface MuscleContribution {
  muscle_name: string;
  contribution: number;
}

export interface Exercise {
  id: number;
  name: string;
  description: string;
  equipment_name: string;
  movement_category: string;
  exercise_type: string;
  notes: string;
  muscles: MuscleContribution[];
  supported_set_types: string[];
  supported_tempos: string[];
}

export interface MuscleContributionInput {
  muscle_name: string;
  contribution: number;
}

export interface ExerciseInput {
  name: string;
  description: string;
  equipment_name: string;
  movement_category: string;
  exercise_type: string;
  notes: string;
  muscles: MuscleContributionInput[];
  supported_set_types: string[];
  supported_tempos: string[];
}

export function listExercises(token: string): Promise<Exercise[]> {
  return apiFetch<Exercise[]>("/exercises", { token });
}

export function createExercise(body: ExerciseInput, token: string): Promise<Exercise> {
  return apiFetch<Exercise>("/exercises", { method: "POST", body, token });
}

export function editExercise(
  exerciseId: number,
  body: ExerciseInput,
  token: string
): Promise<Exercise> {
  return apiFetch<Exercise>(`/exercises/${exerciseId}`, { method: "PATCH", body, token });
}
