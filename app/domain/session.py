"""
Domain model for the PERFORMED side of the hierarchy — what actually
happened, as distinct from Exercise Prescription / Set Prescription
(what was planned). This is the pairing the constitution calls the app's
core differentiator: comparing expected vs. actual, not just logging.

A PerformedExercise's exercise_id can differ from its template_exercise's
planned exercise (an exercise swap) — the schema allows this for free,
even though no dedicated "swap" workflow is built yet. Likewise a
SetPerformance's set_prescription_id can be None (an added/extra set with
no plan behind it) without breaking anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class WorkoutSessionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class SetPerformance:
    id: int | None
    set_prescription_id: int | None  # None = an added set with no plan behind it
    set_number: int
    set_type: str
    tempo: str
    actual_weight: float | None
    actual_reps: int | None
    partial_reps: int | None
    actual_rir: float | None


@dataclass
class PerformedExercise:
    id: int | None
    workout_session_id: int
    template_exercise_id: int | None  # None = an exercise not in the plan at all
    exercise_id: int
    exercise_name: str
    order_performed: int
    sets: list[SetPerformance] = field(default_factory=list)


@dataclass
class WorkoutSession:
    id: int | None
    mesocycle_id: int
    week_id: int
    workout_template_id: int
    status: WorkoutSessionStatus
    started_at: datetime
    completed_at: datetime | None
    performed_exercises: list[PerformedExercise] = field(default_factory=list)
