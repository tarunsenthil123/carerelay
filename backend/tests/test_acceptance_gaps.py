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
    ChangingDetails,
    FeedingDetails,
    MedicationDetails,
    RepositioningDetails,
)
from backend.app.models.policies import (
    EventPolicy,
    EventPolicyRegistry,
)
from backend.app.services.event_repository import (
    InMemoryEventRepository,
)
from backend.app.services.event_service import (
    build_care_event,
)


def test_a_medication_confirmation():
    repo = InMemoryEventRepository()

    now = datetime.now(timezone.utc)

    draft = CareEventDraft(
        recipient_id="recipient-1",
        caregiver_id="caregiver-1",
        device_id="device-1",
        event_type=EventType.MEDICATION,
        lifecycle_status=LifecycleStatus.PROPOSED,
        care_status=CareStatus.COMPLETED,
        started_at=now,
        time_source=TimeSource.SENSOR_OBSERVED,
        source=EventSource.VISION,
        details=MedicationDetails(
            medication_name="Medication A",
            dose=10,
            dose_unit="mg",
        ),
    )

    proposed = repo.create_event(draft)

    confirmed = repo.confirm_event(
        proposed.id,
        verification_method=VerificationMethod.CONFIRM_BUTTON,
        verified_at=now,
    )

    assert confirmed.lifecycle_status == LifecycleStatus.CONFIRMED
    assert confirmed.risk_level == RiskLevel.HIGH
    assert confirmed.verification_method == VerificationMethod.CONFIRM_BUTTON


def test_e_invalid_event_type_is_rejected():
    with pytest.raises(ValidationError):
        CareEventDraft(
            recipient_id="recipient-1",
            event_type="not_a_real_event",
            lifecycle_status=LifecycleStatus.PROPOSED,
            care_status=CareStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            time_source=TimeSource.SENSOR_OBSERVED,
            source=EventSource.VISION,
            details=FeedingDetails(
                feeding_type="tube",
            ),
        )


