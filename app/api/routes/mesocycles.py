from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    AddSetRequest,
    AddTemplateExerciseRequest,
    AddWorkoutTemplateRequest,
    EditPrescriptionNotesRequest,
    EditSetRequest,
    EditTemplateExerciseRequest,
    EditWorkoutTemplateRequest,
    ExercisePrescriptionResponse,
    MesocycleCopyRequest,
    MesocycleCreateRequest,
    MesocycleEditRequest,
    MesocycleResponse,
    MesocycleStopRequest,
    PrescriptionCreateRequest,
    ReorderTemplateExerciseRequest,
    ReorderWorkoutTemplateRequest,
    SetPrescriptionResponse,
    TemplateExerciseResponse,
    WeekResponse,
    WorkoutTemplateResponse,
)
from app.application.mesocycle_service import (
    AthleteAlreadyHasActiveMesocycle,
    ExercisePrescriptionNotFound,
    InvalidMesocycleLength,
    MesocycleAlreadyStarted,
    MesocycleLocked,
    MesocycleNotDraft,
    MesocycleNotFound,
    MesocycleStillActive,
    SetPrescriptionInput,
    SetPrescriptionNotFound,
    TemplateExerciseNotFound,
    WeekAlreadyTrained,
    WorkoutTemplateInput,
    WorkoutTemplateNotFound,
    add_prescription,
    add_set_to_prescription,
    add_template_exercise,
    add_workout_template,
    copy_mesocycle,
    create_mesocycle,
    current_position,
    delete_mesocycle,
    edit_mesocycle,
    edit_prescription_notes,
    edit_set_in_prescription,
    edit_template_exercise,
    edit_workout_template,
    get_mesocycle,
    get_week_prescriptions,
    list_athlete_mesocycles,
    remove_prescription,
    remove_set_from_prescription,
    remove_template_exercise,
    remove_workout_template,
    reorder_template_exercise,
    reorder_workout_template,
    start_mesocycle,
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
            WeekResponse(
                id=w.id, week_number=w.week_number, is_deload=w.is_deload,
                target_rpe=w.target_rpe,
            )
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


def _template_exercise_response(te) -> TemplateExerciseResponse:
    return TemplateExerciseResponse(
        id=te.id, exercise_id=te.exercise_id, exercise_name=te.exercise.name,
        order_in_workout=te.order_in_workout,
    )


def _set_prescription_response(sp, target_rpe: float | None) -> SetPrescriptionResponse:
    return SetPrescriptionResponse(
        id=sp.id, set_number=sp.set_number, set_type=sp.set_type.name,
        tempo=sp.tempo.name, rep_range_min=sp.rep_range_min,
        rep_range_max=sp.rep_range_max, target_rpe=target_rpe, target_weight=sp.target_weight,
    )


def _exercise_prescription_response(prescription) -> ExercisePrescriptionResponse:
    target_rpe = prescription.week.target_rpe
    return ExercisePrescriptionResponse(
        id=prescription.id,
        template_exercise_id=prescription.template_exercise_id,
        week_id=prescription.week_id,
        notes=prescription.notes,
        sets=[_set_prescription_response(s, target_rpe) for s in prescription.sets],
    )


# --- Mesocycle lifecycle ---


@router.post(
    "/mesocycles", response_model=MesocycleResponse, status_code=status.HTTP_201_CREATED
)
def create_mesocycle_route(
    body: MesocycleCreateRequest, db: Session = Depends(get_db)
) -> MesocycleResponse:
    """Creates a DRAFT mesocycle — not active. Call POST .../start when
    ready to actually begin training it. An athlete can have as many
    drafts as they like; only one ACTIVE mesocycle is enforced, and only
    at start time."""
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
    except InvalidMesocycleLength as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mesocycle length must be between 4 and 12 weeks.",
        ) from exc

    return _mesocycle_to_response(mesocycle)


