import type { Exercise } from "../api/exercises";

// The exercise library is currently just a handful of hardcoded examples
// (see app/infrastructure/seed_data.py), so a plain checkbox list is enough
// for now — no search/filter needed until the library actually grows.
export function ExercisePicker({
  exercises,
  selectedIds,
  onChange,
}: {
  exercises: Exercise[];
  selectedIds: number[];
  onChange: (ids: number[]) => void;
}) {
  function toggle(id: number) {
    onChange(
      selectedIds.includes(id) ? selectedIds.filter((x) => x !== id) : [...selectedIds, id]
    );
  }

  return (
    <div className="exercise-picker">
      {exercises.map((exercise) => (
        <label key={exercise.id} className="exercise-picker-row">
          <input
            type="checkbox"
            checked={selectedIds.includes(exercise.id)}
            onChange={() => toggle(exercise.id)}
          />
          {exercise.name} <span className="exercise-picker-meta">({exercise.equipment_name})</span>
        </label>
      ))}
    </div>
  );
}
