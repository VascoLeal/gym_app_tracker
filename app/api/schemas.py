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


# --- Program / Mesocycle / Prescription ---


class ProgramCreateRequest(BaseModel):
    athlete_id: int
    name: str
    description: str = ""


class ProgramResponse(BaseModel):
    id: int
    athlete_id: int
    name: str
    description: str


class WeekCreateRequest(BaseModel):
    week_number: int
    is_deload: bool = False


class WorkoutTemplateCreateRequest(BaseModel):
    name: str
    order_in_split: int
    exercise_ids: list[int] = Field(min_length=1)


class MesocycleCreateRequest(BaseModel):
    name: str
    weeks: list[WeekCreateRequest] = Field(min_length=1)
    workout_templates: list[WorkoutTemplateCreateRequest] = Field(min_length=1)


class WeekResponse(BaseModel):
    id: int
    week_number: int
    is_deload: bool


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
    program_id: int
    name: str
    weeks: list[WeekResponse]
    workout_templates: list[WorkoutTemplateResponse]


class SetPrescriptionCreateRequest(BaseModel):
    set_type: str
    tempo: str
    rep_range_min: int
    rep_range_max: int
    target_rir: float | None = None


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
    target_rir: float | None


class ExercisePrescriptionResponse(BaseModel):
    id: int
    template_exercise_id: int
    week_id: int
    notes: str
    sets: list[SetPrescriptionResponse]
