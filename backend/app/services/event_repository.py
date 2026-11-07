from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

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


class InMemoryEventRepository:
    """
    Step 2 in-memory CareRelay event repository.

    Corrections create new events rather than overwriting historical
    care records.

    The repository receives an EventPolicyRegistry so production uses
    the real policy while tests may inject isolated policy registries.
    """

    def __init__(
        self,
        registry: EventPolicyRegistry = PRODUCTION_POLICY_REGISTRY,
    ):
        self.registry = registry
        self._events: dict[UUID, CareEvent] = {}

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

        self._events[event.id] = event

        return event

    def get_event(
        self,
        event_id: UUID,
    ) -> CareEvent:
        event = self._events.get(event_id)

        if event is None:
            raise ValueError(
                f"Event does not exist: {event_id}"
            )

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
        existing = self.get_event(event_id)

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

        draft = CareEventDraft(**draft_data)

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

        self._events[event_id] = confirmed

        return confirmed

    def deny_event(
        self,
        event_id: UUID,
    ) -> CareEvent:
        existing = self.get_event(event_id)

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

        self._events[event_id] = denied

        return denied

    def amend_event(
        self,
        target_event_id: UUID,
        draft: CareEventDraft,
        now: datetime | None = None,
    ) -> CareEvent:
        target = self.get_event(target_event_id)

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

        for event in self._events.values():
            if (
                event.amends_event_id == target_event_id
                and event.lifecycle_status
                in ACTIVE_AMENDMENT_STATUSES
            ):
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

        self._events[amendment.id] = amendment

        return amendment

    def expire_overdue_proposals(
        self,
        now: datetime | None = None,
    ) -> list[CareEvent]:
        current_time = now or datetime.now(timezone.utc)

        if (
            current_time.tzinfo is None
            or current_time.utcoffset() is None
        ):
            raise ValueError(
                "now must be timezone-aware"
            )

        expired_events: list[CareEvent] = []

        for event_id, event in list(self._events.items()):
            if event.lifecycle_status != LifecycleStatus.PROPOSED:
                continue

            policy = self.registry.get(
                event.event_type
            )

            expiry_time = (
                event.created_at
                + timedelta(
                    seconds=policy.proposal_timeout_seconds
                )
            )

            if current_time >= expiry_time:
                expired = event.model_copy(
                    update={
                        "lifecycle_status": LifecycleStatus.EXPIRED,
                    }
                )

                self._events[event_id] = expired
                expired_events.append(expired)

        return expired_events

    def get_effective_timeline(
        self,
        recipient_id: str,
        now: datetime | None = None,
    ) -> list[CareEvent]:
        self.expire_overdue_proposals(
            now=now
        )

        recipient_events = {
            event.id: event
            for event in self._events.values()
            if event.recipient_id == recipient_id
        }

        children: dict[
            UUID,
            list[CareEvent],
        ] = defaultdict(list)

        for event in recipient_events.values():
            if event.amends_event_id is not None:
                children[event.amends_event_id].append(
                    event
                )

        for child_list in children.values():
            child_list.sort(
                key=lambda event: event.created_at
            )

        roots = [
            event
            for event in recipient_events.values()
            if (
                event.amends_event_id is None
                or event.amends_event_id
                not in recipient_events
            )
        ]

        effective_events: list[CareEvent] = []

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

            walk(root, 0)

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