"""
Domain model for the Exercise Library. Plain Python again — see
domain/athlete.py for why.

movement_category, exercise_type, equipment_name, and set/tempo names are
all plain strings here rather than Python enums. They're backed by
reference tables in the database (see infrastructure/exercise_models.py),
specifically so new values are addable with a DB row, not a code change —
hardcoding them as an enum on top of that would defeat the point.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MuscleContribution:
    muscle_name: str
    # How much this exercise trains this muscle, as a fraction of a "full"
    # working set for that muscle: 1.0 = primary mover, 0.5 = trained at
    # roughly half that degree, etc. This is a modeling choice (an
    # algorithmic design decision per the constitution's fitness-science
    # honesty section), not a precisely measured physiological quantity —
    # it exists to support future per-muscle volume calculations.
    contribution: float


@dataclass
class Exercise:
    """A library exercise — not a template, not a prescription, not a
    performed set. Those are separate future concepts per the constitution's
    domain hierarchy (§2). Notably: no rep range here — that's a property
    of how an exercise is PRESCRIBED in a specific mesocycle, not of the
    exercise itself, so it belongs on the future Set Prescription entity."""

    id: int | None
    name: str
    description: str
    equipment_name: str
    movement_category: str
    exercise_type: str
    is_warmup_suitable: bool
    notes: str
    muscles: list[MuscleContribution] = field(default_factory=list)
    supported_set_types: list[str] = field(default_factory=list)
    supported_tempos: list[str] = field(default_factory=list)
