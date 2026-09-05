from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    ExercisePrescriptionResponse,
    MesocycleCreateRequest,
    MesocycleResponse,
    PrescriptionCreateRequest,
    ProgramCreateRequest,
    ProgramResponse,
    SetPrescriptionResponse,
    TemplateExerciseResponse,
    WeekResponse,
    WorkoutTemplateResponse,
)
from app.application.program_service import (
    SetPrescriptionInput,
    WeekInput,
    WorkoutTemplateInput,
    add_prescription,
    create_mesocycle,
    create_program,
    get_mesocycle,
    get_week_prescriptions,
)
from app.infrastructure.database import get_db
from app.infrastructure.program_models import MesocycleModel

router = APIRouter(tags=["programs"])


def _mesocycle_to_response(m: MesocycleModel) -> MesocycleResponse:
    return MesocycleResponse(
        id=m.id,
        program_id=m.program_id,
        name=m.name,
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
    "/programs", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED
)
def create_program_route(
    body: ProgramCreateRequest, db: Session = Depends(get_db)
) -> ProgramResponse:
    program = create_program(db, body.athlete_id, body.name, body.description)
    return ProgramResponse(
        id=program.id, athlete_id=program.athlete_id, name=program.name,
        description=program.description,
    )


@router.post(
    "/programs/{program_id}/mesocycles",
    response_model=MesocycleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mesocycle_route(
    program_id: int, body: MesocycleCreateRequest, db: Session = Depends(get_db)
) -> MesocycleResponse:
    mesocycle = create_mesocycle(
        db,
        program_id=program_id,
        name=body.name,
        weeks=[WeekInput(w.week_number, w.is_deload) for w in body.weeks],
        workout_templates=[
            WorkoutTemplateInput(t.name, t.order_in_split, t.exercise_ids)
            for t in body.workout_templates
        ],
    )
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
