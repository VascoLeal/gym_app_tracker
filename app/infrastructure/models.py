"""
SQLAlchemy ORM models — the persistence-layer shape of our data. This is
deliberately a *different* class from app.domain.athlete.Athlete: this one
knows about database columns and constraints; that one knows about business
rules. See architecture-discovery.md §2.2 for why we're not using SQLModel
to merge the two.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class AthleteModel(Base):
    __tablename__ = "athletes"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
