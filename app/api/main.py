from fastapi import FastAPI

from app.api.routes.auth import router as auth_router

app = FastAPI(title="Training App API")

app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple liveness check — also handy for confirming the server started."""
    return {"status": "ok"}
