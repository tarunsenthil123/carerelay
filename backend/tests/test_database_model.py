from datetime import datetime, timezone

from sqlalchemy import select

from backend.app.database.base import Base
from backend.app.database.mappers import (
    care_event_record_to_domain,
    care_event_to_record,
)
from backend.app.database.models import CareEventRecord
from backend.app.database.session import (
    SessionLocal,
    engine,
)
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
    RepositioningDetails,
)
from backend.app.services.event_service import (
    build_care_event,
)


def reset_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_care_event_persists_and_round_trips():
    reset_database()

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
        confidence=0.95,
        details=FeedingDetails(
            feeding_type="tube",
            food_or_formula="Formula A",
            quantity=250,
            unit="mL",
            route="g_tube",
        ),
        verified_at=now,
        verification_method=VerificationMethod.MANUAL_ENTRY,
        verified_by="caregiver-1",
    )

    event = build_care_event(
        draft,
        now=now,
    )

    with SessionLocal() as session:
        session.add(
            care_event_to_record(event)
        )
        session.commit()

    with SessionLocal() as session:
        record = session.execute(
            select(CareEventRecord)
        ).scalar_one()

        restored = care_event_record_to_domain(
            record
        )

    assert restored.id == event.id
    assert restored.event_type == EventType.FEEDING
    assert restored.risk_level == RiskLevel.HIGH
    assert restored.lifecycle_status == LifecycleStatus.CONFIRMED
    assert restored.details.quantity == 250
    assert restored.details.unit == "mL"
    assert restored.verification_method == VerificationMethod.MANUAL_ENTRY


def test_amendment_relationship_persists():
    reset_database()

    now = datetime.now(timezone.utc)

    parent = build_care_event(
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
        ),
        now=now,
    )

    child = build_care_event(
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
                to_position="right_side",
            ),
            amends_event_id=parent.id,
            verified_at=now,
            verification_method=VerificationMethod.MANUAL_ENTRY,
        ),
        now=now,
    )

    with SessionLocal() as session:
        session.add(
            care_event_to_record(parent)
        )
        session.add(
            care_event_to_record(child)
        )
        session.commit()

    with SessionLocal() as session:
        child_record = session.get(
            CareEventRecord,
            child.id,
        )

    assert child_record is not None
    assert child_record.amends_event_id == parent.id