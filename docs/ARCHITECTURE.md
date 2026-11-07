# CareRelay — Final Frozen Implementation Architecture

## 1. Overview

CareRelay is a privacy-first home-care assistant for a single high-dependency care recipient.

Its purpose is to create a trustworthy structured record of care, reduce information loss between caregivers, and make handoffs simple without turning caregiving into paperwork.

CareRelay should answer:

- What happened?
- When did it happen?
- Was it completed?
- Was anything unusual observed?
- Was it on time?
- What still needs to happen?
- What happened while CareRelay could not observe?
- What does the next caregiver need to know?

The product philosophy is:

```text
RICH SYSTEM UNDERNEATH
+
MINIMAL CAREGIVER INTERACTION
```

The engineering philosophy is:

```text
BUILD THE TRUSTWORTHY CARE RECORD FIRST

THEN MAKE AI BETTER AT POPULATING IT
```

---

# 2. Physical Device

Final controls:

```text
[ CONFIRM ]   [ DENY ]   [ LOG ]   [ RECAP ]

              [ SENSING ON / OFF ]
```

Hardware architecture:

```text
XIAO ESP32S3 Sense
├── camera
├── onboard microphone
├── Wi-Fi
├── microSD
├── CONFIRM button
├── DENY button
├── LOG button
├── RECAP button
├── sensing toggle
├── status LEDs
└── I2S audio output

XIAO
↓
MAX98357A
↓
4Ω / 3W speaker
```

There are intentionally no activity-specific buttons such as FEEDING, MEDICATION, CHANGING, or REPOSITIONING.

---

# 3. Button Meanings

## CONFIRM

Meaning:

> Yes, what CareRelay just proposed is correct.

Example:

```text
CareRelay:
"Feeding detected. 250 milliliters. Confirm?"

Caregiver:
CONFIRM
```

---

## DENY

Meaning:

> No, that proposal is wrong.

Flow:

```text
proposal
↓
DENY
↓
"What happened instead?"
↓
caregiver speaks
↓
structured correction
↓
new amendment event
```

The original event remains stored.

---

## LOG

Meaning:

> Something happened and I want to tell CareRelay about it.

Flow:

```text
LOG
↓
"What would you like to log?"
↓
caregiver speaks
↓
speech-to-text
↓
structured extraction
↓
CareEvent
↓
read-back
↓
CONFIRM / DENY
```

LOG is the explicit fallback when automatic sensing misses something.

---

## RECAP

Meaning:

> Tell me what has happened, what matters now, and what comes next.

RECAP does not replay raw audio or video.

---

# 4. Sensing Toggle

One physical switch controls both:

```text
camera
+
microphone
```

When ON:

```text
camera sensing enabled
microphone sensing enabled
```

When OFF:

```text
camera processing disabled
microphone processing disabled
```

For V1, this must be described as:

**software-controlled sensing/privacy mode**

CareRelay must not claim a hardware privacy cutoff until one actually exists.

When sensing is OFF:

```text
red LED
+
backend records sensing-off interval
```

Possible later hardware improvements include:

```text
physical camera shutter
sensor power gating
true electrical cutoff
```

---

# 5. LED States

```text
GREEN
→ sensing active

YELLOW
→ listening
→ processing
→ waiting for caregiver response
→ proposal interaction

RED
→ sensing disabled
```

---

# 6. Device State Machine

Core states:

```text
IDLE
PROPOSAL_PENDING
LISTENING
SPEAKING
```

| State | CONFIRM | DENY | LOG | RECAP |
|---|---|---|---|---|
| Idle | no action | no action | start manual log | speak recap |
| Proposal pending | confirm proposal | deny + correction | preserve proposal, start log | pause proposal, recap, return |
| Listening | no action | cancel | finish recording | no action |
| Speaking | no action | stop speech | no action | no action |

Recording also supports:

```text
auto-stop on silence
maximum recording timeout
```

The caregiver should normally not need to press LOG twice.

---

# 7. Proposal Interruption Behavior

If RECAP is pressed during a pending proposal:

