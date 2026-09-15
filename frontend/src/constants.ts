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
