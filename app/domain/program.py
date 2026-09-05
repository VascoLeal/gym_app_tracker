"""
Domain model for the planning side of the hierarchy: Program down through
Set Prescription. Deliberately does NOT include anything about what
actually happened in a workout (Workout Session, Set Performance) — that's
a separate future milestone, per the constitution's domain hierarchy (§2).

Kept as flat, mostly-independent classes rather than deeply nested trees:
there's no real business logic here yet (that's the progression engine's
job, later), so this is closer to structural data than behavior. Nesting
happens where the application layer assembles a response, not by
embedding children by default in every one of these.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Program:
    id: int | None
    athlete_id: int
    name: str
    description: str


@dataclass
class Mesocycle:
    id: int | None
    program_id: int
    name: str


@dataclass
class Week:
    id: int | None
    mesocycle_id: int
    week_number: int
    is_deload: bool


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
    exercise prescription as a whole — see program_service for why."""

    id: int | None
    set_number: int
    set_type: str
    tempo: str
    rep_range_min: int
    rep_range_max: int
    target_rir: float | None


@dataclass
class ExercisePrescription:
    """The week-specific NUMBERS for one TemplateExercise slot."""

    id: int | None
    template_exercise_id: int
    week_id: int
    notes: str
    sets: list[SetPrescription] = field(default_factory=list)
