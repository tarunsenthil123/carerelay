from enum import Enum


class EventType(str, Enum):
    FEEDING = "feeding"
    MEDICATION = "medication"
    CHANGING = "changing"
    REPOSITIONING = "repositioning"
    CARE_NOTE = "care_note"


class LifecycleStatus(str, Enum):
    CANDIDATE = "candidate"
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    DENIED = "denied"
    EXPIRED = "expired"


class CareStatus(str, Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    INTERRUPTED = "interrupted"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EventSource(str, Enum):
    MANUAL = "manual"
    DASHBOARD = "dashboard"
    VOICE = "voice"

    VISION = "vision"
    AUDIO_VISUAL = "audio_visual"
    SYSTEM = "system"

    @property
    def is_human_initiated(self) -> bool:
        return self in {
            EventSource.MANUAL,
            EventSource.DASHBOARD,
            EventSource.VOICE,
        }

    @property
    def is_ai_derived(self) -> bool:
        return self in {
            EventSource.VISION,
            EventSource.AUDIO_VISUAL,
            EventSource.SYSTEM,
        }


class TimeSource(str, Enum):
    SENSOR_OBSERVED = "sensor_observed"
    CAREGIVER_REPORTED_EXACT = "caregiver_reported_exact"
    CAREGIVER_REPORTED_APPROXIMATE = "caregiver_reported_approximate"
    SYSTEM_INFERRED = "system_inferred"


class VerificationMethod(str, Enum):
    CONFIRM_BUTTON = "confirm_button"
    DASHBOARD = "dashboard"
    MANUAL_ENTRY = "manual_entry"
    AUTO_LOGGED = "auto_logged"