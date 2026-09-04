"""
The progression engine. Per the constitution: deterministic and
explainable first, no ML, and the core decision logic must be unit-testable
without a database or web server — that's decide_progression() below.

Two separate rules, deliberately not merged into one function:
  - decide_progression(): normal week -> normal week. Looks at reps
    achieved vs. the rep range, and RPE vs. target RPE.
  - deload_weight(): normal week -> a "reduced_load" deload week. A fixed
    50% reduction, per the athlete's own definition of that strategy —
    not something the rep/RPE rule table should override.
A "rest" deload week gets nothing generated; there's nothing to train.

v1 scope: only weight is adjusted. Rep range and set count stay fixed for
the whole mesocycle. Volume progression (adding sets across weeks) is a
real technique, just deferred — see project-brief.md.
"""

from __future__ import annotations

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
WEIGHT_INCREASE_FACTOR = 1.05
WEIGHT_DECREASE_FACTOR = 0.95
DELOAD_WEIGHT_FACTOR = 0.5
RPE_OVERSHOOT_THRESHOLD = 0.5  # more than this many points above target = "too hard"
WEIGHT_ROUNDING_INCREMENT = 2.5  # assumes kg; revisit for lb users or per-equipment


@dataclass
class SetOutcome:
    actual_reps: float | None
    actual_rpe: float | None


@dataclass
class ProgressionDecision:
    direction: str  # "increase" | "hold" | "decrease"
    weight_factor: float
    reason: str


def _round_weight(value: float) -> float:
    return round(value / WEIGHT_ROUNDING_INCREMENT) * WEIGHT_ROUNDING_INCREMENT


def decide_progression(
    outcomes: list[SetOutcome],
    rep_range_min: int,
    rep_range_max: int,
    target_rpe: float | None,
) -> ProgressionDecision | None:
    """Pure function: no DB, no I/O. Returns None if there isn't enough
    performance data to base a decision on (e.g. the exercise was skipped
    entirely that session)."""
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
    avg_rpe_diff = sum(rpe_diffs) / len(rpe_diffs) if rpe_diffs else 0.0

    if missed_reps:
        return ProgressionDecision(
            "decrease", WEIGHT_DECREASE_FACTOR,
            "reduced load — missed the rep range on at least one set",
        )
    if hit_top_of_range and avg_rpe_diff <= 0:
        return ProgressionDecision(
            "increase", WEIGHT_INCREASE_FACTOR,
            "increased load — hit the top of the rep range at or below target RPE",
        )
    if avg_rpe_diff > RPE_OVERSHOOT_THRESHOLD:
        return ProgressionDecision(
            "decrease", WEIGHT_DECREASE_FACTOR,
            "reduced load — RPE came in higher than targeted, even though reps were in range",
        )
    return ProgressionDecision(
        "hold", 1.0,
        "kept the load — reps and RPE matched what this week called for",
    )


def _reference_weight(outcomes: list[SetOutcome], performances_with_weight: list[float]) -> float | None:
    """The weight to base next week's number on: the heaviest logged
    working weight this exercise saw this week."""
    return max(performances_with_weight) if performances_with_weight else None


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

    performances = {s.set_prescription_id: s for s in pe.sets if s.set_prescription_id}
    outcomes = [
        SetOutcome(
            actual_reps=performances[sp.id].actual_reps if sp.id in performances else None,
            actual_rpe=performances[sp.id].actual_rpe if sp.id in performances else None,
        )
        for sp in this_week_prescription.sets
    ]
    logged_weights = [
        performances[sp.id].actual_weight
        for sp in this_week_prescription.sets
        if sp.id in performances and performances[sp.id].actual_weight is not None
    ]
    reference_weight = _reference_weight(outcomes, logged_weights)

    first_set = this_week_prescription.sets[0]
    rep_range_min, rep_range_max = first_set.rep_range_min, first_set.rep_range_max

    if next_week.is_deload and mesocycle.deload_strategy.name == "rest":
        return None  # nothing is trained this week — no recommendation makes sense

    if next_week.is_deload and mesocycle.deload_strategy.name == "reduced_load":
        next_weight = _round_weight(reference_weight * DELOAD_WEIGHT_FACTOR) if reference_weight else None
        reason = "deload week — load reduced to 50% per this mesocycle's reduced_load strategy"
    else:
        decision = decide_progression(outcomes, rep_range_min, rep_range_max, week.target_rpe)
        if decision is None:
            return None
        next_weight = _round_weight(reference_weight * decision.weight_factor) if reference_weight else None
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
            target_weight=next_weight,
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
