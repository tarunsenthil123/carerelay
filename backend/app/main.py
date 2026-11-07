from fastapi import FastAPI

from backend.app.routes.events import (
    router as events_router,
)
from backend.app.services.event_repository import (
    InMemoryEventRepository,
)


app = FastAPI(
    title="CareRelay API",
    description=(
        "Backend API for the CareRelay "
        "home-care handoff system."
    ),
    version="0.1.0",
)


app.state.event_repository = (
    InMemoryEventRepository()
)


app.include_router(
    events_router
)


@app.get("/")
def root():
    return {
        "message": "CareRelay API is running",
        "status": "ok",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }