"""
Domain model for Mesocycle down through Set Prescription. No Program layer
— mesocycles belong directly to the athlete (decided 2026-08-29, see
project-brief.md decisions log).

"Week" here is NOT a calendar concept. It's derived from how many training
days the athlete has actually completed since the mesocycle started
(sessions_completed), divided by how many training days per week this
mesocycle has (the number of workout templates). Skipping a day just
delays the derived week boundary — it doesn't create a gap. See
mesocycle_service.current_position() for the actual math.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MesocycleStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class Mesocycle:
    id: int | None
    athlete_id: int
    name: str
    number_of_weeks: int  # 4-12; last week is always the deload week
    deload_strategy: str  # "rest" | "reduced_load" (table-backed, see infra)
    status: MesocycleStatus
    sessions_completed: int = 0


@dataclass
class Week:
    id: int | None
    mesocycle_id: int
    week_number: int
    is_deload: bool
    target_rpe: float | None  # computed at creation, not entered — see mesocycle_service


@dataclass
class WorkoutTemplate:
    id: int | None
    mesocycle_id: int
    name: str
    order_in_split: int


@dataclass
class TemplateExercise:
    """One exercise slot within a WorkoutTemplate — the SHAPE (which
    exercise, what order), reused unchanged across every week."""

    id: int | None
    workout_template_id: int
    exercise_id: int
    exercise_name: str
    order_in_workout: int


@dataclass
class SetPrescription:
    """One planned set. set_type and tempo live HERE, per-set, not on the
    exercise prescription as a whole. target_rpe is NOT stored here — it's
    computed at the Week level (every exercise that week shares the same
    target) and surfaced onto each set only when assembling an API
    response, for convenience."""

    id: int | None
    set_number: int
    set_type: str
    tempo: str
    rep_range_min: int
    rep_range_max: int
    target_rpe: float | None = None


@dataclass
class ExercisePrescription:
    """The week-specific NUMBERS for one TemplateExercise slot."""

    id: int | None
    template_exercise_id: int
    week_id: int
    notes: str
    sets: list[SetPrescription] = field(default_factory=list)
