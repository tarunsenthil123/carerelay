from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

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
    CareNoteDetails,
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


def details_for(event_type: EventType):
    if event_type == EventType.FEEDING:
        return FeedingDetails(
            feeding_type="tube",
            quantity=250,
            unit="mL",
        )

    if event_type == EventType.MEDICATION:
        return MedicationDetails(
            medication_name="Medication A",
            dose=10,
            dose_unit="mg",
        )

    if event_type == EventType.CHANGING:
        return ChangingDetails(
            change_type="diaper",
            condition="wet",
        )

    if event_type == EventType.REPOSITIONING:
        return RepositioningDetails(
            to_position="left_side",
        )

    if event_type == EventType.CARE_NOTE:
        return CareNoteDetails(
            category="general",
            observation="Care note",
        )

    raise ValueError(f"Unsupported event type: {event_type}")


def make_draft(
    event_type: EventType,
    *,
    recipient_id: str = "recipient-1",
    lifecycle_status: LifecycleStatus = LifecycleStatus.PROPOSED,
    source: EventSource = EventSource.VISION,
    started_at: datetime | None = None,
):
    data = {
        "recipient_id": recipient_id,
        "caregiver_id": "caregiver-1",
        "device_id": "device-1",
        "event_type": event_type,
        "lifecycle_status": lifecycle_status,
        "care_status": CareStatus.COMPLETED,
        "started_at": started_at or datetime.now(timezone.utc),
        "time_source": TimeSource.SENSOR_OBSERVED,
        "source": source,
        "details": details_for(event_type),
    }

    if lifecycle_status == LifecycleStatus.CONFIRMED:
        data["verified_at"] = datetime.now(timezone.utc)

        if source.is_human_initiated:
            data["verification_method"] = VerificationMethod.MANUAL_ENTRY
        else:
            data["verification_method"] = VerificationMethod.CONFIRM_BUTTON

    return CareEventDraft(**data)


def test_confirm_event_preserves_event_identity():
    repo = InMemoryEventRepository()

    event = repo.create_event(
        make_draft(EventType.FEEDING)
    )

    original_id = event.id
    original_created_at = event.created_at

    confirmed = repo.confirm_event(
        event.id,
        verification_method=VerificationMethod.CONFIRM_BUTTON,
        verified_at=datetime.now(timezone.utc),
    )

    assert confirmed.id == original_id
    assert confirmed.created_at == original_created_at
    assert confirmed.lifecycle_status == LifecycleStatus.CONFIRMED


def test_basic_amendment_returns_confirmed_child():
    repo = InMemoryEventRepository()

    original = repo.create_event(
        make_draft(
            EventType.REPOSITIONING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        )
    )

    correction = repo.amend_event(
        original.id,
        make_draft(
            EventType.CHANGING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        ),
    )

    timeline = repo.get_effective_timeline("recipient-1")

    assert correction.amends_event_id == original.id
    assert timeline == [correction]


def test_amendment_chain_returns_latest_confirmed_event():
    repo = InMemoryEventRepository()

    event_a = repo.create_event(
        make_draft(
            EventType.REPOSITIONING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        )
    )

    event_b = repo.amend_event(
        event_a.id,
        make_draft(
            EventType.CHANGING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        ),
    )

    event_c = repo.amend_event(
        event_b.id,
        make_draft(
            EventType.CARE_NOTE,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        ),
    )

    timeline = repo.get_effective_timeline("recipient-1")

    assert timeline == [event_c]


def test_denied_false_positive_is_not_effective():
    repo = InMemoryEventRepository()

    proposed = repo.create_event(
        make_draft(EventType.FEEDING)
    )

    repo.deny_event(proposed.id)

    timeline = repo.get_effective_timeline("recipient-1")

    assert timeline == []


def test_pending_amendment_keeps_confirmed_parent_effective():
    repo = InMemoryEventRepository()

    original = repo.create_event(
        make_draft(
            EventType.REPOSITIONING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        )
    )

    repo.amend_event(
        original.id,
        make_draft(EventType.CHANGING),
    )

    timeline = repo.get_effective_timeline("recipient-1")

    assert timeline == [original]