```text
proposal pending
↓
pause proposal
↓
speak recap
↓
return to proposal
```

If LOG is pressed during a pending proposal:

```text
proposal pending
↓
preserve proposal
↓
manual logging workflow
↓
resolve manual event
↓
return to proposal
```

No pending proposal silently disappears.

---

# 8. Overall System Pipeline

```text
CAMERA
+
MICROPHONE
+
CARE SCHEDULE
+
RECENT CARE HISTORY
        ↓
possible care activity
        ↓
audio + visual interpretation
        ↓
CareEvent candidate
        ↓
risk + confidence policy
        ↓
confirm / deny / auto-log when allowed
        ↓
append-only event history
        ↓
effective timeline
        ↓
compare against care plan
        ↓
deterministic rules engine
        ↓
recap
        ↓
dashboard + speaker
```

Vision provides evidence. It does not automatically establish truth.

---

# 9. Event Categories

Long-term architecture:

```text
feeding
medication
changing
repositioning
transfer
hygiene_cleaning
toileting
mobility
sleep_rest
vitals
equipment
symptom_observation
care_note
other
```

Step 2 fully specifies only:

```text
feeding
medication
changing
repositioning
care_note
```

---

# 10. Core CareEvent Model

```text
CareEvent
├── id
├── recipient_id
├── caregiver_id
├── device_id
│
├── event_type
├── lifecycle_status
├── care_status
├── risk_level
│
├── started_at
├── ended_at
├── time_source
│
├── source
├── confidence
│
├── details
├── notes
│
├── related_task_id
├── amends_event_id
│
├── verified_at
├── verification_method
├── verified_by
│
├── created_at
└── evaluation_metadata
```

There is no `verified: bool`.

Verification is derived from:

```text
verified_at
+
verification_method
```

---

# 11. Lifecycle Status

Lifecycle status describes the CareRelay/system workflow:

```text
candidate
proposed
confirmed
denied
expired
```

---

# 12. Care Status

Care status describes the caregiving activity itself:

```text
started
in_progress
completed
skipped
interrupted
```

Lifecycle status and care status remain separate.

Example:

```text
lifecycle_status = confirmed
care_status = completed
```

---

# 13. EventSource

Human-initiated sources:

```text
manual
dashboard
voice
```

AI-derived sources:

```text
vision
audio_visual
system
```

`voice` is explicitly considered human-initiated.

A caregiver pressing LOG or beginning a correction intentionally starts the interaction. Speech-to-structure extraction may be automated, but the underlying care report was initiated by the caregiver and is subsequently confirmed through read-back.

---

# 14. Event Policy Configuration

Each event type has an explicit policy:

```text
EventPolicy
├── risk_level
├── auto_log_eligible
└── proposal_timeout
```

Step 2 production configuration:

```text
feeding:
  risk_level = MEDIUM
  auto_log_eligible = False

medication:
  risk_level = HIGH
  auto_log_eligible = False

changing:
  risk_level = LOW
  auto_log_eligible = False

repositioning:
  risk_level = LOW
  auto_log_eligible = False

care_note:
  risk_level = MEDIUM
  auto_log_eligible = False
```

`auto_log_eligible` is therefore False for every Step 2 event type.

Actual automatic logging is disabled during Step 2.

Only later, around Step 20 and after evaluation, CareRelay may consider:

```text
changing:
  auto_log_eligible = True

repositioning:
  auto_log_eligible = True
```

if the evidence supports it.

---

# 15. Risk Behavior

Risk is derived from the current event's own `event_type`.

Risk is never inherited from an event being amended.

Example:

```text
A = repositioning
risk = LOW

B = medication
B amends A

B risk = HIGH
```

---

# 16. VerificationMethod

Final verification methods:

```text
confirm_button
dashboard
manual_entry
auto_logged
```

## manual_entry

Valid only for human-initiated sources:

```text
manual
dashboard
voice
```

Invalid for:

```text
vision
audio_visual
system
```

## confirm_button

Valid for:

```text
human-initiated sources
or
AI-derived sources
```

