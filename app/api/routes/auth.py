from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import AthleteResponse, LoginRequest, RegisterRequest
from app.application.auth_service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    authenticate_athlete,
    register_athlete,
)
from app.infrastructure.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=AthleteResponse, status_code=status.HTTP_201_CREATED
)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> AthleteResponse:
    try:
        athlete = register_athlete(db, body.email, body.password)
    except EmailAlreadyRegistered as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        ) from exc

    return AthleteResponse(
        id=athlete.id, email=athlete.email, created_at=athlete.created_at
    )


@router.post("/login", response_model=AthleteResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> AthleteResponse:
    try:
        athlete = authenticate_athlete(db, body.email, body.password)
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        ) from exc

    return AthleteResponse(
        id=athlete.id, email=athlete.email, created_at=athlete.created_at
    )
