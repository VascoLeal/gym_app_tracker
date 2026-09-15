// Mirrors app/infrastructure/seed_data.py's reference-table seed values.
// Hand-mirrored like the API types — nothing enforces this stays in sync.
export const SET_TYPES = [
  "warmup_set",
  "straight_set",
  "super_set",
  "circuit_set",
  "drop_set",
  "pyramid_set",
  "myo_rep_set",
];

export const TEMPOS = ["normal", "slow", "explosive", "paused"];

export const DELOAD_STRATEGIES = ["rest", "reduced_load", "none"];

export const EQUIPMENT = [
  "Barbell",
  "Dumbbell",
  "Cable Machine",
  "Machine",
  "Bodyweight",
  "Band",
  "Bosu",
  "Kettlebell",
  "Plate",
  "Sled",
  "Other",
];

export const MOVEMENT_CATEGORIES = [
  "horizontal_push",
  "vertical_push",
  "horizontal_pull",
  "vertical_pull",
  "squat_knee_dominant",
  "squat_hip_dominant",
  "hip_extension",
  "knee_flexion",
  "other",
];

export const EXERCISE_TYPES = ["compound", "isolation", "warmup"];

export interface MuscleDefinition {
  name: string;
  muscle_group: string;
}

export const MUSCLES: MuscleDefinition[] = [
  { name: "Upper Chest", muscle_group: "chest" },
  { name: "Mid Chest", muscle_group: "chest" },
  { name: "Lower Chest", muscle_group: "chest" },
  { name: "Lats", muscle_group: "back" },
  { name: "Traps", muscle_group: "back" },
  { name: "Rhomboids", muscle_group: "back" },
  { name: "Front Delts", muscle_group: "shoulders" },
  { name: "Lateral Delts", muscle_group: "shoulders" },
  { name: "Rear Delts", muscle_group: "shoulders" },
  { name: "Rotator Cuff", muscle_group: "shoulders" },
  { name: "Biceps Long Head", muscle_group: "biceps" },
  { name: "Biceps Short Head", muscle_group: "biceps" },
  { name: "Triceps Long Head", muscle_group: "triceps" },
  { name: "Triceps Lateral Head", muscle_group: "triceps" },
  { name: "Triceps Medial Head", muscle_group: "triceps" },
  { name: "Upper Abs", muscle_group: "core" },
  { name: "Lower Abs", muscle_group: "core" },
  { name: "Obliques", muscle_group: "core" },
  { name: "Glute Max", muscle_group: "glutes" },
  { name: "Glute Med", muscle_group: "glutes" },
  { name: "Glute Min", muscle_group: "glutes" },
  { name: "Rectus Femoris", muscle_group: "quadriceps" },
  { name: "Vastus Lateralis", muscle_group: "quadriceps" },
  { name: "Vastus Medialis", muscle_group: "quadriceps" },
  { name: "Biceps Femoris", muscle_group: "hamstrings" },
  { name: "Semitendinosus", muscle_group: "hamstrings" },
  { name: "Semimembranosus", muscle_group: "hamstrings" },
  { name: "Gastrocnemius", muscle_group: "calves" },
  { name: "Soleus", muscle_group: "calves" },
  { name: "Tibialis Anterior", muscle_group: "tibialis" },
  { name: "Full Body", muscle_group: "full_body" },
  { name: "Other", muscle_group: "other" },
];

// Simplified tiers for the authoring form's muscle-contribution picker —
// a personal-scale library doesn't need the friction of typing an exact
// float per muscle. Still stores as the same numeric `contribution` the
// domain model expects (see domain/exercise.py's MuscleContribution).
export const MUSCLE_CONTRIBUTION_TIERS = [
  { label: "Primary", value: 1.0 },
  { label: "Secondary", value: 0.5 },
  { label: "Tertiary", value: 0.3 },
] as const;
