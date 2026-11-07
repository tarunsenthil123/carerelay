from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.event_repository import (
    InMemoryEventRepository,
)


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_event_repository():
    """
    Give every API test a clean isolated in-memory repository.
    """

    app.state.event_repository = InMemoryEventRepository()


def details_for(event_type: str):
    if event_type == "feeding":
        return {
            "feeding_type": "tube",
            "quantity": 250,
            "unit": "mL",
        }

    if event_type == "medication":
        return {
            "medication_name": "Medication A",
            "dose": 10,
            "dose_unit": "mg",
        }

    if event_type == "changing":
        return {
            "change_type": "diaper",
            "condition": "wet",
        }

    if event_type == "repositioning":
        return {
            "to_position": "left_side",
        }

    if event_type == "care_note":
        return {
            "category": "general",
            "observation": "Care note",
        }

    raise ValueError(
        f"Unsupported event type: {event_type}"
    )


def make_payload(
    event_type: str = "feeding",
    *,
    lifecycle_status: str = "proposed",
    source: str = "vision",
):
    now = datetime.now(timezone.utc)

    payload = {
        "recipient_id": "recipient-1",
        "caregiver_id": "caregiver-1",
        "device_id": "device-1",
        "event_type": event_type,
        "lifecycle_status": lifecycle_status,
        "care_status": "completed",
        "started_at": now.isoformat(),
        "time_source": "sensor_observed",
        "source": source,
        "details": details_for(event_type),
    }

    if lifecycle_status == "confirmed":
        payload["verified_at"] = now.isoformat()

        if source in {
            "manual",
            "dashboard",
            "voice",
        }:
            payload[
                "verification_method"
            ] = "manual_entry"
        else:
            payload[
                "verification_method"
            ] = "confirm_button"

    return payload


def test_create_event_api_derives_high_risk():
    response = client.post(
        "/events",
        json=make_payload(),
    )

    assert response.status_code == 201

    event = response.json()

    assert event["event_type"] == "feeding"
    assert event["risk_level"] == "high"
    assert event["lifecycle_status"] == "proposed"


def test_confirm_event_api():
    created = client.post(
        "/events",
        json=make_payload(),
    ).json()

    response = client.post(
        f"/events/{created['id']}/confirm",
        json={
            "verification_method": "confirm_button",
            "verified_at": datetime.now(
                timezone.utc
            ).isoformat(),
        },
    )

    assert response.status_code == 200

    event = response.json()

    assert event["id"] == created["id"]
    assert event["lifecycle_status"] == "confirmed"
    assert event[
        "verification_method"
    ] == "confirm_button"


def test_deny_event_api():
    created = client.post(
        "/events",
        json=make_payload(),
    ).json()

    response = client.post(
        f"/events/{created['id']}/deny"
    )

    assert response.status_code == 200

    assert (
        response.json()["lifecycle_status"]
        == "denied"
    )


def test_amendment_and_effective_timeline_api():
    original_payload = make_payload(
        event_type="repositioning",
        lifecycle_status="confirmed",
        source="voice",
    )

    original_payload[
        "time_source"
    ] = "caregiver_reported_exact"

    original = client.post(
        "/events",
        json=original_payload,
    ).json()

    correction_payload = make_payload(
        event_type="changing",
        lifecycle_status="confirmed",
        source="voice",
    )

    correction_payload[
        "time_source"
    ] = "caregiver_reported_exact"

    amendment_response = client.post(
        f"/events/{original['id']}/amend",
        json=correction_payload,
    )

    assert amendment_response.status_code == 201

    correction = amendment_response.json()

    assert (
        correction["amends_event_id"]
        == original["id"]
    )

    timeline_response = client.get(
        "/events/effective/recipient-1"
    )

    assert timeline_response.status_code == 200

    timeline = timeline_response.json()

    assert len(timeline) == 1
    assert timeline[0]["id"] == correction["id"]
    assert timeline[0]["event_type"] == "changing"


def test_production_auto_log_is_rejected_through_api():
    payload = make_payload(
        event_type="repositioning",
        lifecycle_status="confirmed",
        source="vision",
    )

    payload[
        "verification_method"
    ] = "auto_logged"

    response = client.post(
        "/events",
        json=payload,
    )

    assert response.status_code == 400


def test_missing_amendment_target_is_rejected_through_api():
    correction_payload = make_payload(
        event_type="changing",
    )

    response = client.post(
        "/events/00000000-0000-0000-0000-000000000001/amend",
        json=correction_payload,
    )

    assert response.status_code == 400