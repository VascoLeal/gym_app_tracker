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

export function listExercises(token: string): Promise<Exercise[]> {
  return apiFetch<Exercise[]>("/exercises", { token });
}
