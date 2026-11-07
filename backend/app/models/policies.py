from dataclasses import dataclass

from backend.app.models.enums import EventType, RiskLevel


@dataclass(frozen=True)
class EventPolicy:
    risk_level: RiskLevel
    auto_log_eligible: bool
    proposal_timeout_seconds: int


class EventPolicyRegistry:
    """
    Provides event policies to the CareRelay domain layer.

    Production code uses the default production registry.
    Tests may create isolated registries with different policies without
    modifying production configuration.
    """

    def __init__(self, policies: dict[EventType, EventPolicy]):
        self._policies = dict(policies)

    def get(self, event_type: EventType) -> EventPolicy:
        try:
            return self._policies[event_type]
        except KeyError as exc:
            raise ValueError(
                f"No event policy configured for event type: {event_type}"
            ) from exc


PRODUCTION_EVENT_POLICIES: dict[EventType, EventPolicy] = {
    EventType.FEEDING: EventPolicy(
        risk_level=RiskLevel.HIGH,
        auto_log_eligible=False,
        proposal_timeout_seconds=300,
    ),

    EventType.MEDICATION: EventPolicy(
        risk_level=RiskLevel.HIGH,
        auto_log_eligible=False,
        proposal_timeout_seconds=300,
    ),

    EventType.CHANGING: EventPolicy(
        risk_level=RiskLevel.HIGH,
        auto_log_eligible=False,
        proposal_timeout_seconds=300,
    ),

    EventType.REPOSITIONING: EventPolicy(
        risk_level=RiskLevel.HIGH,
        auto_log_eligible=False,
        proposal_timeout_seconds=300,
    ),

    EventType.CARE_NOTE: EventPolicy(
        risk_level=RiskLevel.HIGH,
        auto_log_eligible=False,
        proposal_timeout_seconds=300,
    ),
}


PRODUCTION_POLICY_REGISTRY = EventPolicyRegistry(
    PRODUCTION_EVENT_POLICIES
)


def get_event_policy(
    event_type: EventType,
    registry: EventPolicyRegistry = PRODUCTION_POLICY_REGISTRY,
) -> EventPolicy:
    """
    Convenience function for retrieving an event policy.

    Production code uses PRODUCTION_POLICY_REGISTRY by default.
    Tests may inject a different registry.
    """
    return registry.get(event_type)