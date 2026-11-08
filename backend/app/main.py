from fastapi import FastAPI

from backend.app.database.session import (
    initialize_database,
)
from backend.app.routes.events import (
    router as events_router,
)
from backend.app.services.postgres_event_repository import (
    PostgreSQLEventRepository,
)


def create_app(
    event_repository=None,
) -> FastAPI:
    """
    Build the CareRelay FastAPI application.

    Production defaults to PostgreSQL persistence.
    Tests may inject a different repository when isolation is useful.
    """

    initialize_database()

    app = FastAPI(
        title="CareRelay API",
        description=(
            "Backend API for the CareRelay "
            "home-care handoff system."
        ),
        version="0.1.0",
    )

    if event_repository is None:
        event_repository = (
            PostgreSQLEventRepository()
        )

    app.state.event_repository = (
        event_repository
    )

    app.include_router(
        events_router
    )

    @app.get("/")
    def root():
        return {
            "message":
                "CareRelay API is running",
            "status": "ok",
        }

    @app.get("/health")
    def health():
        return {
            "status": "healthy"
        }

    return app


app = create_app()