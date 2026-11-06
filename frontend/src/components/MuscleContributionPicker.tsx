import { MUSCLES, MUSCLE_CONTRIBUTION_TIERS } from "../constants";
import type { MuscleContributionInput } from "../api/exercises";

// One row per muscle in the taxonomy, grouped under its muscle_group
// heading (the array is already contiguous by group — see constants.ts).
// A muscle not worked by this exercise just stays at "—"; a numeric
// contribution only gets recorded once a tier is picked.
export function MuscleContributionPicker({
  selections,
  onChange,
}: {
  selections: MuscleContributionInput[];
  onChange: (selections: MuscleContributionInput[]) => void;
}) {
  const contributionByName = new Map(selections.map((s) => [s.muscle_name, s.contribution]));

  function setTier(muscleName: string, tierValue: number | null) {
    const next = selections.filter((s) => s.muscle_name !== muscleName);
    if (tierValue !== null) {
      next.push({ muscle_name: muscleName, contribution: tierValue });
    }
    onChange(next);
  }

  let lastGroup = "";
  return (
    <div className="muscle-picker">
      {MUSCLES.map((muscle) => {
        const showGroupHeader = muscle.muscle_group !== lastGroup;
        lastGroup = muscle.muscle_group;
        const currentValue = contributionByName.get(muscle.name) ?? "";
        return (
          <div key={muscle.name}>
            {showGroupHeader && (
              <h4 className="muscle-group-header">{muscle.muscle_group.replace(/_/g, " ")}</h4>
            )}
            <div className="muscle-picker-row">
              <span>{muscle.name}</span>
              <select
                value={currentValue}
                onChange={(e) =>
                  setTier(muscle.name, e.target.value === "" ? null : Number(e.target.value))
                }
              >
                <option value="">—</option>
                {MUSCLE_CONTRIBUTION_TIERS.map((tier) => (
                  <option key={tier.label} value={tier.value}>
                    {tier.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        );
      })}
    </div>
  );
}
