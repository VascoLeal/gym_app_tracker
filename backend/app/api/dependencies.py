"""
FastAPI dependency that protects a route: requires a valid Bearer token
and hands the route the actual AthleteModel it belongs to. Use as:

    @router.get("/something")
    def route(athlete: AthleteModel = Depends(get_current_athlete)):
        ...

This is what makes "per-user data isolation enforced at the query level"
(the constitution's security baseline) actually real, rather than trusting
whatever athlete_id a client happens to send.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth_tokens import InvalidToken, decode_access_token
from app.infrastructure.database import get_db
from app.infrastructure.models import AthleteModel

_bearer_scheme = HTTPBearer()


def get_current_athlete(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> AthleteModel:
    try:
        athlete_id = decode_access_token(credentials.credentials)
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    athlete = db.query(AthleteModel).filter(AthleteModel.id == athlete_id).first()
    if athlete is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Athlete no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return athlete
