from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    UUID as PostgreSQLUUID,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from backend.app.database.base import Base


class CareEventRecord(Base):
    """
    PostgreSQL representation of a CareRelay CareEvent.

    The domain layer remains the source of validation and policy truth.
    This model is responsible only for durable persistence.
    """

    __tablename__ = "care_events"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
    )

    recipient_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    caregiver_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    device_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    lifecycle_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    care_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    risk_level: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    time_source: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    related_task_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    amends_event_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "care_events.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    verification_method: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    verified_by: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    evaluation_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )


Index(
    "ix_care_events_recipient_started_at",
    CareEventRecord.recipient_id,
    CareEventRecord.started_at,
)

Index(
    "ix_care_events_amends_event_id",
    CareEventRecord.amends_event_id,
)