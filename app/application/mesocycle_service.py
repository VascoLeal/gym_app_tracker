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


class MesocycleAlreadyStarted(Exception):
    pass


class MesocycleStillActive(Exception):
    pass


class TemplateExerciseNotFound(Exception):
    pass


class SetPrescriptionNotFound(Exception):
    pass


class ExercisePrescriptionNotFound(Exception):
    pass


@dataclass
class WorkoutTemplateInput:
    name: str
    order_in_split: int
    exercise_ids: list[int]  # in workout order


def compute_week_target_rpes(
    number_of_weeks: int, deload_strategy_name: str
) -> dict[int, float | None]:
    """Maps week_number -> target RPE. Non-deload weeks get a linear ramp
    from 7 (week 1) to 10 (the last non-deload week), rounded to the
    nearest whole number. A "rest" deload week gets no target at all
    (nothing is trained). A "reduced_load" deload week also gets no
    target — its whole point is training lighter, not chasing intensity,
    so a target RPE would work against that (author's design call was
    open on this specific case; this is the recommended default).
    "none" means there's no deload week, so every week is part of the ramp.
    """
    has_deload_week = deload_strategy_name in ("rest", "reduced_load")
    non_deload_weeks = number_of_weeks - 1 if has_deload_week else number_of_weeks

    targets: dict[int, float | None] = {}
    for week_number in range(1, non_deload_weeks + 1):
        week_index = week_number - 1
        if non_deload_weeks == 1:
            rpe = 10.0
        else:
            rpe = 7 + 3 * week_index / (non_deload_weeks - 1)
        targets[week_number] = float(round(rpe))

    if has_deload_week:
        targets[number_of_weeks] = None

    return targets


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

    target_rpes = compute_week_target_rpes(number_of_weeks, deload_strategy_name)
    for week_number in range(1, number_of_weeks + 1):
        db.add(WeekModel(
            mesocycle_id=mesocycle.id,
            week_number=week_number,
            is_deload=(
                deload_strategy_name in ("rest", "reduced_load")
                and week_number == number_of_weeks
            ),
            target_rpe=target_rpes[week_number],
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


def _assert_not_started(mesocycle: MesocycleModel) -> None:
    """Exercise selection is supposed to stay fixed for the whole
    mesocycle (per the author's own design principle) — so editing it is
    only allowed before any session has been logged against it, not
    mid-block."""
    if mesocycle.sessions_completed > 0:
        raise MesocycleAlreadyStarted(mesocycle.id)


def edit_template_exercise(db: Session, template_exercise_id: int, exercise_id: int) -> TemplateExerciseModel:
    template_exercise = (
        db.query(TemplateExerciseModel)
        .join(WorkoutTemplateModel)
        .join(MesocycleModel)
        .filter(TemplateExerciseModel.id == template_exercise_id)
        .first()
    )
    if template_exercise is None:
        raise TemplateExerciseNotFound(template_exercise_id)

    _assert_not_started(template_exercise.workout_template.mesocycle)

    template_exercise.exercise_id = exercise_id
    db.commit()
    db.refresh(template_exercise)
    return template_exercise


def add_template_exercise(db: Session, workout_template_id: int, exercise_id: int) -> TemplateExerciseModel:
    template = (
        db.query(WorkoutTemplateModel)
        .filter(WorkoutTemplateModel.id == workout_template_id)
        .first()
    )
    if template is None:
        raise MesocycleNotFound(workout_template_id)

    _assert_not_started(template.mesocycle)

    next_position = len(template.exercises) + 1
    template_exercise = TemplateExerciseModel(
        workout_template_id=workout_template_id,
        exercise_id=exercise_id,
        order_in_workout=next_position,
    )
    db.add(template_exercise)
    db.commit()
    db.refresh(template_exercise)
    return template_exercise


def remove_template_exercise(db: Session, template_exercise_id: int) -> None:
    template_exercise = (
        db.query(TemplateExerciseModel)
        .filter(TemplateExerciseModel.id == template_exercise_id)
        .first()
    )
    if template_exercise is None:
        raise TemplateExerciseNotFound(template_exercise_id)

    template = template_exercise.workout_template
    _assert_not_started(template.mesocycle)

    db.delete(template_exercise)
    db.flush()

    # Renumber remaining slots so order_in_workout stays contiguous.
    remaining = (
        db.query(TemplateExerciseModel)
        .filter(TemplateExerciseModel.workout_template_id == template.id)
        .order_by(TemplateExerciseModel.order_in_workout)
        .all()
    )
    for position, te in enumerate(remaining, start=1):
        te.order_in_workout = position

    db.commit()


def reorder_template_exercise(
    db: Session, template_exercise_id: int, new_position: int
) -> list[TemplateExerciseModel]:
    """Moves one exercise slot to a new position within its workout
    template, shifting everything else to keep a contiguous 1..N
    ordering. Same "not after the mesocycle has started" restriction as
    the other exercise-selection edits — changing exercise ORDER still
    changes fatigue/ordering dynamics mid-block, which the fixed-shape
    principle is meant to protect against. Returns the whole template's
    exercises in their new order."""
    template_exercise = (
        db.query(TemplateExerciseModel)
        .filter(TemplateExerciseModel.id == template_exercise_id)
        .first()
    )
    if template_exercise is None:
        raise TemplateExerciseNotFound(template_exercise_id)

    template = template_exercise.workout_template
    _assert_not_started(template.mesocycle)

    exercises = sorted(template.exercises, key=lambda te: te.order_in_workout)
    exercises.remove(template_exercise)
    clamped_position = max(1, min(new_position, len(exercises) + 1))
    exercises.insert(clamped_position - 1, template_exercise)

    for position, te in enumerate(exercises, start=1):
        te.order_in_workout = position

    db.commit()
    for te in exercises:
        db.refresh(te)
    return exercises


def add_set_to_prescription(
    db: Session, exercise_prescription_id: int, set_input: "SetPrescriptionInput"
) -> SetPrescriptionModel:
    """Adds one more planned set to an existing prescription — the "edit
    number of sets" the author asked for. Not restricted to before the
    mesocycle starts: unlike exercise selection, tweaking a specific
    week's set count doesn't violate the "shape stays fixed" principle,
    since each week already has its own independent prescription."""
    prescription = (
        db.query(ExercisePrescriptionModel)
        .filter(ExercisePrescriptionModel.id == exercise_prescription_id)
        .first()
    )
    if prescription is None:
        raise ExercisePrescriptionNotFound(exercise_prescription_id)

    set_types_by_name = {s.name: s for s in db.query(SetTypeModel).all()}
    tempos_by_name = {t.name: t for t in db.query(TempoModel).all()}
    next_set_number = len(prescription.sets) + 1

    new_set = SetPrescriptionModel(
        exercise_prescription_id=exercise_prescription_id,
        set_number=next_set_number,
        set_type_id=set_types_by_name[set_input.set_type].id,
        tempo_id=tempos_by_name[set_input.tempo].id,
        rep_range_min=set_input.rep_range_min,
        rep_range_max=set_input.rep_range_max,
        target_weight=set_input.target_weight,
    )
    db.add(new_set)
    db.commit()
    db.refresh(new_set)
    return new_set


def remove_set_from_prescription(db: Session, set_prescription_id: int) -> None:
    set_prescription = (
        db.query(SetPrescriptionModel)
        .filter(SetPrescriptionModel.id == set_prescription_id)
        .first()
    )
    if set_prescription is None:
        raise SetPrescriptionNotFound(set_prescription_id)

    exercise_prescription_id = set_prescription.exercise_prescription_id
    db.delete(set_prescription)
    db.flush()

    remaining = (
        db.query(SetPrescriptionModel)
        .filter(SetPrescriptionModel.exercise_prescription_id == exercise_prescription_id)
        .order_by(SetPrescriptionModel.set_number)
        .all()
    )
    for position, sp in enumerate(remaining, start=1):
        sp.set_number = position

    db.commit()


def edit_set_in_prescription(
    db: Session,
    set_prescription_id: int,
    set_type: str | None = None,
    tempo: str | None = None,
    rep_range_min: int | None = None,
    rep_range_max: int | None = None,
    target_weight: float | None = None,
    clear_target_weight: bool = False,
) -> SetPrescriptionModel:
    """Edits an existing set's own fields in place. Any argument left as
    None is unchanged, EXCEPT target_weight — since None is a legitimate
    value there (no recommendation), clear_target_weight explicitly opts
    into clearing it rather than overloading None to mean "don't touch"."""
    set_prescription = (
        db.query(SetPrescriptionModel)
        .filter(SetPrescriptionModel.id == set_prescription_id)
        .first()
    )
    if set_prescription is None:
        raise SetPrescriptionNotFound(set_prescription_id)

    if set_type is not None:
        set_type_row = db.query(SetTypeModel).filter(SetTypeModel.name == set_type).first()
        set_prescription.set_type_id = set_type_row.id
    if tempo is not None:
        tempo_row = db.query(TempoModel).filter(TempoModel.name == tempo).first()
        set_prescription.tempo_id = tempo_row.id
    if rep_range_min is not None:
        set_prescription.rep_range_min = rep_range_min
    if rep_range_max is not None:
        set_prescription.rep_range_max = rep_range_max
    if clear_target_weight:
        set_prescription.target_weight = None
    elif target_weight is not None:
        set_prescription.target_weight = target_weight

    db.commit()
    db.refresh(set_prescription)
    return set_prescription


def delete_mesocycle(db: Session, mesocycle_id: int) -> None:
    """Removes a mesocycle from history. Only for non-active ones —
    an active mesocycle must be stopped first (via stop_mesocycle), since
    deleting an in-progress block outright is more likely to be a mistake
    than an intentional action."""
    mesocycle = db.query(MesocycleModel).filter(MesocycleModel.id == mesocycle_id).first()
    if mesocycle is None:
        raise MesocycleNotFound(mesocycle_id)
    if mesocycle.status == MesocycleStatus.ACTIVE.value:
        raise MesocycleStillActive(mesocycle_id)

    db.delete(mesocycle)
    db.commit()


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


def total_required_sessions(mesocycle: MesocycleModel) -> int:
    """How many sessions this mesocycle needs before it's done.

    A "rest" deload week needs ZERO sessions — there's no calendar to wait
    out in this model, so the mesocycle simply finishes once the last
    NORMAL week's sessions are complete. "reduced_load" still trains that
    week (just lighter), so it counts like any other week."""
    training_days_per_week = len(mesocycle.workout_templates)
    effective_weeks = mesocycle.number_of_weeks
    if mesocycle.deload_strategy.name == "rest":
        effective_weeks -= 1
    return effective_weeks * training_days_per_week


def current_position(mesocycle: MesocycleModel) -> tuple[int, WorkoutTemplateModel | None]:
    """Derives (current_week_number, next_workout_template) from
    sessions_completed — see domain/mesocycle.py module docstring for why
    this is session-count-based rather than calendar-based. Returns
    (number_of_weeks, None) once the mesocycle's total sessions are done."""
    training_days_per_week = len(mesocycle.workout_templates)
    if training_days_per_week == 0:
        return 1, None

    if mesocycle.sessions_completed >= total_required_sessions(mesocycle):
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
    target_weight: float | None = None


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
            target_weight=s.target_weight,
        ))

    db.commit()
    db.refresh(prescription)
    return _prescription_to_domain(prescription)


def _prescription_to_domain(row: ExercisePrescriptionModel) -> ExercisePrescription:
    target_rpe = row.week.target_rpe
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
                target_rpe=target_rpe,
                target_weight=s.target_weight,
            )
            for s in row.sets
        ],
    )


def get_week_prescriptions(db: Session, week_id: int) -> list[ExercisePrescription]:
    rows = (
        db.query(ExercisePrescriptionModel)
        .options(
            selectinload(ExercisePrescriptionModel.week),
            selectinload(ExercisePrescriptionModel.sets)
            .selectinload(SetPrescriptionModel.set_type),
            selectinload(ExercisePrescriptionModel.sets)
            .selectinload(SetPrescriptionModel.tempo),
        )
        .filter(ExercisePrescriptionModel.week_id == week_id)
        .all()
    )
    return [_prescription_to_domain(row) for row in rows]
