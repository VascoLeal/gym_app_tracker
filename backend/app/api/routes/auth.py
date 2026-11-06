from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_athlete
from app.api.schemas import AthleteResponse, LoginRequest, LoginResponse, RegisterRequest
from app.application.auth_service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    authenticate_athlete,
    register_athlete,
)
from app.auth_tokens import create_access_token
from app.config import Settings, get_settings
from app.infrastructure.database import get_db
from app.infrastructure.models import AthleteModel

router = APIRouter(prefix="/auth", tags=["auth"])


def _athlete_response(athlete) -> AthleteResponse:
    return AthleteResponse(
        id=athlete.id, email=athlete.email, created_at=athlete.created_at
    )


@router.post(
    "/register", response_model=AthleteResponse, status_code=status.HTTP_201_CREATED
)
def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AthleteResponse:
    if not settings.can_register(body.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is closed.",
        )

    try:
        athlete = register_athlete(db, body.email, body.password)
    except EmailAlreadyRegistered as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        ) from exc

    return _athlete_response(athlete)


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        athlete = authenticate_athlete(db, body.email, body.password)
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        ) from exc

    token = create_access_token(athlete.id)
    return LoginResponse(access_token=token, athlete=_athlete_response(athlete))


@router.get("/me", response_model=AthleteResponse)
def me(current_athlete: AthleteModel = Depends(get_current_athlete)) -> AthleteResponse:
    """First protected route — proves a token round-trips correctly end
    to end: issued at login, sent back as a Bearer header, verified here."""
    return _athlete_response(current_athlete)