@router.post("/mesocycles/{mesocycle_id}/start", response_model=MesocycleResponse)
def start_mesocycle_route(
    mesocycle_id: int, db: Session = Depends(get_db)
) -> MesocycleResponse:
    try:
        mesocycle = start_mesocycle(db, mesocycle_id)
    except MesocycleNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mesocycle not found."
        ) from exc
    except MesocycleNotDraft as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mesocycle is '{exc.args[0]}', not draft — only drafts can be started.",
        ) from exc
    except AthleteAlreadyHasActiveMesocycle as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Athlete already has an active mesocycle (id={exc.args[0]}). "
                   "Stop it before starting this one.",
        ) from exc
    return _mesocycle_to_response(mesocycle)


@router.patch("/mesocycles/{mesocycle_id}", response_model=MesocycleResponse)
def edit_mesocycle_route(
    mesocycle_id: int, body: MesocycleEditRequest, db: Session = Depends(get_db)
) -> MesocycleResponse:
    try:
        mesocycle = edit_mesocycle(
            db, mesocycle_id, name=body.name, number_of_weeks=body.number_of_weeks,
            deload_strategy_name=body.deload_strategy,
        )
    except MesocycleNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mesocycle not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except MesocycleAlreadyStarted as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can't change length or deload strategy after the mesocycle has started.",
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
    except MesocycleNotDraft as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mesocycle is '{exc.args[0]}', not active.",
        ) from exc


@router.post(
    "/mesocycles/{mesocycle_id}/copy",
    response_model=MesocycleResponse,
    status_code=status.HTTP_201_CREATED,
)
def copy_mesocycle_route(
    mesocycle_id: int, body: MesocycleCopyRequest, db: Session = Depends(get_db)
) -> MesocycleResponse:
    """Copy always produces a DRAFT — start it separately when ready."""
    try:
        new_mesocycle = copy_mesocycle(db, mesocycle_id, body.new_name)
    except MesocycleNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mesocycle not found."
        ) from exc
    return _mesocycle_to_response(new_mesocycle)


@router.delete("/mesocycles/{mesocycle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mesocycle_route(mesocycle_id: int, db: Session = Depends(get_db)) -> None:
    try:
        delete_mesocycle(db, mesocycle_id)
    except MesocycleNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mesocycle not found."
        ) from exc
    except MesocycleStillActive as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stop the mesocycle before deleting it.",
        ) from exc


# --- Workout templates ---


@router.post(
    "/mesocycles/{mesocycle_id}/workout-templates",
    response_model=WorkoutTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_workout_template_route(
    mesocycle_id: int, body: AddWorkoutTemplateRequest, db: Session = Depends(get_db)
) -> WorkoutTemplateResponse:
    try:
        template = add_workout_template(
            db, mesocycle_id, body.name, body.order_in_split, body.exercise_ids
        )
    except MesocycleNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mesocycle not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except MesocycleAlreadyStarted as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can't add a training day after the mesocycle has started.",
        ) from exc
    return WorkoutTemplateResponse(
        id=template.id, name=template.name, order_in_split=template.order_in_split,
        exercises=[_template_exercise_response(te) for te in template.exercises],
    )


@router.patch("/workout-templates/{workout_template_id}", response_model=WorkoutTemplateResponse)
def edit_workout_template_route(
    workout_template_id: int, body: EditWorkoutTemplateRequest, db: Session = Depends(get_db)
) -> WorkoutTemplateResponse:
    try:
        template = edit_workout_template(db, workout_template_id, body.name)
    except WorkoutTemplateNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workout template not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    return WorkoutTemplateResponse(
        id=template.id, name=template.name, order_in_split=template.order_in_split,
        exercises=[_template_exercise_response(te) for te in template.exercises],
    )


