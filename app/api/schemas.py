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
