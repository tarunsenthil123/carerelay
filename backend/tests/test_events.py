from backend.app.models.enums import (
    EventSource,
    EventType,
    RiskLevel,
)
from backend.app.models.policies import (
    EventPolicy,
    EventPolicyRegistry,
    PRODUCTION_POLICY_REGISTRY,
    get_event_policy,
)


def test_voice_is_human_initiated():
    assert EventSource.VOICE.is_human_initiated is True
    assert EventSource.VOICE.is_ai_derived is False


def test_vision_is_ai_derived():
    assert EventSource.VISION.is_ai_derived is True
    assert EventSource.VISION.is_human_initiated is False


def test_medication_policy_is_high_risk():
    policy = get_event_policy(EventType.MEDICATION)

    assert policy.risk_level == RiskLevel.HIGH
    assert policy.auto_log_eligible is False


def test_repositioning_is_high_risk_and_auto_logging_is_disabled():
    policy = get_event_policy(EventType.REPOSITIONING)

    assert policy.risk_level == RiskLevel.HIGH
    assert policy.auto_log_eligible is False


def test_all_step_2_care_events_are_high_risk():
    for event_type in EventType:
        policy = get_event_policy(event_type)

        assert policy.risk_level == RiskLevel.HIGH
        assert policy.auto_log_eligible is False


def test_custom_policy_registry_does_not_change_production_policy():
    test_registry = EventPolicyRegistry(
        {
            EventType.REPOSITIONING: EventPolicy(
                risk_level=RiskLevel.LOW,
                auto_log_eligible=True,
                proposal_timeout_seconds=300,
            )
        }
    )

    test_policy = get_event_policy(
        EventType.REPOSITIONING,
        registry=test_registry,
    )

    production_policy = get_event_policy(
        EventType.REPOSITIONING,
        registry=PRODUCTION_POLICY_REGISTRY,
    )

    assert test_policy.risk_level == RiskLevel.LOW
    assert test_policy.auto_log_eligible is True

    assert production_policy.risk_level == RiskLevel.HIGH
    assert production_policy.auto_log_eligible is False