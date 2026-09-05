"""
SQLAlchemy ORM models for the planning hierarchy: Program -> Mesocycle ->
Week / WorkoutTemplate -> TemplateExercise -> ExercisePrescription ->
SetPrescription.

set_type and tempo on SetPrescriptionModel are FKs into the same
set_types/tempos reference tables the exercise library uses — a
prescribed set type has to be one of the real, known set types, same as
a library exercise's supported set types.
"""

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.infrastructure.exercise_models import ExerciseModel, SetTypeModel, TempoModel
from app.infrastructure.models import AthleteModel


class ProgramModel(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")

    athlete: Mapped[AthleteModel] = relationship()
    mesocycles: Mapped[list["MesocycleModel"]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )


class MesocycleModel(Base):
    __tablename__ = "mesocycles"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"))
    name: Mapped[str] = mapped_column(String(200))

    program: Mapped[ProgramModel] = relationship(back_populates="mesocycles")
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
    target_rir: Mapped[float | None] = mapped_column(Float, nullable=True)

    exercise_prescription: Mapped[ExercisePrescriptionModel] = relationship(
        back_populates="sets"
    )
    set_type: Mapped[SetTypeModel] = relationship()
    tempo: Mapped[TempoModel] = relationship()
