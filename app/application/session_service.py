from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from app.application.mesocycle_service import (
    current_position,
    get_mesocycle,
    total_required_sessions,
)
from app.infrastructure.mesocycle_models import (
    ExercisePrescriptionModel,
    MesocycleModel,
    SetPrescriptionModel,
)
from app.infrastructure.session_models import (
    PerformedExerciseModel,
    SetPerformanceModel,
    WorkoutSessionModel,
)


class MesocycleNotActive(Exception):
    pass


class MesocycleAlreadyComplete(Exception):
    pass


class SessionAlreadyInProgress(Exception):
    pass


class SessionNotFound(Exception):
    pass


class InvalidSessionState(Exception):
    pass


def start_session(db: Session, mesocycle_id: int) -> WorkoutSessionModel:
    """Starts a session for whatever current_position() says is next —
    the caller doesn't get to pick, per the fixed-rotation decision."""
    mesocycle = get_mesocycle(db, mesocycle_id)
    if mesocycle is None or mesocycle.status != "active":
        raise MesocycleNotActive(mesocycle_id)

    existing = (
        db.query(WorkoutSessionModel)
        .filter(
            WorkoutSessionModel.mesocycle_id == mesocycle_id,
            WorkoutSessionModel.status == "in_progress",
        )
        .first()
    )
    if existing is not None:
        raise SessionAlreadyInProgress(existing.id)

    week_number, next_template = current_position(mesocycle)
    if next_template is None:
        raise MesocycleAlreadyComplete(mesocycle_id)

    week = next(w for w in mesocycle.weeks if w.week_number == week_number)

    workout_session = WorkoutSessionModel(
        mesocycle_id=mesocycle_id,
        week_id=week.id,
        workout_template_id=next_template.id,
        status="in_progress",
    )
    db.add(workout_session)
    db.flush()

    for template_exercise in next_template.exercises:
        db.add(PerformedExerciseModel(
            workout_session_id=workout_session.id,
            template_exercise_id=template_exercise.id,
            exercise_id=template_exercise.exercise_id,
            order_performed=template_exercise.order_in_workout,
        ))

    db.commit()
    db.refresh(workout_session)
    return workout_session


def log_set(
    db: Session,
    performed_exercise_id: int,
    set_prescription_id: int | None = None,
    actual_weight: float | None = None,
    actual_reps: float | None = None,
    actual_rpe: float | None = None,
    notes: str | None = None,
) -> SetPerformanceModel:
    existing_count = (
        db.query(SetPerformanceModel)
        .filter(SetPerformanceModel.performed_exercise_id == performed_exercise_id)
        .count()
    )

    set_performance = SetPerformanceModel(
        performed_exercise_id=performed_exercise_id,
        set_prescription_id=set_prescription_id,
        set_number=existing_count + 1,
        actual_weight=actual_weight,
        actual_reps=actual_reps,
        actual_rpe=actual_rpe,
        notes=notes,
    )
    db.add(set_performance)
    db.commit()
    db.refresh(set_performance)
    return set_performance


def complete_session(db: Session, session_id: int) -> WorkoutSessionModel:
    workout_session = (
        db.query(WorkoutSessionModel)
        .filter(WorkoutSessionModel.id == session_id)
        .first()
    )
    if workout_session is None:
        raise SessionNotFound(session_id)
    if workout_session.status != "in_progress":
        raise InvalidSessionState(workout_session.status)

    workout_session.status = "completed"
    workout_session.completed_at = datetime.now(timezone.utc)

    mesocycle = (
        db.query(MesocycleModel)
        .filter(MesocycleModel.id == workout_session.mesocycle_id)
        .first()
    )
    mesocycle.sessions_completed += 1

    # Auto-complete: the mesocycle finishes the instant its required
    # sessions are done — no explicit "finish mesocycle" confirmation,
    # consistent with everything else here being session-driven rather
    # than requiring a manual step. A "rest" deload week needs zero
    # sessions, so this can trigger right after the last normal week.
    full_mesocycle = get_mesocycle(db, mesocycle.id)
    if mesocycle.sessions_completed >= total_required_sessions(full_mesocycle):
        mesocycle.status = "completed"

    db.commit()
    db.refresh(workout_session)
    return workout_session


def abandon_session(db: Session, session_id: int) -> WorkoutSessionModel:
    """Does NOT touch sessions_completed — an abandoned session can be
    picked back up later without having consumed its rotation slot."""
    workout_session = (
        db.query(WorkoutSessionModel)
        .filter(WorkoutSessionModel.id == session_id)
        .first()
    )
    if workout_session is None:
        raise SessionNotFound(session_id)
    if workout_session.status != "in_progress":
        raise InvalidSessionState(workout_session.status)

    workout_session.status = "abandoned"
    db.commit()
    db.refresh(workout_session)
    return workout_session


def get_session(db: Session, session_id: int) -> WorkoutSessionModel | None:
    return (
        db.query(WorkoutSessionModel)
        .options(
            selectinload(WorkoutSessionModel.week),
            selectinload(WorkoutSessionModel.performed_exercises)
            .selectinload(PerformedExerciseModel.exercise),
            selectinload(WorkoutSessionModel.performed_exercises)
            .selectinload(PerformedExerciseModel.sets),
        )
        .filter(WorkoutSessionModel.id == session_id)
        .first()
    )


def get_prescription_for(
    db: Session, template_exercise_id: int, week_id: int
) -> ExercisePrescriptionModel | None:
    """Looks up the plan for a given slot+week, so the API layer can show
    prescribed sets alongside performed sets — the actual expected-vs-actual
    comparison."""
    return (
        db.query(ExercisePrescriptionModel)
        .options(
            selectinload(ExercisePrescriptionModel.week),
            selectinload(ExercisePrescriptionModel.sets)
            .selectinload(SetPrescriptionModel.set_type),
            selectinload(ExercisePrescriptionModel.sets)
            .selectinload(SetPrescriptionModel.tempo),
        )
        .filter(
            ExercisePrescriptionModel.template_exercise_id == template_exercise_id,
            ExercisePrescriptionModel.week_id == week_id,
        )
        .first()
    )