## dashboard

Valid for:

```text
human-initiated sources
or
AI-derived sources
```

## auto_logged

Valid only when all three conditions are true:

```text
1. source is AI-derived
2. risk_level != HIGH
3. event policy auto_log_eligible = True
```

If any condition fails, the event is rejected.

---

# 17. Confirmed-Event Invariant

Any event with:

```text
lifecycle_status = confirmed
```

must contain:

```text
verified_at
verification_method
```

There are no exceptions.

---

# 18. HIGH-Risk Verification Invariant

AI-derived HIGH-risk events may not use:

```text
auto_logged
```

Example:

```text
event_type = medication
source = audio_visual
verification_method = auto_logged

→ INVALID
```

They require human confirmation such as:

```text
confirm_button
dashboard
```

---

# 19. Human-Initiated HIGH-Risk Events

Human-initiated HIGH-risk events are allowed.

Example:

```text
source = voice
event_type = medication
verification_method = manual_entry
```

Valid.

---

# 20. Verification Identity

`verified_by` may initially be null.

Example:

```text
verification_method = confirm_button
verified_at = timestamp
verified_by = null
```

A shared physical device may not know which caregiver pressed the button.

Later CareRelay adds:

```text
current_caregiver
```

selected through the dashboard or at shift start.

---

# 21. Append-Only Care History

Corrections never overwrite historical events.

Example:

```text
A:
repositioning
```

Caregiver corrects it.

Create:

```text
B:
changing
amends_event_id = A.id
```

A remains stored.

---

# 22. Amendment Reference Rules

`amends_event_id` must reference:

```text
1. an existing event
2. belonging to the same recipient
```

Reject:

```text
nonexistent amendment target
```

and:

```text
cross-recipient amendment
```

---

# 23. One-Active-Amendment Rule

An event may have only one active amendment.

Active means:

```text
proposed
confirmed
```

Denied and expired amendments do not count as active.

Valid:

```text
A → B → C
```

Invalid while B is active:

```text
     B
    /
A
    \
     C
```

---

# 24. Effective Timeline Resolver

One rule controls amendment resolution:

> For each amendment chain, return the latest event whose `lifecycle_status = confirmed`.

If there is no confirmed event in the chain:

```text
show nothing
```

Examples:

```text
confirmed A
+ proposed B
→ A
```

```text
confirmed A
+ confirmed B
→ B
```

```text
confirmed A
+ denied B
→ A
```

```text
confirmed A
+ expired B
→ A
```

```text
denied A
+ confirmed B
→ B
```

```text
proposed A
+ denied B
→ nothing
```

```text
A → B → C
latest confirmed = C
→ C
```

---

# 25. Denied False Positives

Example:

```text
AI proposes feeding
↓
caregiver presses DENY
↓
no correction
```

The event does not appear in the effective care timeline.

It remains stored for:

```text
evaluation
debugging
false-positive measurement
future retraining
```

---

# 26. Event Time vs. Record Time

These are separate.

```text
started_at / ended_at
→ when care happened

created_at
→ when CareRelay recorded it
```

Late entry is valid.

Example:

```text
started_at = 12:00 PM
created_at = 4:17 PM
```

---

# 27. TimeSource

Supported values:

```text
sensor_observed
caregiver_reported_exact
caregiver_reported_approximate
system_inferred
```

There is no separate `time_precision`.

If needed later:

```text
time_uncertainty_minutes
```

may be added.

---

# 28. Time Validation

All datetimes must be timezone-aware.

Naive datetimes are rejected.

Also:

```text
ended_at >= started_at
```

and:

```text
started_at cannot be meaningfully in the future
```

A small configurable allowance exists for clock skew.

Persisted timestamps use UTC.

The recipient's local timezone is stored separately later.

---

# 29. FeedingDetails

```text
feeding_type
food_or_formula
quantity
unit
route
tolerance
observations
issues
```

Example:

```json
{
  "event_type": "feeding",
  "details": {
    "feeding_type": "tube",
    "food_or_formula": "Formula A",
    "quantity": 250,
    "unit": "mL",
    "route": "g_tube",
    "tolerance": "mostly_tolerated",
    "observations": [
      "mild coughing near end"
    ]
  }
}
```

---

# 30. MedicationDetails

```text
medication_name
dose
dose_unit
route
scheduled_at
administered_at
is_prn
reason_if_prn
notes
```

Medication begins HIGH risk.

---

# 31. ChangingDetails

```text
change_type
condition
skin_condition
barrier_cream_applied
clothing_changed
notes
```

Possible condition:

```text
wet
soiled
both
dry
```

---

# 32. RepositioningDetails

```text
from_position
to_position
assistance_level
reason
skin_observation
```

---

# 33. CareNoteDetails

```text
category
observation
severity_optional
notes
```

Initial categories may include:

```text
symptom_observation
behavior
skin
equipment
general
```

---

# 34. EvaluationMetadata

Optional.

Manual events do not require evaluation metadata.

AI-generated events may contain:

```text
model_prediction
model_confidence
source_modalities
proposal_created_at
human_response
human_correction
confirmation_time
processing_latency
```

Later metrics include:

```text
accuracy
precision
recall
F1
false-positive rate
correction rate
confirmation rate
confirmation latency
speech extraction accuracy
```

---

# 35. Proposal Expiry

Proposal timeout is configurable through EventPolicy.

Step 2 implements:

```text
expire_overdue_proposals()
```

It is called:

```text
explicitly
and
before relevant reads
```

No background scheduler is required yet.

Expired events remain stored.

---

# 36. Manual LOG Workflow

```text
LOG
↓
"What would you like to log?"
↓
audio
↓
speech-to-text
↓
structured extraction
↓
CareEvent
↓
read-back
↓
CONFIRM / DENY
```

---

# 37. DENY Correction Workflow

```text
proposal
↓
DENY
↓
"What happened instead?"
↓
voice correction
↓
structured event
↓
amends_event_id
↓
confirmation
```

---

# 38. Ambient Audio Policy

Ambient speech alone does not initially create care events.

Invalid behavior:

```text
TV says:
"Take ten milligrams"

→ medication event
```

CareRelay must ignore this.

A stronger candidate may exist when multiple signals agree:

```text
feeding-like activity
+
feeding expected around now
+
"finished 250"
→ feeding candidate
```

---

# 39. Event-Triggered Media Architecture

Later:

```text
Stage 0
motion/audio-energy gate

Stage 1
possible caregiving context

Stage 2
short relevant media window

Stage 3
vision + speech + schedule interpretation
```

This is not required for the initial MVP.

---

# 40. Raw-Media Privacy

Default architecture:

```text
temporary rolling buffer
↓
event trigger
↓
short relevant media window
↓
analysis
↓
structured event retained
↓
raw media discarded
```

The primary record is structured care data.

Potential optional retention later:

```text
never retain clips
retain for 24 hours
retain for 7 days
```

---

# 41. Device Heartbeat

The XIAO periodically reports:

```text
device alive
sensing state
```

Initial target:

```text
approximately every 30–60 seconds
```

Backend determines:

```text
online
offline
sensing on
sensing off
```

---

# 42. Sensing Intervals

Example:

```text
1:00–2:06 PM  ON
2:06–2:47 PM  OFF
2:47–5:00 PM  ON
```

Sensing intervals later feed care-state reasoning.

---

# 43. Missed vs. Unknown

A care task may potentially be considered MISSED when:

```text
task expected
+
device online
+
sensing available
+
no matching event
```

A task is UNKNOWN when:

```text
device offline
or
sensing disabled
during relevant interval
```

CareRelay must never claim care was missed simply because it could not observe.

---

# 44. Care Plan

Expected care exists separately from actual events.

Example:

```text
8:00 AM   feeding
11:00 AM  repositioning
12:00 PM  medication
2:00 PM   feeding
4:00 PM   medication
```

Later the care plan supports:

```text
exact times
time windows
every-N-hours rules
PRN tasks
instructions
feeding protocols
medication protocols
equipment instructions
```