@router.patch(
    "/workout-templates/{workout_template_id}/order",
    response_model=list[WorkoutTemplateResponse],
)
def reorder_workout_template_route(
    workout_template_id: int, body: ReorderWorkoutTemplateRequest, db: Session = Depends(get_db)
) -> list[WorkoutTemplateResponse]:
    try:
        templates = reorder_workout_template(db, workout_template_id, body.new_position)
    except WorkoutTemplateNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workout template not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except MesocycleAlreadyStarted as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can't reorder training days after the mesocycle has started.",
        ) from exc
    return [
        WorkoutTemplateResponse(
            id=t.id, name=t.name, order_in_split=t.order_in_split,
            exercises=[_template_exercise_response(te) for te in t.exercises],
        )
        for t in templates
    ]


@router.delete(
    "/workout-templates/{workout_template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_workout_template_route(
    workout_template_id: int, db: Session = Depends(get_db)
) -> None:
    try:
        remove_workout_template(db, workout_template_id)
    except WorkoutTemplateNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workout template not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except MesocycleAlreadyStarted as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can't remove a training day after the mesocycle has started.",
        ) from exc


# --- Template exercises ---


@router.patch("/template-exercises/{template_exercise_id}", response_model=TemplateExerciseResponse)
def edit_template_exercise_route(
    template_exercise_id: int, body: EditTemplateExerciseRequest, db: Session = Depends(get_db)
) -> TemplateExerciseResponse:
    try:
        te = edit_template_exercise(db, template_exercise_id, body.exercise_id)
    except TemplateExerciseNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise slot not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except MesocycleAlreadyStarted as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can't edit exercises after the mesocycle has started — "
                   "the selection is meant to stay fixed once training begins.",
        ) from exc
    return _template_exercise_response(te)


@router.post(
    "/workout-templates/{workout_template_id}/exercises",
    response_model=TemplateExerciseResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_template_exercise_route(
    workout_template_id: int, body: AddTemplateExerciseRequest, db: Session = Depends(get_db)
) -> TemplateExerciseResponse:
    try:
        te = add_template_exercise(db, workout_template_id, body.exercise_id)
    except WorkoutTemplateNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workout template not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except MesocycleAlreadyStarted as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can't edit exercises after the mesocycle has started.",
        ) from exc
    return _template_exercise_response(te)


@router.patch(
    "/template-exercises/{template_exercise_id}/order",
    response_model=list[TemplateExerciseResponse],
)
def reorder_template_exercise_route(
    template_exercise_id: int, body: ReorderTemplateExerciseRequest, db: Session = Depends(get_db)
) -> list[TemplateExerciseResponse]:
    try:
        exercises = reorder_template_exercise(db, template_exercise_id, body.new_position)
    except TemplateExerciseNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise slot not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except MesocycleAlreadyStarted as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can't reorder exercises after the mesocycle has started.",
        ) from exc
    return [_template_exercise_response(te) for te in exercises]


@router.delete(
    "/template-exercises/{template_exercise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_template_exercise_route(
    template_exercise_id: int, db: Session = Depends(get_db)
) -> None:
    try:
        remove_template_exercise(db, template_exercise_id)
    except TemplateExerciseNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise slot not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except MesocycleAlreadyStarted as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can't edit exercises after the mesocycle has started.",
        ) from exc


# --- Exercise & set prescriptions ---


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
    try:
        prescription = add_prescription(
            db,
            template_exercise_id=template_exercise_id,
            week_id=body.week_id,
            notes=body.notes,
            sets=[
                SetPrescriptionInput(
                    s.set_type, s.tempo, s.rep_range_min, s.rep_range_max, s.target_weight
                )
                for s in body.sets
            ],
        )
    except TemplateExerciseNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise slot not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except WeekAlreadyTrained as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session has already been completed for this week — its plan is locked.",
        ) from exc
    return ExercisePrescriptionResponse(
        id=prescription.id,
        template_exercise_id=prescription.template_exercise_id,
        week_id=prescription.week_id,
        notes=prescription.notes,
        sets=[
            SetPrescriptionResponse(
                id=s.id, set_number=s.set_number, set_type=s.set_type,
                tempo=s.tempo, rep_range_min=s.rep_range_min,
                rep_range_max=s.rep_range_max, target_rpe=s.target_rpe,
                target_weight=s.target_weight,
            )
            for s in prescription.sets
        ],
    )


