from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    ExercisePrescriptionResponse,
    MesocycleCopyRequest,
    MesocycleCreateRequest,
    MesocycleResponse,
    MesocycleStopRequest,
    PrescriptionCreateRequest,
    SetPrescriptionResponse,
    TemplateExerciseResponse,
    WeekResponse,
    WorkoutTemplateResponse,
)
from app.application.mesocycle_service import (
    AthleteAlreadyHasActiveMesocycle,
    InvalidMesocycleLength,
    MesocycleNotFound,
    SetPrescriptionInput,
    WorkoutTemplateInput,
    add_prescription,
    copy_mesocycle,
    create_mesocycle,
    current_position,
    get_mesocycle,
    get_week_prescriptions,
    list_athlete_mesocycles,
    stop_mesocycle,
)
from app.infrastructure.database import get_db
from app.infrastructure.mesocycle_models import MesocycleModel

router = APIRouter(tags=["mesocycles"])


def _mesocycle_to_response(m: MesocycleModel) -> MesocycleResponse:
    week_number, next_template = current_position(m)
    return MesocycleResponse(
        id=m.id,
        athlete_id=m.athlete_id,
        name=m.name,
        number_of_weeks=m.number_of_weeks,
        deload_strategy=m.deload_strategy.name,
        status=m.status,
        sessions_completed=m.sessions_completed,
        current_week_number=week_number,
        next_workout_template_id=next_template.id if next_template else None,
        weeks=[
            WeekResponse(id=w.id, week_number=w.week_number, is_deload=w.is_deload)
            for w in m.weeks
        ],
        workout_templates=[
            WorkoutTemplateResponse(
                id=t.id,
                name=t.name,
                order_in_split=t.order_in_split,
                exercises=[
                    TemplateExerciseResponse(
                        id=te.id,
                        exercise_id=te.exercise_id,
                        exercise_name=te.exercise.name,
                        order_in_workout=te.order_in_workout,
                    )
                    for te in t.exercises
                ],
            )
            for t in m.workout_templates
        ],
    )


@router.post(
    "/mesocycles", response_model=MesocycleResponse, status_code=status.HTTP_201_CREATED
)
def create_mesocycle_route(
    body: MesocycleCreateRequest, db: Session = Depends(get_db)
) -> MesocycleResponse:
    try:
        mesocycle = create_mesocycle(
            db,
            athlete_id=body.athlete_id,
            name=body.name,
            number_of_weeks=body.number_of_weeks,
            deload_strategy_name=body.deload_strategy,
            workout_templates=[
                WorkoutTemplateInput(t.name, t.order_in_split, t.exercise_ids)
                for t in body.workout_templates
            ],
        )
    except AthleteAlreadyHasActiveMesocycle as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Athlete already has an active mesocycle (id={exc.args[0]}). "
                   "Stop it before starting a new one.",
        ) from exc
    except InvalidMesocycleLength as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mesocycle length must be between 4 and 12 weeks.",
        ) from exc

    return _mesocycle_to_response(mesocycle)


@router.get("/mesocycles/{mesocycle_id}", response_model=MesocycleResponse)
def get_mesocycle_route(
    mesocycle_id: int, db: Session = Depends(get_db)
) -> MesocycleResponse:
    mesocycle = get_mesocycle(db, mesocycle_id)
    if mesocycle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mesocycle not found."
        )
    return _mesocycle_to_response(mesocycle)


@router.get("/athletes/{athlete_id}/mesocycles", response_model=list[MesocycleResponse])
def list_athlete_mesocycles_route(
    athlete_id: int, db: Session = Depends(get_db)
) -> list[MesocycleResponse]:
    mesocycles = list_athlete_mesocycles(db, athlete_id)
    return [_mesocycle_to_response(m) for m in mesocycles]


@router.post("/mesocycles/{mesocycle_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
def stop_mesocycle_route(
    mesocycle_id: int, body: MesocycleStopRequest, db: Session = Depends(get_db)
) -> None:
    try:
        stop_mesocycle(db, mesocycle_id, keep_as_history=body.keep_as_history)
    except MesocycleNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mesocycle not found."
        ) from exc


@router.post(
    "/mesocycles/{mesocycle_id}/copy",
    response_model=MesocycleResponse,
    status_code=status.HTTP_201_CREATED,
)
def copy_mesocycle_route(
    mesocycle_id: int, body: MesocycleCopyRequest, db: Session = Depends(get_db)
) -> MesocycleResponse:
    try:
        new_mesocycle = copy_mesocycle(db, mesocycle_id, body.new_name)
    except MesocycleNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mesocycle not found."
        ) from exc
    except AthleteAlreadyHasActiveMesocycle as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Athlete already has an active mesocycle (id={exc.args[0]}). "
                   "Stop it before copying into a new one.",
        ) from exc
    return _mesocycle_to_response(new_mesocycle)


@router.post(
    "/template-exercises/{template_exercise_id}/prescriptions",
    response_model=ExercisePrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_prescription_route(
    template_exercise_id: int,
    body: PrescriptionCreateRequest,
    db: Session = Depends(get_db),
) -> ExercisePrescriptionResponse:
    prescription = add_prescription(
        db,
        template_exercise_id=template_exercise_id,
        week_id=body.week_id,
        notes=body.notes,
        sets=[
            SetPrescriptionInput(
                s.set_type, s.tempo, s.rep_range_min, s.rep_range_max, s.target_rir
            )
            for s in body.sets
        ],
    )
    return ExercisePrescriptionResponse(
        id=prescription.id,
        template_exercise_id=prescription.template_exercise_id,
        week_id=prescription.week_id,
        notes=prescription.notes,
        sets=[
            SetPrescriptionResponse(
                id=s.id, set_number=s.set_number, set_type=s.set_type,
                tempo=s.tempo, rep_range_min=s.rep_range_min,
                rep_range_max=s.rep_range_max, target_rir=s.target_rir,
            )
            for s in prescription.sets
        ],
    )


@router.get(
    "/weeks/{week_id}/prescriptions",
    response_model=list[ExercisePrescriptionResponse],
)
def list_week_prescriptions_route(
    week_id: int, db: Session = Depends(get_db)
) -> list[ExercisePrescriptionResponse]:
    prescriptions = get_week_prescriptions(db, week_id)
    return [
        ExercisePrescriptionResponse(
            id=p.id, template_exercise_id=p.template_exercise_id, week_id=p.week_id,
            notes=p.notes,
            sets=[
                SetPrescriptionResponse(
                    id=s.id, set_number=s.set_number, set_type=s.set_type,
                    tempo=s.tempo, rep_range_min=s.rep_range_min,
                    rep_range_max=s.rep_range_max, target_rir=s.target_rir,
                )
                for s in p.sets
            ],
        )
        for p in prescriptions
    ]