---

# 45. Deterministic Rules Engine

Possible task states:

```text
upcoming
completed
late
overdue
missed
unknown
unresolved
```

Example:

```text
medication due = 12:00 PM
confirmed event = 12:18 PM

→ completed
→ 18 minutes late
```

These states are determined by normal deterministic code, not an LLM.

---

# 46. Dashboard

Main surfaces:

```text
TODAY
TIMELINE
RECAP
CARE PLAN
```

## Today

Shows current task status.

Example:

```text
✓ Morning feeding
✓ Medication
✓ Changing

○ Repositioning due in 34 min
○ Medication at 4 PM
```

## Timeline

Shows only the effective care timeline.

Superseded or denied AI predictions do not clutter it.

## Recap

Displays the same core summary available through the physical device.

## Care Plan

Manages expected care routines and instructions.

---

# 47. Recap Engine

Fact construction:

```text
effective timeline
+
task states
+
upcoming care
+
unknown sensing periods
↓
fact packet
```

There is always a deterministic recap path:

```text
fact packet
↓
deterministic template
↓
valid recap
```

Optional enhancement:

```text
fact packet
↓
LLM
↓
fact validator
↓
accept or fallback
```

---

# 48. LLM Responsibility

The LLM may:

```text
summarize
rephrase
improve readability
```

The LLM may not establish:

```text
whether medication occurred
when care occurred
how much was given
whether something was late
whether something was missed
```

Those facts come from structured records and deterministic rules.

---

# 49. Speaker Path

```text
text
↓
text-to-speech
↓
XIAO
↓
I2S
↓
MAX98357A
↓
speaker
```

Used for:

```text
proposal prompts
LOG prompts
correction prompts
RECAP
```

---

# 50. Development Architecture

Initial processing:

```text
XIAO
↓ Wi-Fi
Mac
↓
FastAPI
↓
PostgreSQL
```

Backend owns:

```text
events
care plans
rules
device state
speech processing
ML
recap
```

---

# 51. Device Authentication

Before meaningful hardware integration:

```text
device_id
+
static per-device token
```

Backend stores:

```text
hash(token)
```

rather than the plaintext token.

Every device request authenticates.

A static per-device token is sufficient for the prototype.

---

# 52. Current Caregiver

Later add:

```text
current_caregiver
```

Selected through:

```text
dashboard
or
shift-start interaction
```

Until then:

```text
verified_by = null
```

is valid for physical-button verification.

---

# 53. V1 Scope

```text
1 care recipient
1 primary CareRelay device
1 primary room
multiple caregivers
```

`recipient_id` remains part of the model for future expansion.

Multi-recipient visual identification is outside V1.

---

# 54. Vision Layer

Vision is an advanced automation layer rather than an MVP dependency.

Initial classes may include:

```text
feeding
repositioning
changing
transfer
other
```

Vision outputs probabilities.

Example:

```text
feeding         0.88
repositioning   0.05
changing        0.03
transfer        0.01
other           0.03
```

These are evidence, not facts.

---

# 55. Multimodal Fusion

Eventually combine:

```text
vision probabilities
audio transcript
care schedule
time of day
recent care history
```

Initial fusion may use deterministic/simple scoring.

A complex multimodal neural network is not required initially.

---

# 56. Schedule as Context

Example:

```text
2 PM feeding expected
+
feeding-like activity
+
"finished 250"
→ confidence increases
```

Schedule alone never proves an activity happened.

---

# 57. Correction-Driven Learning

Each DENY + correction produces useful labeled information.

Example:

```text
AI prediction = repositioning
human correction = changing
```

This supports:

```text
evaluation
dataset creation
model retraining
model improvement
```

---

# 58. Personalized Baselines

Later, start with simple explainable methods:

```text
median
MAD
rolling averages
thresholds
```

Example:

```text
usual feeding duration = 45 minutes
current feeding = 79 minutes
```

CareRelay may say:

> “This feeding lasted longer than usual.”

It should not make diagnostic claims.

---

# 59. Step 1 — COMPLETE