@router.patch(
    "/exercise-prescriptions/{exercise_prescription_id}",
    response_model=ExercisePrescriptionResponse,
)
def edit_prescription_notes_route(
    exercise_prescription_id: int, body: EditPrescriptionNotesRequest, db: Session = Depends(get_db)
) -> ExercisePrescriptionResponse:
    try:
        prescription = edit_prescription_notes(db, exercise_prescription_id, body.notes)
    except ExercisePrescriptionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise prescription not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except WeekAlreadyTrained as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session has already been completed for this week — its plan is locked.",
        ) from exc
    return ExercisePrescriptionResponse(
        id=prescription.id, template_exercise_id=prescription.template_exercise_id,
        week_id=prescription.week_id, notes=prescription.notes,
        sets=[
            SetPrescriptionResponse(
                id=s.id, set_number=s.set_number, set_type=s.set_type, tempo=s.tempo,
                rep_range_min=s.rep_range_min, rep_range_max=s.rep_range_max,
                target_rpe=s.target_rpe, target_weight=s.target_weight,
            )
            for s in prescription.sets
        ],
    )


@router.delete(
    "/exercise-prescriptions/{exercise_prescription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_prescription_route(
    exercise_prescription_id: int, db: Session = Depends(get_db)
) -> None:
    try:
        remove_prescription(db, exercise_prescription_id)
    except ExercisePrescriptionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise prescription not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except WeekAlreadyTrained as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session has already been completed for this week — its plan is locked.",
        ) from exc


@router.post(
    "/exercise-prescriptions/{exercise_prescription_id}/sets",
    response_model=SetPrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_set_route(
    exercise_prescription_id: int, body: AddSetRequest, db: Session = Depends(get_db)
) -> SetPrescriptionResponse:
    try:
        sp = add_set_to_prescription(
            db, exercise_prescription_id,
            SetPrescriptionInput(
                body.set_type, body.tempo, body.rep_range_min, body.rep_range_max,
                body.target_weight,
            ),
        )
    except ExercisePrescriptionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise prescription not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except WeekAlreadyTrained as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session has already been completed for this week — its plan is locked.",
        ) from exc
    return _set_prescription_response(sp, target_rpe=None)


@router.patch("/set-prescriptions/{set_prescription_id}", response_model=SetPrescriptionResponse)
def edit_set_route(
    set_prescription_id: int, body: EditSetRequest, db: Session = Depends(get_db)
) -> SetPrescriptionResponse:
    try:
        sp = edit_set_in_prescription(
            db, set_prescription_id,
            set_type=body.set_type, tempo=body.tempo,
            rep_range_min=body.rep_range_min, rep_range_max=body.rep_range_max,
            target_weight=body.target_weight, clear_target_weight=body.clear_target_weight,
        )
    except SetPrescriptionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Set not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except WeekAlreadyTrained as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session has already been completed for this week — its plan is locked.",
        ) from exc
    target_rpe = sp.exercise_prescription.week.target_rpe
    return _set_prescription_response(sp, target_rpe)


@router.delete(
    "/set-prescriptions/{set_prescription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_set_route(set_prescription_id: int, db: Session = Depends(get_db)) -> None:
    try:
        remove_set_from_prescription(db, set_prescription_id)
    except SetPrescriptionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Set not found."
        ) from exc
    except MesocycleLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mesocycle is completed/abandoned and can't be edited.",
        ) from exc
    except WeekAlreadyTrained as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session has already been completed for this week — its plan is locked.",
        ) from exc


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
                    rep_range_max=s.rep_range_max, target_rpe=s.target_rpe,
                    target_weight=s.target_weight,
                )
                for s in p.sets
            ],
        )
        for p in prescriptions
    ]
