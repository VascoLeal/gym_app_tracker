from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.exercises import router as exercises_router
from app.api.routes.programs import router as programs_router

app = FastAPI(title="Training App API")

app.include_router(auth_router)
app.include_router(exercises_router)
app.include_router(programs_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple liveness check — also handy for confirming the server started."""
    return {"status": "ok"}
