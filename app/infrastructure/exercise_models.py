"""
SQLAlchemy ORM models for the exercise library.

Muscle, Equipment, SetType, Tempo, MovementCategory, and ExerciseType are
ALL reference tables now (not Python enums) — see project-brief.md's
decisions log for why movement_category/exercise_type moved from enums to
tables. The pattern is now uniform: every one of these grows by adding a
row, never by shipping code.
"""

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class MuscleModel(Base):
    __tablename__ = "muscles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    # Coarser grouping for display/filtering (e.g. "Chest" groups
    # "Upper Chest" / "Mid Chest" / "Lower Chest") without losing the
    # granular row each muscle needs for contribution-weighting.
    muscle_group: Mapped[str] = mapped_column(String(100))


class EquipmentModel(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class SetTypeModel(Base):
    __tablename__ = "set_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


class TempoModel(Base):
    __tablename__ = "tempos"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


class MovementCategoryModel(Base):
    __tablename__ = "movement_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


class ExerciseTypeModel(Base):
    __tablename__ = "exercise_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


class ExerciseModel(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"))
    movement_category_id: Mapped[int] = mapped_column(
        ForeignKey("movement_categories.id")
    )
    exercise_type_id: Mapped[int] = mapped_column(ForeignKey("exercise_types.id"))
    is_warmup_suitable: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str] = mapped_column(Text, default="")

    equipment: Mapped[EquipmentModel] = relationship()
    movement_category: Mapped[MovementCategoryModel] = relationship()
    exercise_type: Mapped[ExerciseTypeModel] = relationship()
    muscle_links: Mapped[list["ExerciseMuscleModel"]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan"
    )
    set_type_links: Mapped[list["ExerciseSetTypeModel"]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan"
    )
    tempo_links: Mapped[list["ExerciseTempoModel"]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan"
    )


class ExerciseMuscleModel(Base):
    """Many-to-many Exercise<->Muscle, carrying a numeric contribution
    weight rather than a primary/secondary category — see domain/exercise.py."""

    __tablename__ = "exercise_muscles"
    __table_args__ = (UniqueConstraint("exercise_id", "muscle_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    muscle_id: Mapped[int] = mapped_column(ForeignKey("muscles.id"))
    contribution: Mapped[float] = mapped_column(Float)

    exercise: Mapped[ExerciseModel] = relationship(back_populates="muscle_links")
    muscle: Mapped[MuscleModel] = relationship()


class ExerciseSetTypeModel(Base):
    """Many-to-many Exercise<->SetType: which set structures suit this exercise."""

    __tablename__ = "exercise_set_types"
    __table_args__ = (UniqueConstraint("exercise_id", "set_type_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    set_type_id: Mapped[int] = mapped_column(ForeignKey("set_types.id"))

    exercise: Mapped[ExerciseModel] = relationship(back_populates="set_type_links")
    set_type: Mapped[SetTypeModel] = relationship()


class ExerciseTempoModel(Base):
    """Many-to-many Exercise<->Tempo: which tempos suit this exercise."""

    __tablename__ = "exercise_tempos"
    __table_args__ = (UniqueConstraint("exercise_id", "tempo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    tempo_id: Mapped[int] = mapped_column(ForeignKey("tempos.id"))

    exercise: Mapped[ExerciseModel] = relationship(back_populates="tempo_links")
    tempo: Mapped[TempoModel] = relationship()
