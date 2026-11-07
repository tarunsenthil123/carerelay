from datetime import datetime
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
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


def _datetime_is_aware(value: datetime) -> bool:
    return (
        value.tzinfo is not None
        and value.utcoffset() is not None
    )


class CareRelayDetailsModel(BaseModel):
    """
    Shared base model for CareRelay event-detail schemas.

    Unknown fields are rejected so unexpected or misspelled care data
    cannot silently enter the structured record.
    """

    model_config = ConfigDict(extra="forbid")


class FeedingDetails(CareRelayDetailsModel):
    feeding_type: str
    food_or_formula: str | None = None
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = None
    route: str | None = None
    tolerance: str | None = None
    observations: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class MedicationDetails(CareRelayDetailsModel):
    medication_name: str
    dose: float = Field(gt=0)
    dose_unit: str
    route: str | None = None
    scheduled_at: datetime | None = None
    administered_at: datetime | None = None
    is_prn: bool = False
    reason_if_prn: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_datetimes(self) -> Self:
        for field_name in ("scheduled_at", "administered_at"):
            value = getattr(self, field_name)

            if value is not None and not _datetime_is_aware(value):
                raise ValueError(
                    f"{field_name} must be timezone-aware"
                )

        return self


class ChangingDetails(CareRelayDetailsModel):
    change_type: str
    condition: Literal["wet", "soiled", "both", "dry"]
    skin_condition: str | None = None
    barrier_cream_applied: bool | None = None
    clothing_changed: bool | None = None
    notes: str | None = None


class RepositioningDetails(CareRelayDetailsModel):
    from_position: str | None = None
    to_position: str
    assistance_level: str | None = None
    reason: str | None = None
    skin_observation: str | None = None


class CareNoteDetails(CareRelayDetailsModel):
    category: str
    observation: str
    severity_optional: str | None = None
    notes: str | None = None


EventDetails = (
    FeedingDetails
    | MedicationDetails
    | ChangingDetails
    | RepositioningDetails
    | CareNoteDetails
)


class EvaluationMetadata(CareRelayDetailsModel):
    model_prediction: str | None = None
    model_confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    source_modalities: list[str] = Field(default_factory=list)
    proposal_created_at: datetime | None = None
    human_response: str | None = None
    human_correction: str | None = None
    confirmation_time: datetime | None = None
    processing_latency: float | None = Field(
        default=None,
        ge=0,
    )

    @model_validator(mode="after")
    def validate_datetimes(self) -> Self:
        for field_name in (
            "proposal_created_at",
            "confirmation_time",
        ):
            value = getattr(self, field_name)

            if value is not None and not _datetime_is_aware(value):
                raise ValueError(
                    f"{field_name} must be timezone-aware"
                )

        return self


class CareEventDraft(BaseModel):
    """
    Input representation of a care event before CareRelay policy is applied.

    risk_level and auto_log_eligible are intentionally absent because
    callers do not get to choose them.
    """

    model_config = ConfigDict(extra="forbid")

    recipient_id: str
    caregiver_id: str | None = None
    device_id: str | None = None

    event_type: EventType
    lifecycle_status: LifecycleStatus
    care_status: CareStatus

    started_at: datetime
    ended_at: datetime | None = None
    time_source: TimeSource

    source: EventSource

    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    details: EventDetails
    notes: str | None = None

    related_task_id: str | None = None
    amends_event_id: UUID | None = None

    verified_at: datetime | None = None
    verification_method: VerificationMethod | None = None
    verified_by: str | None = None

    evaluation_metadata: EvaluationMetadata | None = None

    @model_validator(mode="after")
    def validate_detail_schema_matches_event_type(self) -> Self:
        expected_types = {
            EventType.FEEDING: FeedingDetails,
            EventType.MEDICATION: MedicationDetails,
            EventType.CHANGING: ChangingDetails,
            EventType.REPOSITIONING: RepositioningDetails,
            EventType.CARE_NOTE: CareNoteDetails,
        }

        expected_type = expected_types[self.event_type]

        if not isinstance(self.details, expected_type):
            raise ValueError(
                f"{self.event_type.value} events require "
                f"{expected_type.__name__}"
            )

        return self


class CareEvent(CareEventDraft):
    """
    Validated CareRelay event after domain policy has been applied.
    """

    id: UUID = Field(default_factory=uuid4)
    risk_level: RiskLevel
    created_at: datetime