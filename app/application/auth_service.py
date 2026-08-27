"""
Orchestrates registration and login: hashing/verifying passwords (argon2id,
per the constitution's security baseline) and translating between the ORM
model (infrastructure) and the domain object (domain.athlete.Athlete).

Deliberately NOT doing session/JWT token issuance here — that's the Auth
milestone's job (see project-brief.md §2 and §3). This milestone only
proves: password gets hashed, athlete gets stored, login can verify it.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.orm import Session

from app.domain.athlete import Athlete
from app.infrastructure.models import AthleteModel

_hasher = PasswordHasher()


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


def _to_domain(row: AthleteModel) -> Athlete:
    return Athlete(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        created_at=row.created_at,
    )


def register_athlete(db: Session, email: str, password: str) -> Athlete:
    email = email.strip().lower()

    existing = db.query(AthleteModel).filter_by(email=email).first()
    if existing is not None:
        raise EmailAlreadyRegistered(email)

    row = AthleteModel(email=email, password_hash=_hasher.hash(password))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_domain(row)


def authenticate_athlete(db: Session, email: str, password: str) -> Athlete:
    email = email.strip().lower()
    row = db.query(AthleteModel).filter_by(email=email).first()

    if row is None:
        # Deliberately the same error as a wrong password (below) — never
        # reveal whether an email is registered via a different message.
        raise InvalidCredentials()

    try:
        _hasher.verify(row.password_hash, password)
    except VerifyMismatchError as exc:
        raise InvalidCredentials() from exc

    return _to_domain(row)
