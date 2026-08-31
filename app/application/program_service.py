from dataclasses import dataclass

from sqlalchemy.orm import Session, selectinload

from app.domain.program import (
    ExercisePrescription,
    Mesocycle,
    Program,
    SetPrescription,
    TemplateExercise,
    Week,
    WorkoutTemplate,
)
from app.infrastructure.exercise_models import SetTypeModel, TempoModel
from app.infrastructure.program_models import (
    ExercisePrescriptionModel,
    MesocycleModel,
    ProgramModel,
    SetPrescriptionModel,
    TemplateExerciseModel,
    WeekModel,
    WorkoutTemplateModel,
)


def create_program(db: Session, athlete_id: int, name: str, description: str) -> Program:
    row = ProgramModel(athlete_id=athlete_id, name=name, description=description)
    db.add(row)
    db.commit()
    db.refresh(row)
    return Program(id=row.id, athlete_id=row.athlete_id, name=row.name,
                    description=row.description)


@dataclass
class WeekInput:
    week_number: int
    is_deload: bool = False


@dataclass
class WorkoutTemplateInput:
    name: str
    order_in_split: int
    exercise_ids: list[int]  # in workout order


def create_mesocycle(
    db: Session,
    program_id: int,
    name: str,
    weeks: list[WeekInput],
    workout_templates: list[WorkoutTemplateInput],
) -> MesocycleModel:
    """Creates the SHAPE only: the mesocycle, its weeks, its workout
    templates, and each template's exercise slots. No prescriptions yet —
    those get added per (slot, week) via add_prescription, since that's
    where the week-to-week progression actually lives."""
    mesocycle = MesocycleModel(program_id=program_id, name=name)
    db.add(mesocycle)
    db.flush()

    for w in weeks:
        db.add(WeekModel(
            mesocycle_id=mesocycle.id,
            week_number=w.week_number,
            is_deload=w.is_deload,
        ))

    for wt in workout_templates:
        template = WorkoutTemplateModel(
            mesocycle_id=mesocycle.id, name=wt.name, order_in_split=wt.order_in_split
        )
        db.add(template)
        db.flush()

        for position, exercise_id in enumerate(wt.exercise_ids, start=1):
            db.add(TemplateExerciseModel(
                workout_template_id=template.id,
                exercise_id=exercise_id,
                order_in_workout=position,
            ))

    db.commit()
    db.refresh(mesocycle)
    return mesocycle


@dataclass
class SetPrescriptionInput:
    set_type: str
    tempo: str
    rep_range_min: int
    rep_range_max: int
    target_rir: float | None = None


def add_prescription(
    db: Session,
    template_exercise_id: int,
    week_id: int,
    notes: str,
    sets: list[SetPrescriptionInput],
) -> ExercisePrescription:
    set_types_by_name = {s.name: s for s in db.query(SetTypeModel).all()}
    tempos_by_name = {t.name: t for t in db.query(TempoModel).all()}

    prescription = ExercisePrescriptionModel(
        template_exercise_id=template_exercise_id, week_id=week_id, notes=notes
    )
    db.add(prescription)
    db.flush()

    for set_number, s in enumerate(sets, start=1):
        db.add(SetPrescriptionModel(
            exercise_prescription_id=prescription.id,
            set_number=set_number,
            set_type_id=set_types_by_name[s.set_type].id,
            tempo_id=tempos_by_name[s.tempo].id,
            rep_range_min=s.rep_range_min,
            rep_range_max=s.rep_range_max,
            target_rir=s.target_rir,
        ))

    db.commit()
    db.refresh(prescription)
    return _prescription_to_domain(prescription)


def _prescription_to_domain(row: ExercisePrescriptionModel) -> ExercisePrescription:
    return ExercisePrescription(
        id=row.id,
        template_exercise_id=row.template_exercise_id,
        week_id=row.week_id,
        notes=row.notes,
        sets=[
            SetPrescription(
                id=s.id,
                set_number=s.set_number,
                set_type=s.set_type.name,
                tempo=s.tempo.name,
                rep_range_min=s.rep_range_min,
                rep_range_max=s.rep_range_max,
                target_rir=s.target_rir,
            )
            for s in row.sets
        ],
    )


def get_mesocycle(db: Session, mesocycle_id: int) -> MesocycleModel | None:
    return (
        db.query(MesocycleModel)
        .options(
            selectinload(MesocycleModel.weeks),
            selectinload(MesocycleModel.workout_templates)
            .selectinload(WorkoutTemplateModel.exercises)
            .selectinload(TemplateExerciseModel.exercise),
        )
        .filter(MesocycleModel.id == mesocycle_id)
        .first()
    )


def get_week_prescriptions(db: Session, week_id: int) -> list[ExercisePrescription]:
    rows = (
        db.query(ExercisePrescriptionModel)
        .options(
            selectinload(ExercisePrescriptionModel.sets)
            .selectinload(SetPrescriptionModel.set_type),
            selectinload(ExercisePrescriptionModel.sets)
            .selectinload(SetPrescriptionModel.tempo),
        )
        .filter(ExercisePrescriptionModel.week_id == week_id)
        .all()
    )
    return [_prescription_to_domain(row) for row in rows]
