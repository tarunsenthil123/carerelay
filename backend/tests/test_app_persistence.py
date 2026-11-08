from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.database.base import Base
from backend.app.database.session import (
    SessionLocal,
    engine,
)
from backend.app.main import create_app
from backend.app.services.postgres_event_repository import (
    PostgreSQLEventRepository,
)


def reset_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_app_uses_postgres_repository_by_default():
    reset_database()

    test_app = create_app()

    assert isinstance(
        test_app.state.event_repository,
        PostgreSQLEventRepository,
    )


def test_api_event_survives_repository_recreation():
    reset_database()

    test_app = create_app()
    client = TestClient(test_app)

    now = datetime.now(timezone.utc)

    response = client.post(
        "/events",
        json={
            "recipient_id": "recipient-1",
            "caregiver_id": "caregiver-1",
            "device_id": "device-1",
            "event_type": "feeding",
            "lifecycle_status": "confirmed",
            "care_status": "completed",
            "started_at": now.isoformat(),
            "time_source": "caregiver_reported_exact",
            "source": "voice",
            "details": {
                "feeding_type": "tube",
                "quantity": 250,
                "unit": "mL",
            },
            "verified_at": now.isoformat(),
            "verification_method": "manual_entry",
        },
    )

    assert response.status_code == 201

    created = response.json()

    # Simulate the repository being recreated, as would happen
    # after an application/server restart.
    test_app.state.event_repository = (
        PostgreSQLEventRepository(
            session_factory=SessionLocal
        )
    )

    timeline_response = client.get(
        "/events/effective/recipient-1"
    )

    assert timeline_response.status_code == 200

    timeline = timeline_response.json()

    assert len(timeline) == 1
    assert timeline[0]["id"] == created["id"]
    assert timeline[0]["event_type"] == "feeding"