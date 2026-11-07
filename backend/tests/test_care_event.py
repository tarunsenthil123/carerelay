from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.app.models.enums import (
    CareStatus,
    EventSource,
    EventType,
    LifecycleStatus,
    RiskLevel,
    TimeSource,
    VerificationMethod,
)
from backend.app.models.events import (
    CareEventDraft,
    FeedingDetails,
    MedicationDetails,
)
from backend.app.models.policies import (
    EventPolicy,
    EventPolicyRegistry,
)
from backend.app.services.event_service import build_care_event


def make_feeding_draft(**overrides):
    data = {
        "recipient_id": "recipient-1",
        "caregiver_id": "caregiver-1",
        "device_id": "device-1",
        "event_type": EventType.FEEDING,
        "lifecycle_status": LifecycleStatus.PROPOSED,
        "care_status": CareStatus.COMPLETED,
        "started_at": datetime.now(timezone.utc),
        "time_source": TimeSource.SENSOR_OBSERVED,
        "source": EventSource.VISION,
        "confidence": 0.91,
        "details": FeedingDetails(
            feeding_type="tube",
            food_or_formula="Formula A",
            quantity=250,
            unit="mL",
            route="g_tube",
        ),
    }

    data.update(overrides)
    return CareEventDraft(**data)


def test_production_policy_derives_high_risk():
    draft = make_feeding_draft()

    event = build_care_event(draft)

    assert event.risk_level == RiskLevel.HIGH


def test_event_payload_cannot_supply_risk_level():
    with pytest.raises(ValidationError):
        CareEventDraft(
            recipient_id="recipient-1",
            caregiver_id="caregiver-1",
            device_id="device-1",
            event_type=EventType.FEEDING,
            lifecycle_status=LifecycleStatus.PROPOSED,
            care_status=CareStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            time_source=TimeSource.SENSOR_OBSERVED,
            source=EventSource.VISION,
            details=FeedingDetails(
                feeding_type="tube",
            ),
            risk_level=RiskLevel.LOW,
        )


def test_confirmed_event_requires_verified_at():
    draft = make_feeding_draft(
        lifecycle_status=LifecycleStatus.CONFIRMED,
        verification_method=VerificationMethod.CONFIRM_BUTTON,
    )

    with pytest.raises(ValueError):
        build_care_event(draft)


def test_confirmed_event_requires_verification_method():
    draft = make_feeding_draft(
        lifecycle_status=LifecycleStatus.CONFIRMED,
        verified_at=datetime.now(timezone.utc),
    )

    with pytest.raises(ValueError):
        build_care_event(draft)


def test_human_voice_manual_entry_is_valid():
    draft = make_feeding_draft(
        lifecycle_status=LifecycleStatus.CONFIRMED,
        source=EventSource.VOICE,
        time_source=TimeSource.CAREGIVER_REPORTED_EXACT,
        verified_at=datetime.now(timezone.utc),
        verification_method=VerificationMethod.MANUAL_ENTRY,
    )

    event = build_care_event(draft)

    assert event.lifecycle_status == LifecycleStatus.CONFIRMED
    assert event.risk_level == RiskLevel.HIGH
    assert event.verification_method == VerificationMethod.MANUAL_ENTRY


def test_ai_source_cannot_use_manual_entry():
    draft = make_feeding_draft(
        lifecycle_status=LifecycleStatus.CONFIRMED,
        source=EventSource.VISION,
        verified_at=datetime.now(timezone.utc),
        verification_method=VerificationMethod.MANUAL_ENTRY,
    )

    with pytest.raises(ValueError):
        build_care_event(draft)


def test_production_ai_event_cannot_auto_log():
    draft = make_feeding_draft(
        lifecycle_status=LifecycleStatus.CONFIRMED,
        source=EventSource.VISION,
        verified_at=datetime.now(timezone.utc),
        verification_method=VerificationMethod.AUTO_LOGGED,
    )

    with pytest.raises(ValueError):
        build_care_event(draft)


def test_test_only_low_risk_eligible_ai_event_can_auto_log():
    test_registry = EventPolicyRegistry(
        {
            EventType.FEEDING: EventPolicy(
                risk_level=RiskLevel.LOW,
                auto_log_eligible=True,
                proposal_timeout_seconds=300,
            )
        }
    )

    draft = make_feeding_draft(
        lifecycle_status=LifecycleStatus.CONFIRMED,
        source=EventSource.VISION,
        verified_at=datetime.now(timezone.utc),
        verification_method=VerificationMethod.AUTO_LOGGED,
    )

    event = build_care_event(
        draft,
        registry=test_registry,
    )

    assert event.risk_level == RiskLevel.LOW
    assert event.verification_method == VerificationMethod.AUTO_LOGGED


def test_end_time_cannot_precede_start_time():
    start = datetime.now(timezone.utc)

    draft = make_feeding_draft(
        started_at=start,
        ended_at=start - timedelta(minutes=10),
    )

    with pytest.raises(ValueError):
        build_care_event(draft)


def test_naive_started_at_is_rejected():
    draft = make_feeding_draft(
        started_at=datetime.now(),
    )

    with pytest.raises(ValueError):
        build_care_event(draft)


def test_materially_future_started_at_is_rejected():
    draft = make_feeding_draft(
        started_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    with pytest.raises(ValueError):
        build_care_event(draft)


def test_event_type_must_match_details_schema():
    with pytest.raises(ValidationError):
        CareEventDraft(
            recipient_id="recipient-1",
            caregiver_id="caregiver-1",
            device_id="device-1",
            event_type=EventType.FEEDING,
            lifecycle_status=LifecycleStatus.PROPOSED,
            care_status=CareStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            time_source=TimeSource.SENSOR_OBSERVED,
            source=EventSource.VISION,
            details=MedicationDetails(
                medication_name="Medication A",
                dose=10,
                dose_unit="mg",
            ),
        )