Already implemented:

```text
project structure
Git
Python virtual environment
FastAPI
dependencies
root endpoint
health endpoint
Swagger documentation
```

---

# 60. Step 2 — Event Domain Layer

This is the next build step.

## Enums

```text
EventType
LifecycleStatus
CareStatus
RiskLevel
EventSource
TimeSource
VerificationMethod
```

## Detail Schemas

```text
FeedingDetails
MedicationDetails
ChangingDetails
RepositioningDetails
CareNoteDetails
```

## Core Schemas

```text
EvaluationMetadata
CareEvent
```

## Policy Configuration

```text
risk_level
auto_log_eligible
proposal_timeout
```

## Domain Rules

```text
EventSource human/AI classification
verification-method compatibility
confirmed-event validation

amendment target existence
same-recipient amendment validation
one-active-amendment rule

risk derived from current event type
effective timeline resolver

timezone/time validation
proposal expiry
```

## Storage

```text
in-memory repository only
```

## Minimal API

```text
create event
confirm event
deny event
amend event
get effective timeline
```

No generic CRUD is required in Step 2.

---

# 61. Step 2 Acceptance Suite — A Through Y

## A — Medication Confirmation

Create a proposed HIGH-risk medication event.

Human-confirm it.

The resulting event is valid and effective.

---

## B — Basic Amendment

```text
A = repositioning
B = changing
B amends A
```

B confirmed.

Effective timeline returns B.

---

## C — Amendment Chain

```text
A → B → C
```

Latest confirmed C is returned.

---

## D — Denied False Positive

A proposed feeding event is denied with no correction.

It remains stored but does not appear in the effective timeline.

---

## E — Invalid Domain Data

Reject invalid values including:

```text
negative medication dose
invalid enum
invalid timestamps
```

---

## F — Denied or Expired Amendment

Confirmed A exists.

B amends A but becomes denied or expired.

Effective timeline continues to return A.

---

## G — HIGH-Risk Auto-Logging Rejected

AI-derived HIGH-risk event using:

```text
verification_method = auto_logged
```

is rejected.

---

## H — Branching Prevention

A already has an active amendment B.

A second active amendment directly against A is rejected.

---

## I — Late / Approximate Event Time

A caregiver may report an earlier approximate event.

Example:

```text
started_at < created_at
time_source = caregiver_reported_approximate
```

Valid.

---

## J — Pending Amendment

Confirmed A exists.

Proposed B amends A.

The timeline still shows A until B is confirmed.

---

## K — Denied Original + Confirmed Correction

```text
A = denied AI proposal
B = confirmed correction
B amends A
```

Effective timeline returns B.

---

## L — Missing Amendment Target

An amendment referencing a nonexistent event is rejected.

---

## M — Cross-Recipient Amendment

An amendment targeting an event belonging to another recipient is rejected.

---

## N — Risk Recalculation

The amendment's risk comes from its own event type.

Example:

```text
A = repositioning → LOW
B = medication → HIGH
B amends A
```

B remains HIGH.

---

## O — Manual HIGH-Risk Event

Human-initiated medication event using:

```text
verification_method = manual_entry
```

is valid.

---

## P — Auto-Log Validator Can Allow Explicit Eligibility

Use a **test-only policy override**:

```text
repositioning:
  risk_level = LOW
  auto_log_eligible = True
```

Then:

```text
event_type = repositioning
source = vision
verification_method = auto_logged
```

is valid.

Production Step 2 configuration is not changed.

---

## Q — Optional Evaluation Metadata

Manual event without `evaluation_metadata` is valid.

---

## R — Naive Datetime

Timezone-naive datetime is rejected.

---

## S — Invalid End Time

```text
ended_at < started_at
```

is rejected.

---

## T — Future Event

A materially future `started_at` is rejected.

A small configured clock-skew tolerance is allowed.

---

## U — Proposal Expiry

An overdue proposal becomes:

```text
expired
```

when the expiry function or relevant read runs.

---

## V — Human Source Cannot Auto-Log

These sources:

```text
manual
dashboard
voice
```

