"""
Pydantic models — the *API* shape of our data. Distinct from both the
domain Athlete and the ORM AthleteModel on purpose: this is what a client
sends/receives over HTTP, and it's allowed to look different from either
(e.g. it never includes password_hash).
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AthleteResponse(BaseModel):
    id: int
    email: str
    created_at: datetime


class MuscleContributionResponse(BaseModel):
    muscle_name: str
    contribution: float


class ExerciseResponse(BaseModel):
    id: int
    name: str
    description: str
    equipment_name: str
    movement_category: str
    exercise_type: str
    notes: str
    muscles: list[MuscleContributionResponse]
    supported_set_types: list[str]
    supported_tempos: list[str]


# --- Mesocycle lifecycle ---


class WorkoutTemplateCreateRequest(BaseModel):
    name: str
    order_in_split: int
    exercise_ids: list[int] = Field(min_length=1)


class MesocycleCreateRequest(BaseModel):
    athlete_id: int
    name: str
    number_of_weeks: int = Field(ge=4, le=12)
    deload_strategy: str
    workout_templates: list[WorkoutTemplateCreateRequest] = Field(min_length=1)


class MesocycleCopyRequest(BaseModel):
    new_name: str


class MesocycleStopRequest(BaseModel):
    keep_as_history: bool


class EditTemplateExerciseRequest(BaseModel):
    exercise_id: int


class AddTemplateExerciseRequest(BaseModel):
    exercise_id: int


class WeekResponse(BaseModel):
    id: int
    week_number: int
    is_deload: bool
    target_rpe: float | None


class TemplateExerciseResponse(BaseModel):
    id: int
    exercise_id: int
    exercise_name: str
    order_in_workout: int


class WorkoutTemplateResponse(BaseModel):
    id: int
    name: str
    order_in_split: int
    exercises: list[TemplateExerciseResponse]


class MesocycleResponse(BaseModel):
    id: int
    athlete_id: int
    name: str
    number_of_weeks: int
    deload_strategy: str
    status: str
    sessions_completed: int
    current_week_number: int
    next_workout_template_id: int | None
    weeks: list[WeekResponse]
    workout_templates: list[WorkoutTemplateResponse]


class SetPrescriptionCreateRequest(BaseModel):
    set_type: str
    tempo: str
    rep_range_min: int
    rep_range_max: int
    target_weight: float | None = None


class PrescriptionCreateRequest(BaseModel):
    week_id: int
    notes: str = ""
    sets: list[SetPrescriptionCreateRequest] = Field(min_length=1)


class SetPrescriptionResponse(BaseModel):
    id: int
    set_number: int
    set_type: str
    tempo: str
    rep_range_min: int
    rep_range_max: int
    target_rpe: float | None
    target_weight: float | None


class ExercisePrescriptionResponse(BaseModel):
    id: int
    template_exercise_id: int
    week_id: int
    notes: str
    sets: list[SetPrescriptionResponse]


# --- Workout Session ---


class LogSetRequest(BaseModel):
    set_prescription_id: int | None = None
    actual_weight: float | None = None
    actual_reps: float | None = None
    actual_rpe: float | None = None
    notes: str | None = None


class SetPerformanceResponse(BaseModel):
    id: int
    set_prescription_id: int | None
    set_number: int
    actual_weight: float | None
    actual_reps: float | None
    actual_rpe: float | None
    notes: str | None


class PrescribedSetResponse(BaseModel):
    id: int
    set_number: int
    set_type: str
    tempo: str
    rep_range_min: int
    rep_range_max: int
    target_rpe: float | None
    target_weight: float | None


class PerformedExerciseResponse(BaseModel):
    id: int
    template_exercise_id: int | None
    exercise_id: int
    exercise_name: str
    order_performed: int
    prescribed_sets: list[PrescribedSetResponse]
    performed_sets: list[SetPerformanceResponse]


class WorkoutSessionResponse(BaseModel):
    id: int
    mesocycle_id: int
    week_id: int
    workout_template_id: int
    status: str
    started_at: datetime
    completed_at: datetime | None
    performed_exercises: list[PerformedExerciseResponse]
