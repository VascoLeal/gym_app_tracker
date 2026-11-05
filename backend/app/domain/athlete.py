"""
Domain model for an Athlete.

This is deliberately plain Python — no SQLAlchemy, no Pydantic, no FastAPI.
That's the point of the "domain" layer per the project constitution: the
core business object should be understandable and testable in complete
isolation from how it's stored (infrastructure/) or how it's exposed over
HTTP (api/).

Note this translation is deliberately NOT applied everywhere — see
docs/project-brief.md's decisions log (2026-09-15) for why auth_service and
exercise_service translate ORM rows to domain objects like this one, while
mesocycle_service/session_service stay ORM-native. The progression engine's
actual decision logic (application/progression_service.decide_progression)
is still independently unit-testable without a database, per the
constitution's requirement — it just doesn't operate on dataclasses from
this domain/ package.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Athlete:
    """A person using the app to train (you or your girlfriend)."""

    id: int | None  # None until persisted and assigned a real DB id
    email: str
    password_hash: str
    created_at: datetime

    def __post_init__(self) -> None:
        # A cheap domain invariant: emails are always compared/stored
        # lower-case, so "Foo@Bar.com" and "foo@bar.com" are the same
        # athlete. This is exactly the kind of rule that belongs HERE,
        # not scattered across API route handlers.
        self.email = self.email.strip().lower()
