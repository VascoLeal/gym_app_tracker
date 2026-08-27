"""
Domain model for an Athlete.

This is deliberately plain Python — no SQLAlchemy, no Pydantic, no FastAPI.
That's the point of the "domain" layer per the project constitution: the
core business object should be understandable and testable in complete
isolation from how it's stored (infrastructure/) or how it's exposed over
HTTP (api/).

Later, this is where progression-engine logic like `recommend_next_set(...)`
will live, operating on plain objects like this one.
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
