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
from app.infrastructure.session_models import WorkoutSessionModel

MIN_WEEKS = 4
MAX_WEEKS = 12

_LOCKED_STATUSES = (MesocycleStatus.COMPLETED.value, MesocycleStatus.ABANDONED.value)


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


class MesocycleNotDraft(Exception):
    pass


class MesocycleLocked(Exception):
    """Raised when trying to mutate a completed/abandoned mesocycle —
    these are locked to preserve accurate history, per the athlete's
    explicit request."""
    pass


class WeekAlreadyTrained(Exception):
    """Raised when trying to edit a prescription/set for a week that
    already has a completed session logged against it — protects the
    accuracy of the historical expected-vs-actual record."""
    pass


class TemplateExerciseNotFound(Exception):
    pass


class SetPrescriptionNotFound(Exception):
    pass


class ExercisePrescriptionNotFound(Exception):
    pass


class WorkoutTemplateNotFound(Exception):
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
    nearest whole number. A "rest" or "reduced_load" deload week gets no
    target at all. "none" means there's no deload week, so every week is
    part of the ramp."""
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


# --- Guards ---


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


def _assert_not_started(mesocycle: MesocycleModel) -> None:
    """Foundational shape (exercise selection, training days, mesocycle
    length/deload strategy) is only editable before any session has been
    logged — changing these mid-block would undermine the athlete's own
    fixed-shape design principle and corrupt the rotation/RPE-ramp math."""
    if mesocycle.sessions_completed > 0:
        raise MesocycleAlreadyStarted(mesocycle.id)


def _assert_mutable(mesocycle: MesocycleModel) -> None:
    """Completed/abandoned mesocycles are locked entirely — no add, edit,
    or remove on anything inside them, so they stay accurate history."""
    if mesocycle.status in _LOCKED_STATUSES:
        raise MesocycleLocked(mesocycle.id)


def _assert_week_not_trained(db: Session, week_id: int) -> None:
    """Protects a week's plan once a real session has been completed
    against it — editing the prescription after the fact would corrupt
    the expected-vs-actual comparison for that history."""
    trained = (
        db.query(WorkoutSessionModel)
        .filter(
            WorkoutSessionModel.week_id == week_id,
            WorkoutSessionModel.status == "completed",
        )
        .first()
    )
    if trained is not None:
        raise WeekAlreadyTrained(week_id)


# --- Mesocycle lifecycle ---


def create_mesocycle(
    db: Session,
    athlete_id: int,
    name: str,
    number_of_weeks: int,
    deload_strategy_name: str,
    workout_templates: list[WorkoutTemplateInput],
) -> MesocycleModel:
    """Creates a new mesocycle in DRAFT status — NOT active yet. An
    athlete can have any number of drafts (e.g. planning the next block
    while still training the current one); only starting one (see
    start_mesocycle) is limited to one at a time. Auto-generates its
    weeks (last one is always the deload week), plus its workout
    templates and exercise slots."""
    if not (MIN_WEEKS <= number_of_weeks <= MAX_WEEKS):
        raise InvalidMesocycleLength(number_of_weeks)

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
        status=MesocycleStatus.DRAFT.value,
        sessions_completed=0,
    )
    db.add(mesocycle)
    db.flush()

    _sync_weeks(db, mesocycle, number_of_weeks, deload_strategy_name)
    _create_workout_templates(db, mesocycle.id, workout_templates)

    db.commit()
    db.refresh(mesocycle)
    return mesocycle


def _sync_weeks(
    db: Session, mesocycle: MesocycleModel, number_of_weeks: int, deload_strategy_name: str
) -> None:
    """Creates (or, for edit_mesocycle, reconciles) this mesocycle's Week
    rows to match number_of_weeks/deload_strategy_name. Safe to call on an
    existing mesocycle ONLY when _assert_not_started has already passed —
    otherwise this could delete weeks real sessions reference."""
    existing_weeks = {w.week_number: w for w in mesocycle.weeks}
    target_rpes = compute_week_target_rpes(number_of_weeks, deload_strategy_name)

    for week_number, week in list(existing_weeks.items()):
        if week_number > number_of_weeks:
            db.delete(week)
            del existing_weeks[week_number]

    for week_number in range(1, number_of_weeks + 1):
        is_deload = (
            deload_strategy_name in ("rest", "reduced_load")
            and week_number == number_of_weeks
        )
        if week_number in existing_weeks:
            existing_weeks[week_number].is_deload = is_deload
            existing_weeks[week_number].target_rpe = target_rpes[week_number]
        else:
            db.add(WeekModel(
                mesocycle_id=mesocycle.id,
                week_number=week_number,
                is_deload=is_deload,
                target_rpe=target_rpes[week_number],
            ))


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


def start_mesocycle(db: Session, mesocycle_id: int) -> MesocycleModel:
    """Activates a DRAFT mesocycle. This is where the one-active-at-a-time
    rule is enforced now — not at creation time — so an athlete can freely
    draft up future blocks while still training a current one."""
    mesocycle = db.query(MesocycleModel).filter(MesocycleModel.id == mesocycle_id).first()
    if mesocycle is None:
        raise MesocycleNotFound(mesocycle_id)
    if mesocycle.status != MesocycleStatus.DRAFT.value:
        raise MesocycleNotDraft(mesocycle.status)

    _assert_no_active_mesocycle(db, mesocycle.athlete_id)

    mesocycle.status = MesocycleStatus.ACTIVE.value
    db.commit()
    db.refresh(mesocycle)
    return mesocycle


def edit_mesocycle(
    db: Session,
    mesocycle_id: int,
    name: str | None = None,
    number_of_weeks: int | None = None,
    deload_strategy_name: str | None = None,
) -> MesocycleModel:
    """name is always editable. number_of_weeks/deload_strategy_name are
    foundational shape — only editable before any session has been
    logged, since they drive the RPE ramp and total-session math."""
    mesocycle = get_mesocycle(db, mesocycle_id)
    if mesocycle is None:
        raise MesocycleNotFound(mesocycle_id)
    _assert_mutable(mesocycle)

    if name is not None:
        mesocycle.name = name

    if number_of_weeks is not None or deload_strategy_name is not None:
        _assert_not_started(mesocycle)

        new_weeks = number_of_weeks if number_of_weeks is not None else mesocycle.number_of_weeks
        if not (MIN_WEEKS <= new_weeks <= MAX_WEEKS):
            raise InvalidMesocycleLength(new_weeks)

        new_strategy_name = deload_strategy_name or mesocycle.deload_strategy.name
        if deload_strategy_name is not None:
            strategy = (
                db.query(DeloadStrategyModel)
                .filter(DeloadStrategyModel.name == deload_strategy_name)
                .first()
            )
            if strategy is None:
                raise ValueError(f"Unknown deload strategy: {deload_strategy_name}")
            mesocycle.deload_strategy_id = strategy.id

        mesocycle.number_of_weeks = new_weeks
        _sync_weeks(db, mesocycle, new_weeks, new_strategy_name)

    db.commit()
    db.refresh(mesocycle)
    return mesocycle


def stop_mesocycle(db: Session, mesocycle_id: int, keep_as_history: bool) -> None:
    """keep_as_history=True marks it ABANDONED (visible in history, per the
    athlete's choice); False deletes it outright. Only valid for an ACTIVE
    mesocycle — a draft should just be deleted directly."""
    mesocycle = db.query(MesocycleModel).filter(MesocycleModel.id == mesocycle_id).first()
    if mesocycle is None:
        raise MesocycleNotFound(mesocycle_id)
    if mesocycle.status != MesocycleStatus.ACTIVE.value:
        raise MesocycleNotDraft(mesocycle.status)  # reused: "not in the expected state"

    if keep_as_history:
        mesocycle.status = MesocycleStatus.ABANDONED.value
        db.commit()
    else:
        db.delete(mesocycle)
        db.commit()


def copy_mesocycle(db: Session, source_mesocycle_id: int, new_name: str) -> MesocycleModel:
    """Duplicates a mesocycle's SHAPE (weeks, workout templates, exercise
    slots) into a brand new DRAFT mesocycle for the same athlete —
    start_mesocycle activates it when the athlete is ready. Deliberately
    does NOT copy prescriptions — starting numbers adjusted from the
    previous mesocycle's performance is progression-engine work, done
    live during training, not at copy time."""
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


def delete_mesocycle(db: Session, mesocycle_id: int) -> None:
    """Removes a mesocycle entirely — drafts, completed, or abandoned
    ones. An active mesocycle must be stopped first (via stop_mesocycle).
    This is intentionally NOT blocked by _assert_mutable: choosing to
    delete a completed record entirely is different from tampering with
    its contents, which IS blocked everywhere else."""
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


# --- Workout templates & template exercises ---


def add_workout_template(
    db: Session, mesocycle_id: int, name: str, order_in_split: int, exercise_ids: list[int]
) -> WorkoutTemplateModel:
    """Adds a whole new training day. Changes training_days_per_week, so
    restricted the same way as exercise-selection edits."""
    mesocycle = get_mesocycle(db, mesocycle_id)
    if mesocycle is None:
        raise MesocycleNotFound(mesocycle_id)
    _assert_mutable(mesocycle)
    _assert_not_started(mesocycle)

    template = WorkoutTemplateModel(
        mesocycle_id=mesocycle_id, name=name, order_in_split=order_in_split
    )
    db.add(template)
    db.flush()
    for position, exercise_id in enumerate(exercise_ids, start=1):
        db.add(TemplateExerciseModel(
            workout_template_id=template.id, exercise_id=exercise_id, order_in_workout=position
        ))
    db.commit()
    db.refresh(template)
    return template


def edit_workout_template(
    db: Session, workout_template_id: int, name: str
) -> WorkoutTemplateModel:
    """Rename only — cosmetic, always allowed regardless of whether the
    mesocycle has started (just not once it's completed/abandoned)."""
    template = (
        db.query(WorkoutTemplateModel).filter(WorkoutTemplateModel.id == workout_template_id).first()
    )
    if template is None:
        raise WorkoutTemplateNotFound(workout_template_id)
    _assert_mutable(template.mesocycle)

    template.name = name
    db.commit()
    db.refresh(template)
    return template


def reorder_workout_template(
    db: Session, workout_template_id: int, new_position: int
) -> list[WorkoutTemplateModel]:
    """Moves a training day to a new position in the weekly rotation.
    Restricted the same as adding/removing a day — changes the rotation
    order that current_position() walks through."""
    template = (
        db.query(WorkoutTemplateModel).filter(WorkoutTemplateModel.id == workout_template_id).first()
    )
    if template is None:
        raise WorkoutTemplateNotFound(workout_template_id)
    mesocycle = template.mesocycle
    _assert_mutable(mesocycle)
    _assert_not_started(mesocycle)

    templates = sorted(mesocycle.workout_templates, key=lambda t: t.order_in_split)
    templates.remove(template)
    clamped_position = max(1, min(new_position, len(templates) + 1))
    templates.insert(clamped_position - 1, template)

    for position, t in enumerate(templates, start=1):
        t.order_in_split = position

    db.commit()
    for t in templates:
        db.refresh(t)
    return templates


def remove_workout_template(db: Session, workout_template_id: int) -> None:
    template = (
        db.query(WorkoutTemplateModel).filter(WorkoutTemplateModel.id == workout_template_id).first()
    )
    if template is None:
        raise WorkoutTemplateNotFound(workout_template_id)
    mesocycle = template.mesocycle
    _assert_mutable(mesocycle)
    _assert_not_started(mesocycle)

    db.delete(template)
    db.flush()

    remaining = (
        db.query(WorkoutTemplateModel)
        .filter(WorkoutTemplateModel.mesocycle_id == mesocycle.id)
        .order_by(WorkoutTemplateModel.order_in_split)
        .all()
    )
    for position, t in enumerate(remaining, start=1):
        t.order_in_split = position

    db.commit()


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

    mesocycle = template_exercise.workout_template.mesocycle
    _assert_mutable(mesocycle)
    _assert_not_started(mesocycle)

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
        raise WorkoutTemplateNotFound(workout_template_id)

    _assert_mutable(template.mesocycle)
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
    _assert_mutable(template.mesocycle)
    _assert_not_started(template.mesocycle)

    db.delete(template_exercise)
    db.flush()

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
    template_exercise = (
        db.query(TemplateExerciseModel)
        .filter(TemplateExerciseModel.id == template_exercise_id)
        .first()
    )
    if template_exercise is None:
        raise TemplateExerciseNotFound(template_exercise_id)

    template = template_exercise.workout_template
    _assert_mutable(template.mesocycle)
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


# --- Exercise & set prescriptions ---


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
    template_exercise = (
        db.query(TemplateExerciseModel)
        .filter(TemplateExerciseModel.id == template_exercise_id)
        .first()
    )
    if template_exercise is None:
        raise TemplateExerciseNotFound(template_exercise_id)
    _assert_mutable(template_exercise.workout_template.mesocycle)
    _assert_week_not_trained(db, week_id)

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


def edit_prescription_notes(
    db: Session, exercise_prescription_id: int, notes: str
) -> ExercisePrescription:
    prescription = (
        db.query(ExercisePrescriptionModel)
        .filter(ExercisePrescriptionModel.id == exercise_prescription_id)
        .first()
    )
    if prescription is None:
        raise ExercisePrescriptionNotFound(exercise_prescription_id)

    mesocycle = prescription.template_exercise.workout_template.mesocycle
    _assert_mutable(mesocycle)
    _assert_week_not_trained(db, prescription.week_id)

    prescription.notes = notes
    db.commit()
    db.refresh(prescription)
    return _prescription_to_domain(prescription)


def remove_prescription(db: Session, exercise_prescription_id: int) -> None:
    prescription = (
        db.query(ExercisePrescriptionModel)
        .filter(ExercisePrescriptionModel.id == exercise_prescription_id)
        .first()
    )
    if prescription is None:
        raise ExercisePrescriptionNotFound(exercise_prescription_id)

    mesocycle = prescription.template_exercise.workout_template.mesocycle
    _assert_mutable(mesocycle)
    _assert_week_not_trained(db, prescription.week_id)

    db.delete(prescription)
    db.commit()


def add_set_to_prescription(
    db: Session, exercise_prescription_id: int, set_input: SetPrescriptionInput
) -> SetPrescriptionModel:
    prescription = (
        db.query(ExercisePrescriptionModel)
        .filter(ExercisePrescriptionModel.id == exercise_prescription_id)
        .first()
    )
    if prescription is None:
        raise ExercisePrescriptionNotFound(exercise_prescription_id)

    mesocycle = prescription.template_exercise.workout_template.mesocycle
    _assert_mutable(mesocycle)
    _assert_week_not_trained(db, prescription.week_id)

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

    prescription = set_prescription.exercise_prescription
    mesocycle = prescription.template_exercise.workout_template.mesocycle
    _assert_mutable(mesocycle)
    _assert_week_not_trained(db, prescription.week_id)

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
    """Any argument left as None is unchanged, EXCEPT target_weight —
    since None is a legitimate value there (no recommendation),
    clear_target_weight explicitly opts into clearing it."""
    set_prescription = (
        db.query(SetPrescriptionModel)
        .filter(SetPrescriptionModel.id == set_prescription_id)
        .first()
    )
    if set_prescription is None:
        raise SetPrescriptionNotFound(set_prescription_id)

    prescription = set_prescription.exercise_prescription
    mesocycle = prescription.template_exercise.workout_template.mesocycle
    _assert_mutable(mesocycle)
    _assert_week_not_trained(db, prescription.week_id)

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
