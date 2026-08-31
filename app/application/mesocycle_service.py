from dataclasses import dataclass

from sqlalchemy.orm import Session, selectinload

from app.domain.mesocycle import (
    ExercisePrescription,
    MesocycleStatus,
    SetPrescription,
)
from app.infrastructure.exercise_models import SetTypeModel, TempoModel
from app.infrastructure.mesocycle_models import (
    DeloadStrategyModel,
    ExercisePrescriptionModel,
    MesocycleModel,
    SetPrescriptionModel,
    TemplateExerciseModel,
    WeekModel,
    WorkoutTemplateModel,
)

MIN_WEEKS = 4
MAX_WEEKS = 12


class InvalidMesocycleLength(Exception):
    pass


class AthleteAlreadyHasActiveMesocycle(Exception):
    pass


class MesocycleNotFound(Exception):
    pass


@dataclass
class WorkoutTemplateInput:
    name: str
    order_in_split: int
    exercise_ids: list[int]  # in workout order


def _assert_no_active_mesocycle(db: Session, athlete_id: int) -> None:
    existing = (
        db.query(MesocycleModel)
        .filter(
            MesocycleModel.athlete_id == athlete_id,
            MesocycleModel.status == MesocycleStatus.ACTIVE.value,
        )
        .first()
    )
    if existing is not None:
        raise AthleteAlreadyHasActiveMesocycle(existing.id)


def create_mesocycle(
    db: Session,
    athlete_id: int,
    name: str,
    number_of_weeks: int,
    deload_strategy_name: str,
    workout_templates: list[WorkoutTemplateInput],
) -> MesocycleModel:
    """Creates a new ACTIVE mesocycle: auto-generates its weeks (last one
    is always the deload week — not something the caller specifies per
    week), plus its workout templates and exercise slots. Enforces that
    the athlete doesn't already have another mesocycle in progress."""
    if not (MIN_WEEKS <= number_of_weeks <= MAX_WEEKS):
        raise InvalidMesocycleLength(number_of_weeks)

    _assert_no_active_mesocycle(db, athlete_id)

    strategy = (
        db.query(DeloadStrategyModel)
        .filter(DeloadStrategyModel.name == deload_strategy_name)
        .first()
    )
    if strategy is None:
        raise ValueError(f"Unknown deload strategy: {deload_strategy_name}")

    mesocycle = MesocycleModel(
        athlete_id=athlete_id,
        name=name,
        number_of_weeks=number_of_weeks,
        deload_strategy_id=strategy.id,
        status=MesocycleStatus.ACTIVE.value,
        sessions_completed=0,
    )
    db.add(mesocycle)
    db.flush()

    for week_number in range(1, number_of_weeks + 1):
        db.add(WeekModel(
            mesocycle_id=mesocycle.id,
            week_number=week_number,
            is_deload=(week_number == number_of_weeks),
        ))

    _create_workout_templates(db, mesocycle.id, workout_templates)

    db.commit()
    db.refresh(mesocycle)
    return mesocycle


def _create_workout_templates(
    db: Session, mesocycle_id: int, workout_templates: list[WorkoutTemplateInput]
) -> None:
    for wt in workout_templates:
        template = WorkoutTemplateModel(
            mesocycle_id=mesocycle_id, name=wt.name, order_in_split=wt.order_in_split
        )
        db.add(template)
        db.flush()

        for position, exercise_id in enumerate(wt.exercise_ids, start=1):
            db.add(TemplateExerciseModel(
                workout_template_id=template.id,
                exercise_id=exercise_id,
                order_in_workout=position,
            ))


def stop_mesocycle(db: Session, mesocycle_id: int, keep_as_history: bool) -> None:
    """keep_as_history=True marks it ABANDONED (visible in history, per the
    athlete's choice); False deletes it outright. Which one happens is a
    decision the frontend asks the athlete for each time — this function
    just executes whichever they picked."""
    mesocycle = db.query(MesocycleModel).filter(MesocycleModel.id == mesocycle_id).first()
    if mesocycle is None:
        raise MesocycleNotFound(mesocycle_id)

    if keep_as_history:
        mesocycle.status = MesocycleStatus.ABANDONED.value
        db.commit()
    else:
        db.delete(mesocycle)
        db.commit()


def copy_mesocycle(db: Session, source_mesocycle_id: int, new_name: str) -> MesocycleModel:
    """Duplicates a mesocycle's SHAPE (weeks, workout templates, exercise
    slots) into a brand new active mesocycle for the same athlete.
    Deliberately does NOT copy prescriptions — starting numbers adjusted
    from the previous mesocycle's performance is progression-engine work,
    not built yet. The exercise selection can be edited afterward via the
    normal template-exercise operations."""
    source = get_mesocycle(db, source_mesocycle_id)
    if source is None:
        raise MesocycleNotFound(source_mesocycle_id)

    strategy_name = source.deload_strategy.name
    templates = [
        WorkoutTemplateInput(
            name=t.name,
            order_in_split=t.order_in_split,
            exercise_ids=[te.exercise_id for te in t.exercises],
        )
        for t in source.workout_templates
    ]

    return create_mesocycle(
        db,
        athlete_id=source.athlete_id,
        name=new_name,
        number_of_weeks=source.number_of_weeks,
        deload_strategy_name=strategy_name,
        workout_templates=templates,
    )


def get_mesocycle(db: Session, mesocycle_id: int) -> MesocycleModel | None:
    return (
        db.query(MesocycleModel)
        .options(
            selectinload(MesocycleModel.deload_strategy),
            selectinload(MesocycleModel.weeks),
            selectinload(MesocycleModel.workout_templates)
            .selectinload(WorkoutTemplateModel.exercises)
            .selectinload(TemplateExerciseModel.exercise),
        )
        .filter(MesocycleModel.id == mesocycle_id)
        .first()
    )


def list_athlete_mesocycles(db: Session, athlete_id: int) -> list[MesocycleModel]:
    return (
        db.query(MesocycleModel)
        .filter(MesocycleModel.athlete_id == athlete_id)
        .order_by(MesocycleModel.id.desc())
        .all()
    )


def current_position(mesocycle: MesocycleModel) -> tuple[int, WorkoutTemplateModel | None]:
    """Derives (current_week_number, next_workout_template) from
    sessions_completed — see domain/mesocycle.py module docstring for why
    this is session-count-based rather than calendar-based. Returns
    (number_of_weeks, None) once the mesocycle's total sessions are done."""
    training_days_per_week = len(mesocycle.workout_templates)
    if training_days_per_week == 0:
        return 1, None

    total_sessions = mesocycle.number_of_weeks * training_days_per_week
    if mesocycle.sessions_completed >= total_sessions:
        return mesocycle.number_of_weeks, None

    current_week_number = mesocycle.sessions_completed // training_days_per_week + 1
    next_template_index = mesocycle.sessions_completed % training_days_per_week
    next_template = mesocycle.workout_templates[next_template_index]
    return current_week_number, next_template


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
