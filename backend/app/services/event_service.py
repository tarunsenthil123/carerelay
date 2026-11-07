from datetime import datetime, timedelta, timezone

from backend.app.models.enums import (
    LifecycleStatus,
    RiskLevel,
    VerificationMethod,
)
from backend.app.models.events import (
    CareEvent,
    CareEventDraft,
)
from backend.app.models.policies import (
    EventPolicy,
    EventPolicyRegistry,
    PRODUCTION_POLICY_REGISTRY,
)


CLOCK_SKEW_ALLOWANCE_SECONDS = 300


def _require_timezone_aware(
    value: datetime,
    field_name: str,
) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )


def _validate_event_times(
    draft: CareEventDraft,
    now: datetime,
) -> None:
    _require_timezone_aware(
        draft.started_at,
        "started_at",
    )

    if draft.ended_at is not None:
        _require_timezone_aware(
            draft.ended_at,
            "ended_at",
        )

        if draft.ended_at < draft.started_at:
            raise ValueError(
                "ended_at cannot precede started_at"
            )

    if draft.verified_at is not None:
        _require_timezone_aware(
            draft.verified_at,
            "verified_at",
        )

    maximum_start_time = now + timedelta(
        seconds=CLOCK_SKEW_ALLOWANCE_SECONDS
    )

    if draft.started_at > maximum_start_time:
        raise ValueError(
            "started_at cannot be materially in the future"
        )


def _validate_verification(
    draft: CareEventDraft,
    policy: EventPolicy,
) -> None:
    if draft.lifecycle_status == LifecycleStatus.CONFIRMED:
        if draft.verified_at is None:
            raise ValueError(
                "confirmed events require verified_at"
            )

        if draft.verification_method is None:
            raise ValueError(
                "confirmed events require verification_method"
            )

    method = draft.verification_method

    if method is None:
        return

    if method == VerificationMethod.MANUAL_ENTRY:
        if not draft.source.is_human_initiated:
            raise ValueError(
                "manual_entry requires a human-initiated source"
            )

    if method == VerificationMethod.AUTO_LOGGED:
        if not draft.source.is_ai_derived:
            raise ValueError(
                "auto_logged requires an AI-derived source"
            )

        if policy.risk_level == RiskLevel.HIGH:
            raise ValueError(
                "HIGH-risk events cannot auto-log"
            )

        if not policy.auto_log_eligible:
            raise ValueError(
                "event policy does not allow auto-logging"
            )


def build_care_event(
    draft: CareEventDraft,
    registry: EventPolicyRegistry = PRODUCTION_POLICY_REGISTRY,
    now: datetime | None = None,
) -> CareEvent:
    """
    Apply CareRelay domain policy to an event draft and return a
    validated CareEvent.

    Event risk and auto-log eligibility come from the injected policy
    registry, never from caller-controlled event data.
    """

    current_time = now or datetime.now(timezone.utc)

    _require_timezone_aware(
        current_time,
        "now",
    )

    policy = registry.get(draft.event_type)

    _validate_event_times(
        draft,
        current_time,
    )

    _validate_verification(
        draft,
        policy,
    )

    return CareEvent(
        **draft.model_dump(),
        risk_level=policy.risk_level,
        created_at=current_time.astimezone(timezone.utc),
    )