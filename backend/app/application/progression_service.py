"""
The progression engine. Per the constitution: deterministic and
explainable first, no ML, and the core decision logic must be unit-testable
without a database or web server — that's decide_progression() below.

Two separate rules, deliberately not merged into one function:
  - decide_progression(): normal week -> normal week. Looks at reps
    achieved vs. the rep range, and RPE vs. target RPE. WORKING sets only
    — warm-up sets (set_type="warmup_set") are excluded entirely, since
    they have their own independent rep/weight scheme and would corrupt
    the comparison if mixed in (see generate_next_week_prescription).
  - the reduced_load deload branch: a fixed ~50% reduction, per the
    athlete's own definition of that strategy — not something the
    rep/RPE rule table should override. Applied to every set that week,
    warm-ups included, since a lighter working weight needs less ramp-in
    too. A "rest" deload week gets nothing generated at all.

Weight recommendations are equipment-aware: barbell/dumbbell/cable/machine
gyms don't let you dial in an arbitrary number, so every recommendation
steps to the next REALISTICALLY LOADABLE weight for that equipment, not a
raw percentage. This is a bigger, more useful improvement than it looks
like at first — a "5% increase" is meaningless if the result isn't a
weight you can actually put on the bar.

v1 scope: only weight is adjusted. Rep range and set count stay fixed for
the whole mesocycle (though still editable by hand — see
mesocycle_service — just not something the algorithm changes on its own).
Volume progression (adding sets across weeks) is deferred — see
project-brief.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy.orm import Session, selectinload

from app.infrastructure.mesocycle_models import (
    ExercisePrescriptionModel,
    MesocycleModel,
    SetPrescriptionModel,
    TemplateExerciseModel,
    WeekModel,
)
from app.infrastructure.session_models import PerformedExerciseModel, SetPerformanceModel

# Algorithmic design decisions (heuristics), not scientifically derived
# constants — see constitution.md §4, fitness-science honesty. Tune freely.
RPE_INCREASE_TOLERANCE = 1.0   # actual can run up to this many points over target and still increase
RPE_DECREASE_THRESHOLD = 2.0   # actual must run at least this many points over target (every set) to decrease on RPE alone
DELOAD_WEIGHT_FACTOR = 0.5     # reduced_load deload weeks: ~50% of the prior week's weight

# Real-world loadable increments per equipment type — most gyms don't
# have 1.25kg plates, so a barbell only moves in 5kg jumps (2.5kg/side);
# dumbbells step by 1kg up to 10kg then 2.5kg above that; cables and
# machines are typically 2.5kg and 5kg respectively. Equipment not listed
# here (Bodyweight, Band, Bosu, Kettlebell, Plate, Sled, Other) falls back
# to a generic 2.5kg — genuinely unverified for those, flagged for
# revisiting once it matters for a real exercise using them.
_FIXED_INCREMENTS = {
    "Barbell": 5.0,
    "Cable Machine": 2.5,
    "Machine": 5.0,
}
_DEFAULT_INCREMENT = 2.5


def _equipment_increment(equipment_name: str, reference_weight: float) -> float:
    if equipment_name == "Dumbbell":
        return 1.0 if reference_weight < 10 else 2.5
    return _FIXED_INCREMENTS.get(equipment_name, _DEFAULT_INCREMENT)


def _step_up(weight: float, increment: float) -> float:
    """The smallest loadable weight strictly greater than `weight`."""
    return (math.floor(weight / increment) + 1) * increment


def _step_down(weight: float, increment: float) -> float:
    """The largest loadable weight strictly less than `weight`."""
    return (math.ceil(weight / increment) - 1) * increment


def _round_to_increment(weight: float, increment: float) -> float:
    """Nearest loadable weight — used for the deload scale-down, which is
    a proportion, not a directional step."""
    return round(weight / increment) * increment


@dataclass
class SetOutcome:
    actual_reps: float | None
    actual_rpe: float | None


@dataclass
class ProgressionDecision:
    direction: str  # "increase" | "hold" | "decrease"
    reason: str


def decide_progression(
    outcomes: list[SetOutcome],
    rep_range_min: int,
    rep_range_max: int,
    target_rpe: float | None,
) -> ProgressionDecision | None:
    """Pure function: no DB, no I/O, and — critically — takes only WORKING
    set outcomes. Callers must exclude warm-up sets before calling this;
    it has no way to distinguish them itself. Returns None if there isn't
    enough performance data to base a decision on (e.g. skipped entirely)."""
    usable = [o for o in outcomes if o.actual_reps is not None]
    if not usable:
        return None

    missed_reps = any(o.actual_reps < rep_range_min for o in usable)
    hit_top_of_range = all(o.actual_reps >= rep_range_max for o in usable)

    rpe_diffs = [
        o.actual_rpe - target_rpe
        for o in usable
        if o.actual_rpe is not None and target_rpe is not None
    ]

    if missed_reps:
        return ProgressionDecision(
            "decrease",
            "missed the bottom of the rep range on at least one set",
        )

    if hit_top_of_range:
        # Increase as long as RPE didn't run away — up to 1 point over
        # target is fine (e.g. target 8, actual 9), 2+ over is not
        # (target 8, actual 10). No RPE data at all: benefit of the doubt.
        if not rpe_diffs or all(d <= RPE_INCREASE_TOLERANCE for d in rpe_diffs):
            return ProgressionDecision(
                "increase",
                "hit the top of the rep range with RPE at or near target",
            )
        return ProgressionDecision(
            "hold",
            "hit the top of the rep range, but RPE ran too high to add more load yet",
        )

    # Didn't hit the top of the range, didn't miss the bottom either —
    # decrease only if EVERY set ran meaningfully over target RPE, since
    # that signals the weight is already too heavy for this stage of the
    # ramp, not just that there's room left to grow reps naturally.
    if rpe_diffs and all(d >= RPE_DECREASE_THRESHOLD for d in rpe_diffs):
        return ProgressionDecision(
            "decrease",
            "RPE ran 2+ points above target on every set, even though reps stayed in range",
        )

    return ProgressionDecision(
        "hold",
        "reps and RPE were in line with what this week called for — let reps "
        "climb naturally before the next load increase",
    )


def compute_next_weight(
    reference_weight: float | None, direction: str, equipment_name: str
) -> float | None:
    """Translates a direction into an actual loadable weight. Always moves
    at least one full increment on increase/decrease — never rounds back
    down to the same number, which a raw-percentage approach could do."""
    if reference_weight is None:
        return None
    if direction == "hold":
        return reference_weight
    increment = _equipment_increment(equipment_name, reference_weight)
    if direction == "increase":
        return _step_up(reference_weight, increment)
    if direction == "decrease":
        return _step_down(reference_weight, increment)
    raise ValueError(f"Unknown direction: {direction}")


def generate_next_week_prescription(
    db: Session, workout_session_id_performed_exercise: PerformedExerciseModel
) -> ExercisePrescriptionModel | None:
    """Called after a session completes. For ONE performed exercise, looks
    at this week's performance and — if there's a next week and it doesn't
    already have a prescription for this slot — creates one. Returns None
    if generation was skipped (no next week, already exists, exercise was
    swapped, or no usable performance data)."""
    pe = workout_session_id_performed_exercise
    if pe.template_exercise_id is None:
        return None  # an ad-hoc addition with no plan slot behind it
    if pe.exercise_id != pe.template_exercise.exercise_id:
        return None  # swapped exercise — comparing against the wrong plan

    week = pe.workout_session.week
    mesocycle = pe.workout_session.mesocycle
    next_week_number = week.week_number + 1
    if next_week_number > mesocycle.number_of_weeks:
        return None  # mesocycle ends here

    next_week = (
        db.query(WeekModel)
        .filter(
            WeekModel.mesocycle_id == mesocycle.id,
            WeekModel.week_number == next_week_number,
        )
        .first()
    )
    if next_week is None:
        return None

    if next_week.is_deload and mesocycle.deload_strategy.name == "rest":
        return None  # nothing is trained this week — no recommendation makes sense

    already_exists = (
        db.query(ExercisePrescriptionModel)
        .filter(
            ExercisePrescriptionModel.template_exercise_id == pe.template_exercise_id,
            ExercisePrescriptionModel.week_id == next_week.id,
        )
        .first()
    )
    if already_exists is not None:
        return None

    this_week_prescription = (
        db.query(ExercisePrescriptionModel)
        .options(selectinload(ExercisePrescriptionModel.sets))
        .filter(
            ExercisePrescriptionModel.template_exercise_id == pe.template_exercise_id,
            ExercisePrescriptionModel.week_id == week.id,
        )
        .first()
    )
    if this_week_prescription is None or not this_week_prescription.sets:
        return None  # nothing to progress FROM

    equipment_name = pe.template_exercise.exercise.equipment.name
    performances = {s.set_prescription_id: s for s in pe.sets if s.set_prescription_id}

    working_sets = [
        sp for sp in this_week_prescription.sets if sp.set_type.name != "warmup_set"
    ]
    if not working_sets:
        return None  # a warm-up-only prescription has nothing to progress

    outcomes = [
        SetOutcome(
            actual_reps=performances[sp.id].actual_reps if sp.id in performances else None,
            actual_rpe=performances[sp.id].actual_rpe if sp.id in performances else None,
        )
        for sp in working_sets
    ]
    working_weights_logged = [
        performances[sp.id].actual_weight
        for sp in working_sets
        if sp.id in performances and performances[sp.id].actual_weight is not None
    ]
    reference_weight = max(working_weights_logged) if working_weights_logged else None

    first_working_set = working_sets[0]
    rep_range_min = first_working_set.rep_range_min
    rep_range_max = first_working_set.rep_range_max

    if next_week.is_deload and mesocycle.deload_strategy.name == "reduced_load":
        deload_increment = _equipment_increment(equipment_name, reference_weight or 0.0)
        new_weights = {
            sp.id: (
                _round_to_increment(sp.target_weight * DELOAD_WEIGHT_FACTOR, deload_increment)
                if sp.target_weight is not None else None
            )
            for sp in this_week_prescription.sets
        }
        reason = "deload week — load reduced to ~50% per this mesocycle's reduced_load strategy"
    else:
        decision = decide_progression(outcomes, rep_range_min, rep_range_max, week.target_rpe)
        if decision is None:
            return None
        next_working_weight = compute_next_weight(reference_weight, decision.direction, equipment_name)
        # Warm-up sets carry forward UNCHANGED in a normal week — they're
        # not what progression is adjusting; see module docstring.
        new_weights = {
            sp.id: (next_working_weight if sp in working_sets else sp.target_weight)
            for sp in this_week_prescription.sets
        }
        reason = decision.reason

    next_prescription = ExercisePrescriptionModel(
        template_exercise_id=pe.template_exercise_id,
        week_id=next_week.id,
        notes=f"Auto-progressed: {reason}",
    )
    db.add(next_prescription)
    db.flush()

    for sp in this_week_prescription.sets:
        db.add(SetPrescriptionModel(
            exercise_prescription_id=next_prescription.id,
            set_number=sp.set_number,
            set_type_id=sp.set_type_id,
            tempo_id=sp.tempo_id,
            rep_range_min=sp.rep_range_min,
            rep_range_max=sp.rep_range_max,
            target_weight=new_weights[sp.id],
        ))

    return next_prescription


def generate_next_week_prescriptions_for_session(db: Session, workout_session) -> None:
    """Runs generate_next_week_prescription for every performed exercise in
    a just-completed session. Best-effort: exercises without enough data,
    already-generated slots, or swaps are silently skipped rather than
    failing the whole session completion."""
    for pe in workout_session.performed_exercises:
        generate_next_week_prescription(db, pe)
    db.commit()
