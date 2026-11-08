from backend.app.database.models import (
    CareEventRecord,
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
    CareEvent,
    CareNoteDetails,
    ChangingDetails,
    EvaluationMetadata,
    FeedingDetails,
    MedicationDetails,
    RepositioningDetails,
)


DETAIL_MODELS = {
    EventType.FEEDING: FeedingDetails,
    EventType.MEDICATION: MedicationDetails,
    EventType.CHANGING: ChangingDetails,
    EventType.REPOSITIONING: RepositioningDetails,
    EventType.CARE_NOTE: CareNoteDetails,
}


def care_event_to_record(
    event: CareEvent,
) -> CareEventRecord:
    evaluation_metadata = None

    if event.evaluation_metadata is not None:
        evaluation_metadata = (
            event.evaluation_metadata.model_dump(
                mode="json"
            )
        )

    return CareEventRecord(
        id=event.id,
        recipient_id=event.recipient_id,
        caregiver_id=event.caregiver_id,
        device_id=event.device_id,
        event_type=event.event_type.value,
        lifecycle_status=event.lifecycle_status.value,
        care_status=event.care_status.value,
        risk_level=event.risk_level.value,
        started_at=event.started_at,
        ended_at=event.ended_at,
        time_source=event.time_source.value,
        source=event.source.value,
        confidence=event.confidence,
        details=event.details.model_dump(
            mode="json"
        ),
        notes=event.notes,
        related_task_id=event.related_task_id,
        amends_event_id=event.amends_event_id,
        verified_at=event.verified_at,
        verification_method=(
            event.verification_method.value
            if event.verification_method
            else None
        ),
        verified_by=event.verified_by,
        created_at=event.created_at,
        evaluation_metadata=evaluation_metadata,
    )


def care_event_record_to_domain(
    record: CareEventRecord,
) -> CareEvent:
    event_type = EventType(
        record.event_type
    )

    detail_model = DETAIL_MODELS[
        event_type
    ]

    details = detail_model.model_validate(
        record.details
    )

    evaluation_metadata = None

    if record.evaluation_metadata is not None:
        evaluation_metadata = (
            EvaluationMetadata.model_validate(
                record.evaluation_metadata
            )
        )

    return CareEvent(
        id=record.id,
        recipient_id=record.recipient_id,
        caregiver_id=record.caregiver_id,
        device_id=record.device_id,
        event_type=event_type,
        lifecycle_status=LifecycleStatus(
            record.lifecycle_status
        ),
        care_status=CareStatus(
            record.care_status
        ),
        risk_level=RiskLevel(
            record.risk_level
        ),
        started_at=record.started_at,
        ended_at=record.ended_at,
        time_source=TimeSource(
            record.time_source
        ),
        source=EventSource(
            record.source
        ),
        confidence=record.confidence,
        details=details,
        notes=record.notes,
        related_task_id=record.related_task_id,
        amends_event_id=record.amends_event_id,
        verified_at=record.verified_at,
        verification_method=(
            VerificationMethod(
                record.verification_method
            )
            if record.verification_method
            else None
        ),
        verified_by=record.verified_by,
        created_at=record.created_at,
        evaluation_metadata=evaluation_metadata,
    )