from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.database.base import Base
from backend.app.database.models import CareEventRecord
from backend.app.database.session import (
    SessionLocal,
    engine,
)
from backend.app.main import create_app


def reset_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_confirmed_event_survives_new_app_instance():
    reset_database()

    app_one = create_app()
    client_one = TestClient(app_one)

    now = datetime.now(timezone.utc)

    created_response = client_one.post(
        "/events",
        json={
            "recipient_id": "recipient-1",
            "caregiver_id": "caregiver-1",
            "device_id": "device-1",
            "event_type": "feeding",
            "lifecycle_status": "proposed",
            "care_status": "completed",
            "started_at": now.isoformat(),
            "time_source": "sensor_observed",
            "source": "vision",
            "details": {
                "feeding_type": "tube",
                "quantity": 250,
                "unit": "mL",
            },
        },
    )

    assert created_response.status_code == 201

    created = created_response.json()

    confirm_response = client_one.post(
        f"/events/{created['id']}/confirm",
        json={
            "verification_method": "confirm_button",
            "verified_at": now.isoformat(),
        },
    )

    assert confirm_response.status_code == 200

    # Simulate a new application/server instance.
    app_two = create_app()
    client_two = TestClient(app_two)

    timeline_response = client_two.get(
        "/events/effective/recipient-1"
    )

    assert timeline_response.status_code == 200

    timeline = timeline_response.json()

    assert len(timeline) == 1
    assert timeline[0]["id"] == created["id"]
    assert timeline[0]["lifecycle_status"] == "confirmed"


def test_denied_event_remains_non_effective_after_new_app_instance():
    reset_database()

    app_one = create_app()
    client_one = TestClient(app_one)

    now = datetime.now(timezone.utc)

    created = client_one.post(
        "/events",
        json={
            "recipient_id": "recipient-1",
            "caregiver_id": "caregiver-1",
            "device_id": "device-1",
            "event_type": "feeding",
            "lifecycle_status": "proposed",
            "care_status": "completed",
            "started_at": now.isoformat(),
            "time_source": "sensor_observed",
            "source": "vision",
            "details": {
                "feeding_type": "tube",
            },
        },
    ).json()

    deny_response = client_one.post(
        f"/events/{created['id']}/deny"
    )

    assert deny_response.status_code == 200

    app_two = create_app()
    client_two = TestClient(app_two)

    timeline_response = client_two.get(
        "/events/effective/recipient-1"
    )

    assert timeline_response.status_code == 200
    assert timeline_response.json() == []


def test_confirmed_amendment_survives_new_app_instance():
    reset_database()

    app_one = create_app()
    client_one = TestClient(app_one)

    now = datetime.now(timezone.utc)

    parent_response = client_one.post(
        "/events",
        json={
            "recipient_id": "recipient-1",
            "caregiver_id": "caregiver-1",
            "device_id": "device-1",
            "event_type": "repositioning",
            "lifecycle_status": "confirmed",
            "care_status": "completed",
            "started_at": now.isoformat(),
            "time_source": "caregiver_reported_exact",
            "source": "voice",
            "details": {
                "to_position": "left_side",
            },
            "verified_at": now.isoformat(),
            "verification_method": "manual_entry",
        },
    )

    assert parent_response.status_code == 201

    parent = parent_response.json()

    correction_response = client_one.post(
        f"/events/{parent['id']}/amend",
        json={
            "recipient_id": "recipient-1",
            "caregiver_id": "caregiver-1",
            "device_id": "device-1",
            "event_type": "changing",
            "lifecycle_status": "confirmed",
            "care_status": "completed",
            "started_at": now.isoformat(),
            "time_source": "caregiver_reported_exact",
            "source": "voice",
            "details": {
                "change_type": "diaper",
                "condition": "wet",
            },
            "verified_at": now.isoformat(),
            "verification_method": "manual_entry",
        },
    )

    assert correction_response.status_code == 201

    correction = correction_response.json()

    app_two = create_app()
    client_two = TestClient(app_two)

    timeline_response = client_two.get(
        "/events/effective/recipient-1"
    )

    assert timeline_response.status_code == 200

    timeline = timeline_response.json()

    assert len(timeline) == 1
    assert timeline[0]["id"] == correction["id"]
    assert timeline[0]["event_type"] == "changing"
    assert timeline[0]["amends_event_id"] == parent["id"]


def test_invalid_auto_logged_event_is_not_persisted():
    reset_database()

    app = create_app()
    client = TestClient(app)

    now = datetime.now(timezone.utc)

    response = client.post(
        "/events",
        json={
            "recipient_id": "recipient-1",
            "device_id": "device-1",
            "event_type": "repositioning",
            "lifecycle_status": "confirmed",
            "care_status": "completed",
            "started_at": now.isoformat(),
            "time_source": "sensor_observed",
            "source": "vision",
            "details": {
                "to_position": "left_side",
            },
            "verified_at": now.isoformat(),
            "verification_method": "auto_logged",
        },
    )

    assert response.status_code == 400

    with SessionLocal() as session:
        count = session.execute(
            select(
                func.count()
            ).select_from(
                CareEventRecord
            )
        ).scalar_one()

    assert count == 0