cannot use:

```text
auto_logged
```

---

## W — Confirmed Requires Verification Metadata

Any confirmed event missing:

```text
verified_at
or
verification_method
```

is rejected.

---

## X — Verification Method / Source Compatibility

`manual_entry` is valid only for human-initiated sources.

Invalid:

```text
source = vision
verification_method = manual_entry
```

Also verify that:

```text
confirm_button
dashboard
```

may be used with human-initiated or AI-derived sources when all other rules are satisfied.

---

## Y — Production Step 2 Auto-Logging Is Truly Disabled

Using the real Step 2 policy:

```text
event_type = repositioning
risk_level = LOW
source = vision
verification_method = auto_logged
auto_log_eligible = False
```

must be rejected.

This proves that:

```text
P
→ auto-logging can work if explicitly enabled

Y
→ auto-logging is actually disabled in Step 2
```

---

# 62. Step 2 Development Workflow

Step 2 is built test-first.

```text
1. Save docs/ARCHITECTURE.md

2. Commit frozen architecture

3. Write failing tests A–Y

4. Implement enums

5. Implement EventPolicy config

6. Implement five detail schemas

7. Implement CareEvent + validators

8. Implement in-memory repository

9. Implement amendment rules

10. Implement effective timeline resolver

11. Implement proposal expiry

12. Implement minimal API endpoints

13. Run tests until A–Y all pass

14. Commit Step 2

15. Move to PostgreSQL
```

Any new design issue discovered from this point becomes a failing test first.

---

# 63. Step 3 — PostgreSQL

Replace in-memory persistence with:

```text
SQLAlchemy
+
PostgreSQL
```

Persist:

```text
events
amendment relationships
verification metadata
evaluation metadata
```

---

# 64. Step 4 — XIAO Smoke Test

May overlap with Step 3.

Test:

```text
boot
Wi-Fi
device authentication
CONFIRM
DENY
LOG
RECAP
sensing toggle
LEDs
heartbeat
short microphone capture
basic backend communication
```

The goal is discovering hardware problems early.

---

# 65. Step 5 — Identity Models

Add:

```text
CareRecipient
Caregiver
Device
recipient timezone
current caregiver
```

---

# 66. Step 6 — Device State

Persist:

```text
heartbeat
online/offline
sensing on/off
sensing intervals
```

---

# 67. Step 7 — Care Plan

Add:

```text
scheduled tasks
recurring tasks
PRN tasks
instructions
task-event matching
```

---

# 68. Step 8 — Rules Engine

Implement:

```text
upcoming
completed
late
overdue
missed
unknown
unresolved
```

---

# 69. Step 9 — Dashboard

Build:

```text
Today
Timeline
Recap
Care Plan
```

---

# 70. Step 10 — Voice LOG Workflow

```text
LOG
↓
audio
↓
speech-to-text
↓
structured extraction
↓
CareEvent
↓
read-back
↓
CONFIRM / DENY
```

---

# 71. Step 11 — Correction Workflow

```text
DENY
↓
voice correction
↓
speech-to-text
↓
structured amendment
↓
confirmation
```

---

# 72. Step 12 — Deterministic Recap

Build the full recap system from structured facts without an LLM.

---

# 73. Step 13 — Validated LLM Recap

Optional layer:

```text
fact packet
↓
LLM
↓
fact validator
↓
fallback if invalid
```

---

# 74. Step 14 — Speaker Integration

Complete the physical assistant loop.

At this point:

```text
CARELAY FUNCTIONAL MVP COMPLETE
```

Capabilities include:

```text
LOG
CONFIRM
DENY
RECAP

voice logging
corrections
structured timeline
care plan
rules engine
dashboard
speaker
physical controls
```

---

# 75. Explicit MVP Boundary

```text
STEPS 1–14
=
COMPLETE PRODUCT MVP
```

CareRelay is still a complete project if vision is not finished.

---

# 76. Advanced Intelligence Layer

After the MVP:

