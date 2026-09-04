"""
SQLAlchemy ORM models: Mesocycle (athlete-owned, no Program layer) down
through SetPrescription.

deload_strategy is a reference table (like set_types/tempos/etc.) because
it's genuinely expected to grow — the author already flagged wanting a
future "prehab exercises" option alongside rest/reduced_load. status is
a plain validated string, NOT a reference table: every new status value
would require new application code to handle its transitions anyway, so
a table wouldn't buy the same code-free extensibility it does for content
like equipment or set types.
"""

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.infrastructure.exercise_models import ExerciseModel, SetTypeModel, TempoModel
from app.infrastructure.models import AthleteModel


class DeloadStrategyModel(Base):
    __tablename__ = "deload_strategies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


class MesocycleModel(Base):
    __tablename__ = "mesocycles"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    name: Mapped[str] = mapped_column(String(200))
    number_of_weeks: Mapped[int] = mapped_column(Integer)
    deload_strategy_id: Mapped[int] = mapped_column(ForeignKey("deload_strategies.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")
    sessions_completed: Mapped[int] = mapped_column(Integer, default=0)

    athlete: Mapped[AthleteModel] = relationship()
    deload_strategy: Mapped[DeloadStrategyModel] = relationship()
    weeks: Mapped[list["WeekModel"]] = relationship(
        back_populates="mesocycle", cascade="all, delete-orphan",
        order_by="WeekModel.week_number",
    )
    workout_templates: Mapped[list["WorkoutTemplateModel"]] = relationship(
        back_populates="mesocycle", cascade="all, delete-orphan",
        order_by="WorkoutTemplateModel.order_in_split",
    )


class WeekModel(Base):
    __tablename__ = "weeks"
    __table_args__ = (UniqueConstraint("mesocycle_id", "week_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mesocycle_id: Mapped[int] = mapped_column(ForeignKey("mesocycles.id"))
    week_number: Mapped[int] = mapped_column(Integer)
    is_deload: Mapped[bool] = mapped_column(default=False)
    target_rpe: Mapped[float | None] = mapped_column(Float, nullable=True)

    mesocycle: Mapped[MesocycleModel] = relationship(back_populates="weeks")


class WorkoutTemplateModel(Base):
    __tablename__ = "workout_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    mesocycle_id: Mapped[int] = mapped_column(ForeignKey("mesocycles.id"))
    name: Mapped[str] = mapped_column(String(200))
    order_in_split: Mapped[int] = mapped_column(Integer)

    mesocycle: Mapped[MesocycleModel] = relationship(
        back_populates="workout_templates"
    )
    exercises: Mapped[list["TemplateExerciseModel"]] = relationship(
        back_populates="workout_template", cascade="all, delete-orphan",
        order_by="TemplateExerciseModel.order_in_workout",
    )


class TemplateExerciseModel(Base):
    __tablename__ = "template_exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_template_id: Mapped[int] = mapped_column(
        ForeignKey("workout_templates.id")
    )
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    order_in_workout: Mapped[int] = mapped_column(Integer)

    workout_template: Mapped[WorkoutTemplateModel] = relationship(
        back_populates="exercises"
    )
    exercise: Mapped[ExerciseModel] = relationship()


class ExercisePrescriptionModel(Base):
    __tablename__ = "exercise_prescriptions"
    __table_args__ = (UniqueConstraint("template_exercise_id", "week_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_exercise_id: Mapped[int] = mapped_column(
        ForeignKey("template_exercises.id")
    )
    week_id: Mapped[int] = mapped_column(ForeignKey("weeks.id"))
    notes: Mapped[str] = mapped_column(Text, default="")

    template_exercise: Mapped[TemplateExerciseModel] = relationship()
    week: Mapped[WeekModel] = relationship()
    sets: Mapped[list["SetPrescriptionModel"]] = relationship(
        back_populates="exercise_prescription", cascade="all, delete-orphan",
        order_by="SetPrescriptionModel.set_number",
    )


class SetPrescriptionModel(Base):
    __tablename__ = "set_prescriptions"
    __table_args__ = (UniqueConstraint("exercise_prescription_id", "set_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_prescription_id: Mapped[int] = mapped_column(
        ForeignKey("exercise_prescriptions.id")
    )
    set_number: Mapped[int] = mapped_column(Integer)
    set_type_id: Mapped[int] = mapped_column(ForeignKey("set_types.id"))
    tempo_id: Mapped[int] = mapped_column(ForeignKey("tempos.id"))
    rep_range_min: Mapped[int] = mapped_column(Integer)
    rep_range_max: Mapped[int] = mapped_column(Integer)
    target_weight: Mapped[float | None] = mapped_column(Float, nullable=True)

    exercise_prescription: Mapped[ExercisePrescriptionModel] = relationship(
        back_populates="sets"
    )
    set_type: Mapped[SetTypeModel] = relationship()
    tempo: Mapped[TempoModel] = relationship()
