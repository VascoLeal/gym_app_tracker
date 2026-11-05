"""
JWT access tokens. v1 scope, deliberately: ONE token per login, no refresh
rotation — simpler to build and reason about while learning the frontend
side of this from zero. Revisit if/when a real security hardening pass
happens; see docs/project-brief.md decisions log.

HS256 (symmetric signing) is enough here — there's a single backend
verifying its own tokens, no need for the asymmetric-key complexity RS256
exists for (multiple independent services verifying tokens they didn't
issue).
"""

from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings

ALGORITHM = "HS256"


def create_access_token(athlete_id: int) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiry_days)
    payload = {"sub": str(athlete_id), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


class InvalidToken(Exception):
    pass


def decode_access_token(token: str) -> int:
    """Returns the athlete_id encoded in the token, or raises InvalidToken
    for anything wrong with it — expired, tampered, malformed."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidToken() from exc

    try:
        return int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidToken() from exc
