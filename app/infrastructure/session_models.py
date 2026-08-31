"""
SQLAlchemy ORM models for WorkoutSession -> PerformedExercise ->
SetPerformance — the performed side, paired against the planning
hierarchy in mesocycle_models.py.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.infrastructure.exercise_models import ExerciseModel, SetTypeModel, TempoModel
from app.infrastructure.mesocycle_models import (
    MesocycleModel,
    SetPrescriptionModel,
    TemplateExerciseModel,
    WeekModel,
    WorkoutTemplateModel,
)


class WorkoutSessionModel(Base):
    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    mesocycle_id: Mapped[int] = mapped_column(ForeignKey("mesocycles.id"))
    week_id: Mapped[int] = mapped_column(ForeignKey("weeks.id"))
    workout_template_id: Mapped[int] = mapped_column(ForeignKey("workout_templates.id"))
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    mesocycle: Mapped[MesocycleModel] = relationship()
    week: Mapped[WeekModel] = relationship()
    workout_template: Mapped[WorkoutTemplateModel] = relationship()
    performed_exercises: Mapped[list["PerformedExerciseModel"]] = relationship(
        back_populates="workout_session", cascade="all, delete-orphan",
        order_by="PerformedExerciseModel.order_performed",
    )


class PerformedExerciseModel(Base):
    __tablename__ = "performed_exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id"))
    # Nullable: an exercise added on the fly with no corresponding plan slot.
    template_exercise_id: Mapped[int | None] = mapped_column(
        ForeignKey("template_exercises.id"), nullable=True
    )
    # The exercise ACTUALLY performed — may differ from the template
    # slot's planned exercise (a swap), which is why this is its own FK
    # rather than just following template_exercise.exercise_id.
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    order_performed: Mapped[int] = mapped_column(Integer)

    workout_session: Mapped[WorkoutSessionModel] = relationship(
        back_populates="performed_exercises"
    )
    template_exercise: Mapped[TemplateExerciseModel | None] = relationship()
    exercise: Mapped[ExerciseModel] = relationship()
    sets: Mapped[list["SetPerformanceModel"]] = relationship(
        back_populates="performed_exercise", cascade="all, delete-orphan",
        order_by="SetPerformanceModel.set_number",
    )


class SetPerformanceModel(Base):
    __tablename__ = "set_performances"

    id: Mapped[int] = mapped_column(primary_key=True)
    performed_exercise_id: Mapped[int] = mapped_column(
        ForeignKey("performed_exercises.id")
    )
    # Nullable: an added set with no prescription behind it.
    set_prescription_id: Mapped[int | None] = mapped_column(
        ForeignKey("set_prescriptions.id"), nullable=True
    )
    set_number: Mapped[int] = mapped_column(Integer)
    set_type_id: Mapped[int] = mapped_column(ForeignKey("set_types.id"))
    tempo_id: Mapped[int] = mapped_column(ForeignKey("tempos.id"))
    actual_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    partial_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_rir: Mapped[float | None] = mapped_column(Float, nullable=True)

    performed_exercise: Mapped[PerformedExerciseModel] = relationship(
        back_populates="sets"
    )
    set_prescription: Mapped[SetPrescriptionModel | None] = relationship()
    set_type: Mapped[SetTypeModel] = relationship()
    tempo: Mapped[TempoModel] = relationship()
