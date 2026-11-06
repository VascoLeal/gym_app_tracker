from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.exercises import router as exercises_router
from app.api.routes.mesocycles import router as mesocycles_router
from app.api.routes.sessions import router as sessions_router
from app.config import get_settings

app = FastAPI(title="Training App API")

# CORS is allow-listed by exact origin, not "*", since the API sends
# credentials-adjacent data (Bearer tokens). See cors_allowed_origins in
# app/config.py.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(exercises_router)
app.include_router(mesocycles_router)
app.include_router(sessions_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple liveness check — also handy for confirming the server started."""
    return {"status": "ok"}