def test_denied_amendment_keeps_confirmed_parent_effective():
    repo = InMemoryEventRepository()

    original = repo.create_event(
        make_draft(
            EventType.REPOSITIONING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        )
    )

    amendment = repo.amend_event(
        original.id,
        make_draft(EventType.CHANGING),
    )

    repo.deny_event(amendment.id)

    timeline = repo.get_effective_timeline("recipient-1")

    assert timeline == [original]


def test_denied_original_can_have_confirmed_correction():
    repo = InMemoryEventRepository()

    original = repo.create_event(
        make_draft(EventType.REPOSITIONING)
    )

    repo.deny_event(original.id)

    correction = repo.amend_event(
        original.id,
        make_draft(
            EventType.CHANGING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        ),
    )

    timeline = repo.get_effective_timeline("recipient-1")

    assert timeline == [correction]


def test_second_active_amendment_against_same_event_is_rejected():
    repo = InMemoryEventRepository()

    original = repo.create_event(
        make_draft(
            EventType.REPOSITIONING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        )
    )

    repo.amend_event(
        original.id,
        make_draft(EventType.CHANGING),
    )

    with pytest.raises(ValueError):
        repo.amend_event(
            original.id,
            make_draft(EventType.CARE_NOTE),
        )


def test_missing_amendment_target_is_rejected():
    repo = InMemoryEventRepository()

    with pytest.raises(ValueError):
        repo.amend_event(
            uuid4(),
            make_draft(EventType.CHANGING),
        )


def test_cross_recipient_amendment_is_rejected():
    repo = InMemoryEventRepository()

    original = repo.create_event(
        make_draft(
            EventType.REPOSITIONING,
            recipient_id="recipient-1",
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        )
    )

    with pytest.raises(ValueError):
        repo.amend_event(
            original.id,
            make_draft(
                EventType.CHANGING,
                recipient_id="recipient-2",
            ),
        )


def test_amendment_risk_is_recalculated_in_both_directions():
    test_registry = EventPolicyRegistry(
        {
            EventType.REPOSITIONING: EventPolicy(
                risk_level=RiskLevel.LOW,
                auto_log_eligible=False,
                proposal_timeout_seconds=300,
            ),
            EventType.MEDICATION: EventPolicy(
                risk_level=RiskLevel.HIGH,
                auto_log_eligible=False,
                proposal_timeout_seconds=300,
            ),
        }
    )

    repo_one = InMemoryEventRepository(
        registry=test_registry
    )

    low_parent = repo_one.create_event(
        make_draft(
            EventType.REPOSITIONING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        )
    )

    high_child = repo_one.amend_event(
        low_parent.id,
        make_draft(
            EventType.MEDICATION,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        ),
    )

    assert low_parent.risk_level == RiskLevel.LOW
    assert high_child.risk_level == RiskLevel.HIGH

    repo_two = InMemoryEventRepository(
        registry=test_registry
    )

    high_parent = repo_two.create_event(
        make_draft(
            EventType.MEDICATION,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        )
    )

    low_child = repo_two.amend_event(
        high_parent.id,
        make_draft(
            EventType.REPOSITIONING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            source=EventSource.VOICE,
        ),
    )

    assert high_parent.risk_level == RiskLevel.HIGH
    assert low_child.risk_level == RiskLevel.LOW


def test_overdue_proposal_expires():
    repo = InMemoryEventRepository()

    created_at = datetime(
        2026,
        11,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    event = repo.create_event(
        make_draft(
            EventType.FEEDING,
            started_at=created_at,
        ),
        now=created_at,
    )

    expired = repo.expire_overdue_proposals(
        now=created_at + timedelta(seconds=301)
    )

    refreshed = repo.get_event(event.id)

    assert refreshed.lifecycle_status == LifecycleStatus.EXPIRED
    assert expired == [refreshed]