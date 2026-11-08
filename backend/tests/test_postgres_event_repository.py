from datetime import datetime, timedelta, timezone

import pytest

from backend.app.database.base import Base
from backend.app.database.session import (
    SessionLocal,
    engine,
)
from backend.app.models.enums import (
    CareStatus,
    EventSource,
    EventType,
    LifecycleStatus,
    TimeSource,
    VerificationMethod,
)
from backend.app.models.events import (
    CareEventDraft,
    ChangingDetails,
    FeedingDetails,
    RepositioningDetails,
)
from backend.app.services.postgres_event_repository import (
    PostgreSQLEventRepository,
)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def make_feeding_draft(
    *,
    lifecycle_status=LifecycleStatus.PROPOSED,
    source=EventSource.VISION,
    started_at=None,
):
    now = started_at or datetime.now(timezone.utc)

    data = {
        "recipient_id": "recipient-1",
        "caregiver_id": "caregiver-1",
        "device_id": "device-1",
        "event_type": EventType.FEEDING,
        "lifecycle_status": lifecycle_status,
        "care_status": CareStatus.COMPLETED,
        "started_at": now,
        "time_source": TimeSource.SENSOR_OBSERVED,
        "source": source,
        "details": FeedingDetails(
            feeding_type="tube",
            quantity=250,
            unit="mL",
        ),
    }

    if lifecycle_status == LifecycleStatus.CONFIRMED:
        data["verified_at"] = now

        if source.is_human_initiated:
            data["verification_method"] = (
                VerificationMethod.MANUAL_ENTRY
            )
        else:
            data["verification_method"] = (
                VerificationMethod.CONFIRM_BUTTON
            )

    return CareEventDraft(**data)


def test_event_survives_repository_recreation():
    repo_one = PostgreSQLEventRepository(
        session_factory=SessionLocal
    )

    event = repo_one.create_event(
        make_feeding_draft()
    )

    repo_two = PostgreSQLEventRepository(
        session_factory=SessionLocal
    )

    restored = repo_two.get_event(event.id)

    assert restored.id == event.id
    assert restored.event_type == EventType.FEEDING
    assert restored.details.quantity == 250


def test_confirm_event_persists():
    repo = PostgreSQLEventRepository(
        session_factory=SessionLocal
    )

    event = repo.create_event(
        make_feeding_draft()
    )

    now = datetime.now(timezone.utc)

    repo.confirm_event(
        event.id,
        verification_method=VerificationMethod.CONFIRM_BUTTON,
        verified_at=now,
    )

    fresh_repo = PostgreSQLEventRepository(
        session_factory=SessionLocal
    )

    restored = fresh_repo.get_event(event.id)

    assert restored.lifecycle_status == LifecycleStatus.CONFIRMED
    assert restored.verification_method == VerificationMethod.CONFIRM_BUTTON


def test_denied_event_is_not_in_effective_timeline():
    repo = PostgreSQLEventRepository(
        session_factory=SessionLocal
    )

    event = repo.create_event(
        make_feeding_draft()
    )

    repo.deny_event(event.id)

    timeline = repo.get_effective_timeline(
        "recipient-1"
    )

    assert timeline == []


def test_confirmed_amendment_replaces_parent_in_effective_timeline():
    repo = PostgreSQLEventRepository(
        session_factory=SessionLocal
    )

    now = datetime.now(timezone.utc)

    parent = repo.create_event(
        CareEventDraft(
            recipient_id="recipient-1",
            caregiver_id="caregiver-1",
            device_id="device-1",
            event_type=EventType.REPOSITIONING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            care_status=CareStatus.COMPLETED,
            started_at=now,
            time_source=TimeSource.CAREGIVER_REPORTED_EXACT,
            source=EventSource.VOICE,
            details=RepositioningDetails(
                to_position="left_side",
            ),
            verified_at=now,
            verification_method=VerificationMethod.MANUAL_ENTRY,
        )
    )

    correction = repo.amend_event(
        parent.id,
        CareEventDraft(
            recipient_id="recipient-1",
            caregiver_id="caregiver-1",
            device_id="device-1",
            event_type=EventType.CHANGING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            care_status=CareStatus.COMPLETED,
            started_at=now,
            time_source=TimeSource.CAREGIVER_REPORTED_EXACT,
            source=EventSource.VOICE,
            details=ChangingDetails(
                change_type="diaper",
                condition="wet",
            ),
            verified_at=now,
            verification_method=VerificationMethod.MANUAL_ENTRY,
        ),
    )

    timeline = repo.get_effective_timeline(
        "recipient-1"
    )

    assert timeline == [correction]


def test_second_active_amendment_is_rejected():
    repo = PostgreSQLEventRepository(
        session_factory=SessionLocal
    )

    now = datetime.now(timezone.utc)

    parent = repo.create_event(
        CareEventDraft(
            recipient_id="recipient-1",
            caregiver_id="caregiver-1",
            device_id="device-1",
            event_type=EventType.REPOSITIONING,
            lifecycle_status=LifecycleStatus.CONFIRMED,
            care_status=CareStatus.COMPLETED,
            started_at=now,
            time_source=TimeSource.CAREGIVER_REPORTED_EXACT,
            source=EventSource.VOICE,
            details=RepositioningDetails(
                to_position="left_side",
            ),
            verified_at=now,
            verification_method=VerificationMethod.MANUAL_ENTRY,
        )
    )

    repo.amend_event(
        parent.id,
        make_feeding_draft(),
    )

    with pytest.raises(ValueError):
        repo.amend_event(
            parent.id,
            make_feeding_draft(),
        )


def test_overdue_proposal_expiry_persists():
    repo = PostgreSQLEventRepository(
        session_factory=SessionLocal
    )

    created_at = datetime(
        2026,
        11,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    event = repo.create_event(
        make_feeding_draft(
            started_at=created_at,
        ),
        now=created_at,
    )

    repo.expire_overdue_proposals(
        now=created_at + timedelta(seconds=301)
    )

    fresh_repo = PostgreSQLEventRepository(
        session_factory=SessionLocal
    )

    restored = fresh_repo.get_event(
        event.id
    )

    assert restored.lifecycle_status == LifecycleStatus.EXPIRED