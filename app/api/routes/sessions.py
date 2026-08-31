from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    LogSetRequest,
    PerformedExerciseResponse,
    PrescribedSetResponse,
    SetPerformanceResponse,
    WorkoutSessionResponse,
)
from app.application.session_service import (
    InvalidSessionState,
    MesocycleAlreadyComplete,
    MesocycleNotActive,
    SessionAlreadyInProgress,
    SessionNotFound,
    abandon_session,
    complete_session,
    get_prescription_for,
    get_session,
    log_set,
    start_session,
)
from app.infrastructure.database import get_db
from app.infrastructure.session_models import WorkoutSessionModel

router = APIRouter(tags=["sessions"])


def _session_to_response(db: Session, ws: WorkoutSessionModel) -> WorkoutSessionResponse:
    performed_exercises = []
    for pe in ws.performed_exercises:
        prescribed_sets: list[PrescribedSetResponse] = []
        if pe.template_exercise_id is not None:
            prescription = get_prescription_for(db, pe.template_exercise_id, ws.week_id)
            if prescription is not None:
                prescribed_sets = [
                    PrescribedSetResponse(
                        set_number=s.set_number, set_type=s.set_type.name,
                        tempo=s.tempo.name, rep_range_min=s.rep_range_min,
                        rep_range_max=s.rep_range_max, target_rir=s.target_rir,
                    )
                    for s in prescription.sets
                ]

        performed_exercises.append(PerformedExerciseResponse(
            id=pe.id,
            template_exercise_id=pe.template_exercise_id,
            exercise_id=pe.exercise_id,
            exercise_name=pe.exercise.name,
            order_performed=pe.order_performed,
            prescribed_sets=prescribed_sets,
            performed_sets=[
                SetPerformanceResponse(
                    id=s.id, set_prescription_id=s.set_prescription_id,
                    set_number=s.set_number, set_type=s.set_type.name,
                    tempo=s.tempo.name, actual_weight=s.actual_weight,
                    actual_reps=s.actual_reps, partial_reps=s.partial_reps,
                    actual_rir=s.actual_rir,
                )
                for s in pe.sets
            ],
        ))

    return WorkoutSessionResponse(
        id=ws.id, mesocycle_id=ws.mesocycle_id, week_id=ws.week_id,
        workout_template_id=ws.workout_template_id, status=ws.status,
        started_at=ws.started_at, completed_at=ws.completed_at,
        performed_exercises=performed_exercises,
    )


@router.post(
    "/mesocycles/{mesocycle_id}/sessions/start",
    response_model=WorkoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_session_route(
    mesocycle_id: int, db: Session = Depends(get_db)
) -> WorkoutSessionResponse:
    try:
        workout_session = start_session(db, mesocycle_id)
    except MesocycleNotActive as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mesocycle is not active.",
        ) from exc
    except SessionAlreadyInProgress as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A session is already in progress (id={exc.args[0]}).",
        ) from exc
    except MesocycleAlreadyComplete as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle has no remaining sessions.",
        ) from exc

    return _session_to_response(db, workout_session)


@router.get("/workout-sessions/{session_id}", response_model=WorkoutSessionResponse)
def get_session_route(
    session_id: int, db: Session = Depends(get_db)
) -> WorkoutSessionResponse:
    workout_session = get_session(db, session_id)
    if workout_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
        )
    return _session_to_response(db, workout_session)


@router.post(
    "/performed-exercises/{performed_exercise_id}/sets",
    response_model=SetPerformanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def log_set_route(
    performed_exercise_id: int, body: LogSetRequest, db: Session = Depends(get_db)
) -> SetPerformanceResponse:
    s = log_set(
        db,
        performed_exercise_id=performed_exercise_id,
        set_type_name=body.set_type,
        tempo_name=body.tempo,
        set_prescription_id=body.set_prescription_id,
        actual_weight=body.actual_weight,
        actual_reps=body.actual_reps,
        partial_reps=body.partial_reps,
        actual_rir=body.actual_rir,
    )
    return SetPerformanceResponse(
        id=s.id, set_prescription_id=s.set_prescription_id, set_number=s.set_number,
        set_type=s.set_type.name, tempo=s.tempo.name, actual_weight=s.actual_weight,
        actual_reps=s.actual_reps, partial_reps=s.partial_reps, actual_rir=s.actual_rir,
    )


@router.post("/workout-sessions/{session_id}/complete", response_model=WorkoutSessionResponse)
def complete_session_route(
    session_id: int, db: Session = Depends(get_db)
) -> WorkoutSessionResponse:
    try:
        workout_session = complete_session(db, session_id)
    except SessionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
        ) from exc
    except InvalidSessionState as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session is '{exc.args[0]}', not in progress.",
        ) from exc
    return _session_to_response(db, workout_session)


@router.post("/workout-sessions/{session_id}/abandon", response_model=WorkoutSessionResponse)
def abandon_session_route(
    session_id: int, db: Session = Depends(get_db)
) -> WorkoutSessionResponse:
    try:
        workout_session = abandon_session(db, session_id)
    except SessionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
        ) from exc
    except InvalidSessionState as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session is '{exc.args[0]}', not in progress.",
        ) from exc
    return _session_to_response(db, workout_session)