def test_f_expired_amendment_keeps_confirmed_parent_effective():
    repo = InMemoryEventRepository()

    base_time = datetime(
        2026,
        11,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    parent_draft = CareEventDraft(
        recipient_id="recipient-1",
        caregiver_id="caregiver-1",
        device_id="device-1",
        event_type=EventType.REPOSITIONING,
        lifecycle_status=LifecycleStatus.CONFIRMED,
        care_status=CareStatus.COMPLETED,
        started_at=base_time,
        time_source=TimeSource.CAREGIVER_REPORTED_EXACT,
        source=EventSource.VOICE,
        details=RepositioningDetails(
            to_position="left_side",
        ),
        verified_at=base_time,
        verification_method=VerificationMethod.MANUAL_ENTRY,
    )

    parent = repo.create_event(
        parent_draft,
        now=base_time,
    )

    amendment_draft = CareEventDraft(
        recipient_id="recipient-1",
        caregiver_id="caregiver-1",
        device_id="device-1",
        event_type=EventType.CHANGING,
        lifecycle_status=LifecycleStatus.PROPOSED,
        care_status=CareStatus.COMPLETED,
        started_at=base_time,
        time_source=TimeSource.SENSOR_OBSERVED,
        source=EventSource.VISION,
        details=ChangingDetails(
            change_type="diaper",
            condition="wet",
        ),
    )

    amendment = repo.amend_event(
        parent.id,
        amendment_draft,
        now=base_time,
    )

    repo.expire_overdue_proposals(
        now=base_time + timedelta(seconds=301)
    )

    expired = repo.get_event(amendment.id)

    assert expired.lifecycle_status == LifecycleStatus.EXPIRED

    timeline = repo.get_effective_timeline(
        "recipient-1",
        now=base_time + timedelta(seconds=301),
    )

    assert timeline == [parent]


def test_i_late_approximate_event_time_is_valid():
    now = datetime.now(timezone.utc)
    reported_time = now - timedelta(hours=2)

    draft = CareEventDraft(
        recipient_id="recipient-1",
        caregiver_id="caregiver-1",
        device_id="device-1",
        event_type=EventType.FEEDING,
        lifecycle_status=LifecycleStatus.CONFIRMED,
        care_status=CareStatus.COMPLETED,
        started_at=reported_time,
        time_source=TimeSource.CAREGIVER_REPORTED_APPROXIMATE,
        source=EventSource.VOICE,
        details=FeedingDetails(
            feeding_type="tube",
            quantity=250,
            unit="mL",
        ),
        verified_at=now,
        verification_method=VerificationMethod.MANUAL_ENTRY,
    )

    event = build_care_event(
        draft,
        now=now,
    )

    assert event.started_at == reported_time
    assert event.created_at == now
    assert (
        event.time_source
        == TimeSource.CAREGIVER_REPORTED_APPROXIMATE
    )


def test_o_manual_high_risk_medication_event_is_valid():
    now = datetime.now(timezone.utc)

    draft = CareEventDraft(
        recipient_id="recipient-1",
        caregiver_id="caregiver-1",
        device_id="device-1",
        event_type=EventType.MEDICATION,
        lifecycle_status=LifecycleStatus.CONFIRMED,
        care_status=CareStatus.COMPLETED,
        started_at=now,
        time_source=TimeSource.CAREGIVER_REPORTED_EXACT,
        source=EventSource.VOICE,
        details=MedicationDetails(
            medication_name="Medication A",
            dose=10,
            dose_unit="mg",
        ),
        verified_at=now,
        verification_method=VerificationMethod.MANUAL_ENTRY,
    )

    event = build_care_event(draft)

    assert event.risk_level == RiskLevel.HIGH
    assert event.lifecycle_status == LifecycleStatus.CONFIRMED


def test_p_test_only_repositioning_policy_can_auto_log():
    test_registry = EventPolicyRegistry(
        {
            EventType.REPOSITIONING: EventPolicy(
                risk_level=RiskLevel.LOW,
                auto_log_eligible=True,
                proposal_timeout_seconds=300,
            )
        }
    )

    now = datetime.now(timezone.utc)

    draft = CareEventDraft(
        recipient_id="recipient-1",
        device_id="device-1",
        event_type=EventType.REPOSITIONING,
        lifecycle_status=LifecycleStatus.CONFIRMED,
        care_status=CareStatus.COMPLETED,
        started_at=now,
        time_source=TimeSource.SENSOR_OBSERVED,
        source=EventSource.VISION,
        details=RepositioningDetails(
            to_position="left_side",
        ),
        verified_at=now,
        verification_method=VerificationMethod.AUTO_LOGGED,
    )

    event = build_care_event(
        draft,
        registry=test_registry,
    )

    assert event.risk_level == RiskLevel.LOW
    assert event.verification_method == VerificationMethod.AUTO_LOGGED


def test_q_evaluation_metadata_is_optional():
    now = datetime.now(timezone.utc)

    draft = CareEventDraft(
        recipient_id="recipient-1",
        caregiver_id="caregiver-1",
        device_id="device-1",
        event_type=EventType.FEEDING,
        lifecycle_status=LifecycleStatus.CONFIRMED,
        care_status=CareStatus.COMPLETED,
        started_at=now,
        time_source=TimeSource.CAREGIVER_REPORTED_EXACT,
        source=EventSource.VOICE,
        details=FeedingDetails(
            feeding_type="tube",
        ),
        verified_at=now,
        verification_method=VerificationMethod.MANUAL_ENTRY,
    )

    event = build_care_event(draft)

    assert event.evaluation_metadata is None


def test_v_human_source_cannot_auto_log_even_when_policy_is_eligible():
    test_registry = EventPolicyRegistry(
        {
            EventType.FEEDING: EventPolicy(
                risk_level=RiskLevel.LOW,
                auto_log_eligible=True,
                proposal_timeout_seconds=300,
            )
        }
    )

    now = datetime.now(timezone.utc)

    draft = CareEventDraft(
        recipient_id="recipient-1",
        caregiver_id="caregiver-1",
        device_id="device-1",
        event_type=EventType.FEEDING,
        lifecycle_status=LifecycleStatus.CONFIRMED,
        care_status=CareStatus.COMPLETED,
        started_at=now,
        time_source=TimeSource.CAREGIVER_REPORTED_EXACT,
        source=EventSource.VOICE,
        details=FeedingDetails(
            feeding_type="tube",
        ),
        verified_at=now,
        verification_method=VerificationMethod.AUTO_LOGGED,
    )

    with pytest.raises(ValueError):
        build_care_event(
            draft,
            registry=test_registry,
        )


@pytest.mark.parametrize(
    ("source", "method"),
    [
        (
            EventSource.VOICE,
            VerificationMethod.CONFIRM_BUTTON,
        ),
        (
            EventSource.VISION,
            VerificationMethod.CONFIRM_BUTTON,
        ),
        (
            EventSource.VOICE,
            VerificationMethod.DASHBOARD,
        ),
        (
            EventSource.VISION,
            VerificationMethod.DASHBOARD,
        ),
    ],
)
def test_x_confirm_and_dashboard_support_human_and_ai_sources(
    source,
    method,
):
    now = datetime.now(timezone.utc)

    draft = CareEventDraft(
        recipient_id="recipient-1",
        caregiver_id="caregiver-1",
        device_id="device-1",
        event_type=EventType.FEEDING,
        lifecycle_status=LifecycleStatus.CONFIRMED,
        care_status=CareStatus.COMPLETED,
        started_at=now,
        time_source=TimeSource.SENSOR_OBSERVED,
        source=source,
        details=FeedingDetails(
            feeding_type="tube",
        ),
        verified_at=now,
        verification_method=method,
    )

    event = build_care_event(draft)

    assert event.verification_method == method
    assert event.lifecycle_status == LifecycleStatus.CONFIRMED