```text
15. Visual dataset

16. Vision classifier

17. Event-triggered media buffering

18. Vision suggestion layer

19. Audio + visual + schedule fusion

20. Confidence/risk decision engine

21. Correction-derived training dataset

22. Model evaluation

23. Personalized baselines

24. Simple anomaly detection

25. Quiet-hours / volume polish

26. Stronger hardware privacy

27. 3D-printed enclosure

28. End-to-end testing

29. README / architecture / evaluation metrics

30. Demo / portfolio materials
```

Around Step 20, the policy may be changed after real evaluation.

Likely initial candidates:

```text
repositioning:
  auto_log_eligible = True

changing:
  auto_log_eligible = True
```

Only enable this if performance evidence justifies it.

---

# 77. Demo Honesty

Before vision exists:

```text
use LOG
use real speech
use explicitly labeled scripted proposals
```

Never present simulated computer-vision events as real detections.

After vision exists:

```text
real activity
↓
real model prediction
↓
candidate event
↓
CONFIRM / DENY
```

---

# 78. Documentation

Full architecture source of truth:

```text
docs/ARCHITECTURE.md
```

README remains shorter and includes:

```text
Problem
Solution
Architecture
MVP features
Hardware
Privacy model
Evaluation
Limitations
Demo
```

---

# 79. Final Frozen Rules

1. Care history is append-only.

2. Corrections produce new events.

3. Amendment chains remain linear.

4. Amendment targets must exist.

5. Amendment targets must belong to the same recipient.

6. An event cannot have multiple active amendments.

7. The effective timeline returns the latest confirmed event in each amendment chain.

8. Proposed, denied, or expired amendments do not hide an earlier confirmed event.

9. Lifecycle status and care status remain separate.

10. Risk derives from the current event's own event type.

11. Every event type has an EventPolicy containing `risk_level`, `auto_log_eligible`, and `proposal_timeout`.

12. `auto_log_eligible` is False for every event type during Step 2.

13. LOW risk alone does not imply auto-log eligibility.

14. Auto-log eligibility is explicit configuration.

15. EventSource explicitly distinguishes human-initiated from AI-derived sources.

16. `voice` is human-initiated.

17. Every confirmed event requires `verified_at` and `verification_method`.

18. `manual_entry` is valid only for human-initiated sources.

19. `confirm_button` may verify human-initiated or AI-derived events.

20. `dashboard` may verify human-initiated or AI-derived events.

21. `auto_logged` is valid only when the source is AI-derived, risk is not HIGH, and `auto_log_eligible=True`.

22. AI-derived HIGH-risk events cannot auto-log.

23. Human-initiated HIGH-risk events may be manually entered.

24. Manual logging always exists through LOG.

25. Event time and record time are separate.

26. Late event reporting is valid.

27. Approximate event times are represented honestly.

28. All datetimes are timezone-aware.

29. Persisted timestamps use UTC.

30. `ended_at` cannot precede `started_at`.

31. Materially future event times are rejected.

32. `evaluation_metadata` is optional.

33. Denied AI proposals remain available for evaluation.

34. Proposal expiry is deterministic and testable.

35. Scenario P proves auto-logging can work under an explicit test-only policy override.

36. Scenario Y proves auto-logging is OFF under the actual Step 2 production policy.

37. Missed and unknown are different states.

38. Sensing coverage influences care-state conclusions.

39. Ambient audio alone does not initially create care events.

40. Continuous raw media is not the primary care record.

41. Raw media is discarded by default after useful structured information is extracted.

42. V1 privacy is honestly described as software-controlled sensing/privacy mode.

43. Device API requests are authenticated.

44. Device tokens are stored hashed.

45. V1 is single-recipient and single-primary-device.

46. Recap always works without an LLM.

47. LLMs may phrase facts but may not establish facts.

48. MVP functionality does not depend on computer vision.

49. Vision is an automation layer on top of a trustworthy event-record system.

50. Auto-logging remains disabled until later evaluation explicitly justifies enabling it.

51. AI should reduce caregiver workload rather than add it.

52. Any new issue discovered from this point becomes a failing test rather than another architecture-planning cycle.