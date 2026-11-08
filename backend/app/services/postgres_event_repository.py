from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from backend.app.database.mappers import (
    care_event_record_to_domain,
    care_event_to_record,
)
from backend.app.database.models import (
    CareEventRecord,
)
from backend.app.database.session import (
    SessionLocal,
)
from backend.app.models.enums import (
    LifecycleStatus,
    VerificationMethod,
)
from backend.app.models.events import (
    CareEvent,
    CareEventDraft,
)
from backend.app.models.policies import (
    EventPolicyRegistry,
    PRODUCTION_POLICY_REGISTRY,
)
from backend.app.services.event_service import (
    build_care_event,
)


ACTIVE_AMENDMENT_STATUSES = {
    LifecycleStatus.PROPOSED,
    LifecycleStatus.CONFIRMED,
}


class PostgreSQLEventRepository:
    """
    PostgreSQL-backed CareRelay event repository.

    Domain validation remains in the CareRelay event service.
    PostgreSQL provides durable persistence.
    """

    def __init__(
        self,
        session_factory=SessionLocal,
        registry: EventPolicyRegistry = PRODUCTION_POLICY_REGISTRY,
    ):
        self.session_factory = session_factory
        self.registry = registry

    def create_event(
        self,
        draft: CareEventDraft,
        now: datetime | None = None,
    ) -> CareEvent:
        event = build_care_event(
            draft,
            registry=self.registry,
            now=now,
        )

        with self.session_factory() as session:
            session.add(
                care_event_to_record(event)
            )
            session.commit()

        return event

    def get_event(
        self,
        event_id: UUID,
    ) -> CareEvent:
        with self.session_factory() as session:
            record = session.get(
                CareEventRecord,
                event_id,
            )

            if record is None:
                raise ValueError(
                    f"Event does not exist: {event_id}"
                )

            return care_event_record_to_domain(
                record
            )

    def _persist_event(
        self,
        event: CareEvent,
    ) -> CareEvent:
        with self.session_factory() as session:
            session.merge(
                care_event_to_record(event)
            )
            session.commit()

        return event

    def confirm_event(
        self,
        event_id: UUID,
        *,
        verification_method: VerificationMethod,
        verified_at: datetime,
        verified_by: str | None = None,
        now: datetime | None = None,
    ) -> CareEvent:
        existing = self.get_event(
            event_id
        )

        if existing.lifecycle_status not in {
            LifecycleStatus.CANDIDATE,
            LifecycleStatus.PROPOSED,
        }:
            raise ValueError(
                "Only candidate or proposed events can be confirmed"
            )

        draft_data = existing.model_dump(
            exclude={
                "id",
                "risk_level",
                "created_at",
            }
        )

        draft_data.update(
            {
                "lifecycle_status": LifecycleStatus.CONFIRMED,
                "verified_at": verified_at,
                "verification_method": verification_method,
                "verified_by": verified_by,
            }
        )

        draft = CareEventDraft(
            **draft_data
        )

        rebuilt = build_care_event(
            draft,
            registry=self.registry,
            now=now,
        )

        confirmed = rebuilt.model_copy(
            update={
                "id": existing.id,
                "created_at": existing.created_at,
            }
        )

        return self._persist_event(
            confirmed
        )

    def deny_event(
        self,
        event_id: UUID,
    ) -> CareEvent:
        existing = self.get_event(
            event_id
        )

        if existing.lifecycle_status not in {
            LifecycleStatus.CANDIDATE,
            LifecycleStatus.PROPOSED,
        }:
            raise ValueError(
                "Only candidate or proposed events can be denied"
            )

        denied = existing.model_copy(
            update={
                "lifecycle_status": LifecycleStatus.DENIED,
                "verified_at": None,
                "verification_method": None,
                "verified_by": None,
            }
        )

        return self._persist_event(
            denied
        )

    def amend_event(
        self,
        target_event_id: UUID,
        draft: CareEventDraft,
        now: datetime | None = None,
    ) -> CareEvent:
        target = self.get_event(
            target_event_id
        )

        if draft.recipient_id != target.recipient_id:
            raise ValueError(
                "Amendment must belong to the same recipient"
            )

        if (
            draft.amends_event_id is not None
            and draft.amends_event_id != target_event_id
        ):
            raise ValueError(
                "Draft amendment target does not match requested target"
            )

        with self.session_factory() as session:
            active_statuses = [
                status.value
                for status in ACTIVE_AMENDMENT_STATUSES
            ]

            existing_active = session.execute(
                select(
                    CareEventRecord.id
                ).where(
                    CareEventRecord.amends_event_id
                    == target_event_id,
                    CareEventRecord.lifecycle_status.in_(
                        active_statuses
                    ),
                )
            ).first()

        if existing_active is not None:
            raise ValueError(
                "Event already has an active amendment"
            )

        amendment_draft = draft.model_copy(
            update={
                "amends_event_id": target_event_id,
            }
        )

        amendment = build_care_event(
            amendment_draft,
            registry=self.registry,
            now=now,
        )

        with self.session_factory() as session:
            session.add(
                care_event_to_record(
                    amendment
                )
            )
            session.commit()

        return amendment

    def expire_overdue_proposals(
        self,
        now: datetime | None = None,
    ) -> list[CareEvent]:
        current_time = (
            now
            or datetime.now(timezone.utc)
        )

        if (
            current_time.tzinfo is None
            or current_time.utcoffset() is None
        ):
            raise ValueError(
                "now must be timezone-aware"
            )

        expired_events: list[
            CareEvent
        ] = []

        with self.session_factory() as session:
            records = session.execute(
                select(
                    CareEventRecord
                ).where(
                    CareEventRecord.lifecycle_status
                    == LifecycleStatus.PROPOSED.value
                )
            ).scalars().all()

            for record in records:
                event = (
                    care_event_record_to_domain(
                        record
                    )
                )

                policy = self.registry.get(
                    event.event_type
                )

                expiry_time = (
                    event.created_at
                    + timedelta(
                        seconds=(
                            policy.proposal_timeout_seconds
                        )
                    )
                )

                if current_time < expiry_time:
                    continue

                expired = event.model_copy(
                    update={
                        "lifecycle_status":
                            LifecycleStatus.EXPIRED
                    }
                )

                session.merge(
                    care_event_to_record(
                        expired
                    )
                )

                expired_events.append(
                    expired
                )

            session.commit()

        return expired_events

    def get_effective_timeline(
        self,
        recipient_id: str,
        now: datetime | None = None,
    ) -> list[CareEvent]:
        self.expire_overdue_proposals(
            now=now
        )

        with self.session_factory() as session:
            records = session.execute(
                select(
                    CareEventRecord
                ).where(
                    CareEventRecord.recipient_id
                    == recipient_id
                )
            ).scalars().all()

        events = [
            care_event_record_to_domain(
                record
            )
            for record in records
        ]

        events_by_id = {
            event.id: event
            for event in events
        }

        children: dict[
            UUID,
            list[CareEvent],
        ] = defaultdict(list)

        for event in events:
            if event.amends_event_id is not None:
                children[
                    event.amends_event_id
                ].append(event)

        for child_list in children.values():
            child_list.sort(
                key=lambda event:
                    event.created_at
            )

        roots = [
            event
            for event in events
            if (
                event.amends_event_id is None
                or event.amends_event_id
                not in events_by_id
            )
        ]

        effective_events: list[
            CareEvent
        ] = []

        for root in roots:
            candidates: list[
                tuple[int, CareEvent]
            ] = []

            def walk(
                event: CareEvent,
                depth: int,
            ) -> None:
                if (
                    event.lifecycle_status
                    == LifecycleStatus.CONFIRMED
                ):
                    candidates.append(
                        (depth, event)
                    )

                for child in children.get(
                    event.id,
                    [],
                ):
                    walk(
                        child,
                        depth + 1,
                    )

            walk(
                root,
                0,
            )

            if not candidates:
                continue

            _, effective = max(
                candidates,
                key=lambda item: (
                    item[0],
                    item[1].created_at,
                ),
            )

            effective_events.append(
                effective
            )

        effective_events.sort(
            key=lambda event: (
                event.started_at,
                event.created_at,
            )
        )

        return effective_events