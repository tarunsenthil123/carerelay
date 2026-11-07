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

RICH SYSTEM UNDERNEATH  
+  
MINIMAL CAREGIVER INTERACTION

The engineering philosophy is:

BUILD THE TRUSTWORTHY CARE RECORD FIRST

THEN MAKE AI BETTER AT POPULATING IT

---

# 2. Physical Device

Final controls:

[ CONFIRM ]   [ DENY ]   [ LOG ]   [ RECAP ]

              [ SENSING ON / OFF ]

Hardware architecture:

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

There are intentionally no activity-specific buttons such as FEEDING, MEDICATION, CHANGING, or REPOSITIONING.

---

# 3. Button Meanings

## CONFIRM

Meaning:

Yes, what CareRelay just proposed is correct.

Example:

CareRelay:

"Feeding detected. 250 milliliters. Confirm?"

Caregiver:

CONFIRM

---

## DENY

Meaning:

No, that proposal is wrong.

Flow:

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

The original event remains stored.

---

## LOG

Meaning:

Something happened and I want to tell CareRelay about it.

Flow:

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

LOG is the explicit fallback when automatic sensing misses something.

---

## RECAP

Meaning:

Tell me what has happened, what matters now, and what comes next.

RECAP does not replay raw audio or video.

---

# 4. Sensing Toggle

One physical switch controls both:

camera  
+  
microphone

When ON:

camera sensing enabled  
microphone sensing enabled

When OFF:

camera processing disabled  
microphone processing disabled

For V1, this must be described as:

**software-controlled sensing/privacy mode**

CareRelay must not claim a hardware privacy cutoff until one actually exists.

When sensing is OFF:

red LED  
+  
backend records sensing-off interval

Possible later hardware improvements include:

physical camera shutter  
sensor power gating  
true electrical cutoff

---

# 5. LED States

GREEN  
→ sensing active

YELLOW  
→ listening  
→ processing  
→ waiting for caregiver response  
→ proposal interaction

RED  
→ sensing disabled

---

# 6. Device State Machine

Core states:

IDLE  
PROPOSAL_PENDING  
LISTENING  
SPEAKING

| State | CONFIRM | DENY | LOG | RECAP |
|---|---|---|---|---|
| Idle | no action | no action | start manual log | speak recap |
| Proposal pending | confirm proposal | deny + correction | preserve proposal, start log | pause proposal, recap, return |
| Listening | no action | cancel | finish recording | no action |
| Speaking | no action | stop speech | no action | no action |

Recording also supports:

auto-stop on silence  
maximum recording timeout

The caregiver should normally not need to press LOG twice.

---

# 7. Proposal Interruption Behavior

If RECAP is pressed during a pending proposal:

proposal pending  
↓  
pause proposal  
↓  
speak recap  
↓  
return to proposal

If LOG is pressed during a pending proposal:

proposal pending  
↓  
preserve proposal  
↓  
manual logging workflow  
↓  
resolve manual event  
↓  
return to proposal

No pending proposal silently disappears.

---

# 8. Overall System Pipeline

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
policy-derived risk + confidence decision  
↓  
confirm / deny / auto-log when policy allows  
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

Vision provides evidence. It does not automatically establish truth.

---

# 9. Event Categories

Long-term architecture:

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

Step 2 fully specifies only:

feeding  
medication  
changing  
repositioning  
care_note

---

# 10. Core CareEvent Model

CareEvent  
├── id  
├── recipient_id  
├── caregiver_id  
├── device_id  
├── event_type  
├── lifecycle_status  
├── care_status  
├── risk_level  
├── started_at  
├── ended_at  
├── time_source  
├── source  
├── confidence  
├── details  
├── notes  
├── related_task_id  
├── amends_event_id  
├── verified_at  
├── verification_method  
├── verified_by  
├── created_at  
└── evaluation_metadata

There is no `verified: bool`.

Verification is derived from:

verified_at  
+  
verification_method

`risk_level` is stored on the resulting CareEvent as the policy-derived risk snapshot for that event.

The caller does not authoritatively choose the event's risk level.

Conceptually:

event payload  
→ describes what happened

event_type  
→ policy lookup

policy registry  
→ derives risk and auto-log eligibility

validated CareEvent  
→ stores derived risk

This prevents clients, devices, or API callers from declaring their own care event to be LOW risk.

---

# 11. Lifecycle Status

Lifecycle status describes the CareRelay/system workflow:

candidate  
proposed  
confirmed  
denied  
expired

---

# 12. Care Status

Care status describes the caregiving activity itself:

started  
in_progress  
completed  
skipped  
interrupted

Lifecycle status and care status remain separate.

Example:

lifecycle_status = confirmed  
care_status = completed

---

# 13. EventSource

Human-initiated sources:

manual  
dashboard  
voice

AI-derived sources:

vision  
audio_visual  
system

`voice` is explicitly considered human-initiated.

A caregiver pressing LOG or beginning a correction intentionally starts the interaction. Speech-to-structure extraction may be automated, but the underlying care report was initiated by the caregiver and is subsequently confirmed through read-back.

---

# 14. Event Policy Configuration

Each event type has an explicit policy:

EventPolicy  
├── risk_level  
├── auto_log_eligible  
└── proposal_timeout

Policies are accessed through an injectable policy registry/provider rather than having validators depend directly on a module-level dictionary.

Conceptually:

EventPolicyRegistry  
├── policy for feeding  
├── policy for medication  
├── policy for changing  
├── policy for repositioning  
└── policy for care_note

The production policy registry is the default.

Validators, event-domain services, and the Step 2 repository receive a policy registry/provider as a dependency.

Conceptually:

EventValidator(policy_registry=PRODUCTION_POLICY_REGISTRY)

EventRepository(policy_registry=PRODUCTION_POLICY_REGISTRY)

The production registry is used automatically unless a different registry is explicitly injected.

This exists for two reasons:

1. production behavior remains centralized and deterministic
2. tests can inject isolated policy overrides without mutating production configuration

Test-only policy registries may therefore override policies for scenarios such as N and P.

Production configuration itself is never mutated by those tests.

For CareRelay, all Step 2 care events are treated as HIGH risk because every caregiving event materially affects the trustworthiness of the care record.

Step 2 production configuration:

feeding:  
  risk_level = HIGH  
  auto_log_eligible = False

medication:  
  risk_level = HIGH  
  auto_log_eligible = False

changing:  
  risk_level = HIGH  
  auto_log_eligible = False

repositioning:  
  risk_level = HIGH  
  auto_log_eligible = False

care_note:  
  risk_level = HIGH  
  auto_log_eligible = False

This means:

ALL Step 2 care event types  
→ HIGH risk  
→ auto_log_eligible = False  
→ AI-derived events require explicit human verification

CareRelay does not assume that feeding, changing, repositioning, or care notes are lower risk simply because they are not medication events.

A false record of any of these can materially affect downstream caregiving decisions.

Examples:

False feeding record  
→ next caregiver may believe feeding already occurred

False repositioning record  
→ next caregiver may believe pressure-relief care occurred

False changing record  
→ next caregiver may believe hygiene or skin care occurred

False care note  
→ next caregiver may act on an observation that was never verified

False medication record  
→ next caregiver may believe medication was administered

Therefore the Step 2 trust model is intentionally conservative:

AI may propose  
AI may assist  
AI may structure information

AI may NOT silently confirm care events

Automatic logging is disabled for all production Step 2 event types.

If automatic logging is ever reconsidered later, that must be treated as a deliberate future policy change supported by strong evaluation evidence rather than assumed from any supposedly low-risk category.

---

# 15. Risk Behavior

Risk is derived from the current event's own `event_type` through the active policy registry.

In Step 2, every event type in the production policy registry maps to:

HIGH

Risk is never inherited from the event being amended.

Example:

A = repositioning  
production-derived risk = HIGH

B = medication  
B amends A

B production-derived risk = HIGH

Another example:

A = medication  
production-derived risk = HIGH

B = changing  
B amends A

B production-derived risk = HIGH

The amendment system always performs a fresh policy lookup using B's own event type.

Conceptually:

B.event_type  
↓  
active policy registry  
↓  
B.risk_level

It does not perform:

A.risk_level  
↓  
copy  
↓  
B.risk_level

Because all current production Step 2 event types are HIGH risk, every AI-derived event requires human verification before it can become confirmed.

The key distinction remains:

risk_level  
→ how seriously CareRelay treats false confirmation

auto_log_eligible  
→ whether an event type could ever be allowed to confirm automatically

In Step 2 production:

risk_level = HIGH  
auto_log_eligible = False

for every supported event type.

LOW and MEDIUM remain valid `RiskLevel` enum values only for:

- test-only policy overrides
- possible future deliberate policy changes

Production Step 2 code must not assign LOW or MEDIUM to any supported care event through the default production policy.

---

# 16. VerificationMethod

Final verification methods:

confirm_button  
dashboard  
manual_entry  
auto_logged

## manual_entry

Valid only for human-initiated sources:

manual  
dashboard  
voice

Invalid for:

vision  
audio_visual  
system

## confirm_button

Valid for:

human-initiated sources  
or  
AI-derived sources

## dashboard

Valid for:

human-initiated sources  
or  
AI-derived sources

## auto_logged

Valid only when all three conditions are true:

1. source is AI-derived
2. policy-derived risk_level != HIGH
3. active event policy has auto_log_eligible = True

If any condition fails, the event is rejected.

The caller does not provide `auto_log_eligible` as authoritative event data.

CareRelay retrieves it from the active policy registry.

Likewise, the caller does not bypass the policy by manually declaring an event LOW risk.

Under the production Step 2 policy, the `auto_logged` branch is intentionally unreachable because:

- every supported production event type derives HIGH risk
- `auto_log_eligible = False` for every supported production event type

Scenario P exercises this validator using a test-only injected policy registry.

The validator remains part of the domain model because it acts as a guardrail if automatic logging is ever deliberately introduced later.

---

# 17. Confirmed-Event Invariant

Any event with:

lifecycle_status = confirmed

must contain:

verified_at  
verification_method

There are no exceptions.

---

# 18. HIGH-Risk Verification Invariant

AI-derived HIGH-risk events may not use:

auto_logged

Example:

event_type = medication  
source = audio_visual  
verification_method = auto_logged

Production policy lookup:

medication  
→ HIGH  
→ auto_log_eligible = False

Result:

INVALID

The same rule applies to feeding, changing, repositioning, and care notes because all Step 2 production event types are HIGH risk.

They require human confirmation such as:

confirm_button  
dashboard

---

# 19. Human-Initiated HIGH-Risk Events

Human-initiated HIGH-risk events are allowed.

Example:

source = voice  
event_type = medication  
verification_method = manual_entry

Production policy derives:

risk_level = HIGH

Valid.

The same pattern applies to other human-initiated care events.

---

# 20. Verification Identity

`verified_by` may initially be null.

Example:

verification_method = confirm_button  
verified_at = timestamp  
verified_by = null

A shared physical device may not know which caregiver pressed the button.

Later CareRelay adds:

current_caregiver

selected through the dashboard or at shift start.

---

# 21. Append-Only Care History

Corrections never overwrite historical events.

Example:

A:  
repositioning

Caregiver corrects it.

Create:

B:  
changing  
amends_event_id = A.id

A remains stored.

---

# 22. Amendment Reference Rules

`amends_event_id` must reference:

1. an existing event
2. belonging to the same recipient

Reject:

nonexistent amendment target

and:

cross-recipient amendment

---

# 23. One-Active-Amendment Rule

An event may have only one active amendment.

Active means:

proposed  
confirmed

Denied and expired amendments do not count as active.

Valid:

A → B → C

Invalid while B is active:

     B
    /
A
    
     C

---

# 24. Effective Timeline Resolver

One rule controls amendment resolution:

For each amendment chain, return the latest event whose `lifecycle_status = confirmed`.

If there is no confirmed event in the chain:

show nothing

Examples:

confirmed A  
+ proposed B  
→ A

confirmed A  
+ confirmed B  
→ B

confirmed A  
+ denied B  
→ A

confirmed A  
+ expired B  
→ A

denied A  
+ confirmed B  
→ B

proposed A  
+ denied B  
→ nothing

A → B → C  
latest confirmed = C  
→ C

---

# 25. Denied False Positives

Example:

AI proposes feeding  
↓  
caregiver presses DENY  
↓  
no correction

The event does not appear in the effective care timeline.

It remains stored for:

evaluation  
debugging  
false-positive measurement  
future retraining

---

# 26. Event Time vs. Record Time

These are separate.

started_at / ended_at  
→ when care happened

created_at  
→ when CareRelay recorded it

Late entry is valid.

Example:

started_at = 12:00 PM  
created_at = 4:17 PM

---

# 27. TimeSource

Supported values:

sensor_observed  
caregiver_reported_exact  
caregiver_reported_approximate  
system_inferred

There is no separate `time_precision`.

If needed later:

time_uncertainty_minutes

may be added.

---

# 28. Time Validation

All datetimes must be timezone-aware.

Naive datetimes are rejected.

Also:

ended_at >= started_at

and:

started_at cannot be meaningfully in the future

A small configurable allowance exists for clock skew.

Persisted timestamps use UTC.

The recipient's local timezone is stored separately later.

---

# 29. FeedingDetails

feeding_type  
food_or_formula  
quantity  
unit  
route  
tolerance  
observations  
issues

Example:

event_type = feeding

details:
- feeding_type = tube
- food_or_formula = Formula A
- quantity = 250
- unit = mL
- route = g_tube
- tolerance = mostly_tolerated
- observations = mild coughing near end

---

# 30. MedicationDetails

medication_name  
dose  
dose_unit  
route  
scheduled_at  
administered_at  
is_prn  
reason_if_prn  
notes

Medication is HIGH risk under the production policy.

---

# 31. ChangingDetails

change_type  
condition  
skin_condition  
barrier_cream_applied  
clothing_changed  
notes

Possible condition:

wet  
soiled  
both  
dry

---

# 32. RepositioningDetails

from_position  
to_position  
assistance_level  
reason  
skin_observation

---

# 33. CareNoteDetails

category  
observation  
severity_optional  
notes

Initial categories may include:

symptom_observation  
behavior  
skin  
equipment  
general

---

# 34. EvaluationMetadata

Optional.

Manual events do not require evaluation metadata.

AI-generated events may contain:

model_prediction  
model_confidence  
source_modalities  
proposal_created_at  
human_response  
human_correction  
confirmation_time  
processing_latency

Later metrics include:

accuracy  
precision  
recall  
F1  
false-positive rate  
correction rate  
confirmation rate  
confirmation latency  
speech extraction accuracy  
proposal frequency

Because every AI-derived event requires human confirmation in the current production policy, confirmation burden is a key product metric.

CareRelay should specifically monitor:

- confirmation rate
- confirmation latency
- correction rate
- proposal frequency

These metrics help determine whether CareRelay is reducing caregiver work or asking for confirmation too often.

A high proposal frequency combined with low confirmation rate or slow confirmation latency may indicate that CareRelay is interrupting caregivers too often.

Evaluation must therefore measure not only model correctness but also the human interaction burden created by the model.

---

# 35. Proposal Expiry

Proposal timeout is configurable through EventPolicy.

The timeout comes from the active policy registry.

Step 2 implements:

expire_overdue_proposals()

It is called:

explicitly  
and  
before relevant reads

No background scheduler is required yet.

Expired events remain stored.

---

# 36. Manual LOG Workflow

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

---

# 37. DENY Correction Workflow

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
fresh policy lookup for corrected event type  
↓  
confirmation

---

# 38. Ambient Audio Policy

Ambient speech alone does not initially create care events.

Invalid behavior:

TV says:  
"Take ten milligrams"

→ medication event

CareRelay must ignore this.

A stronger candidate may exist when multiple signals agree:

feeding-like activity  
+  
feeding expected around now  
+  
"finished 250"  
→ feeding candidate

---

# 39. Event-Triggered Media Architecture

Later:

Stage 0  
motion/audio-energy gate

Stage 1  
possible caregiving context

Stage 2  
short relevant media window

Stage 3  
vision + speech + schedule interpretation

This is not required for the initial MVP.

---

# 40. Raw-Media Privacy

Default architecture:

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

The primary record is structured care data.

Potential optional retention later:

never retain clips  
retain for 24 hours  
retain for 7 days

---

# 41. Device Heartbeat

The XIAO periodically reports:

device alive  
sensing state

Initial target:

approximately every 30–60 seconds

Backend determines:

online  
offline  
sensing on  
sensing off

---

# 42. Sensing Intervals

Example:

1:00–2:06 PM  ON  
2:06–2:47 PM  OFF  
2:47–5:00 PM  ON

Sensing intervals later feed care-state reasoning.

---

# 43. Missed vs. Unknown

A care task may potentially be considered MISSED when:

task expected  
+  
device online  
+  
sensing available  
+  
no matching event

A task is UNKNOWN when:

device offline  
or  
sensing disabled  
during relevant interval

CareRelay must never claim care was missed simply because it could not observe.

---

# 44. Care Plan

Expected care exists separately from actual events.

Example:

8:00 AM   feeding  
11:00 AM  repositioning  
12:00 PM  medication  
2:00 PM   feeding  
4:00 PM   medication

Later the care plan supports:

exact times  
time windows  
every-N-hours rules  
PRN tasks  
instructions  
feeding protocols  
medication protocols  
equipment instructions

---

# 45. Deterministic Rules Engine

Possible task states:

upcoming  
completed  
late  
overdue  
missed  
unknown  
unresolved

Example:

medication due = 12:00 PM  
confirmed event = 12:18 PM

→ completed  
→ 18 minutes late

These states are determined by normal deterministic code, not an LLM.

---

# 46. Dashboard

Main surfaces:

TODAY  
TIMELINE  
RECAP  
CARE PLAN

## Today

Shows current task status.

Example:

✓ Morning feeding  
✓ Medication  
✓ Changing

○ Repositioning due in 34 min  
○ Medication at 4 PM

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

effective timeline  
+  
task states  
+  
upcoming care  
+  
unknown sensing periods  
↓  
fact packet

There is always a deterministic recap path:

fact packet  
↓  
deterministic template  
↓  
valid recap

Optional enhancement:

fact packet  
↓  
LLM  
↓  
fact validator  
↓  
accept or fallback

---

# 48. LLM Responsibility

The LLM may:

summarize  
rephrase  
improve readability

The LLM may not establish:

whether medication occurred  
when care occurred  
how much was given  
whether something was late  
whether something was missed

Those facts come from structured records and deterministic rules.

---

# 49. Speaker Path

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

Used for:

proposal prompts  
LOG prompts  
correction prompts  
RECAP

---

# 50. Development Architecture

Initial processing:

XIAO  
↓ Wi-Fi  
Mac  
↓  
FastAPI  
↓  
PostgreSQL

Backend owns:

events  
care plans  
rules  
device state  
speech processing  
ML  
recap

Within the backend, policy-dependent event-domain components receive the active EventPolicyRegistry through dependency injection.

Production:

FastAPI / event service  
↓  
production policy registry  
↓  
validators + repository

Tests:

test  
↓  
test policy registry  
↓  
validators + repository

This prevents tests from modifying global production policy state.

---

# 51. Device Authentication

Before meaningful hardware integration:

device_id  
+  
static per-device token

Backend stores:

hash(token)

rather than the plaintext token.

Every device request authenticates.

A static per-device token is sufficient for the prototype.

---

# 52. Current Caregiver

Later add:

current_caregiver

Selected through:

dashboard  
or  
shift-start interaction

Until then:

verified_by = null

is valid for physical-button verification.

---

# 53. V1 Scope

1 care recipient  
1 primary CareRelay device  
1 primary room  
multiple caregivers

`recipient_id` remains part of the model for future expansion.

Multi-recipient visual identification is outside V1.

---

# 54. Vision Layer

Vision is an advanced automation layer rather than an MVP dependency.

Initial classes may include:

feeding  
repositioning  
changing  
transfer  
other

Vision outputs probabilities.

Example:

feeding         0.88  
repositioning   0.05  
changing        0.03  
transfer        0.01  
other           0.03

These are evidence, not facts.

---

# 55. Multimodal Fusion

Eventually combine:

vision probabilities  
audio transcript  
care schedule  
time of day  
recent care history

Initial fusion may use deterministic/simple scoring.

A complex multimodal neural network is not required initially.

---

# 56. Schedule as Context

Example:

2 PM feeding expected  
+  
feeding-like activity  
+  
"finished 250"  
→ confidence increases

Schedule alone never proves an activity happened.

---

# 57. Correction-Driven Learning

Each DENY + correction produces useful labeled information.

Example:

AI prediction = repositioning  
human correction = changing

This supports:

evaluation  
dataset creation  
model retraining  
model improvement

Because the correction creates a new event type, the corrected event receives a fresh policy lookup.

Its risk is not inherited from the original prediction.

---

# 58. Personalized Baselines

Later, start with simple explainable methods:

median  
MAD  
rolling averages  
thresholds

Example:

usual feeding duration = 45 minutes  
current feeding = 79 minutes

CareRelay may say:

"This feeding lasted longer than usual."

It should not make diagnostic claims.

---

# 59. Step 1 — COMPLETE

Already implemented:

project structure  
Git  
Python virtual environment  
FastAPI  
dependencies  
root endpoint  
health endpoint  
Swagger documentation

---

# 60. Step 2 — Event Domain Layer

This is the current build step.

## Enums

EventType  
LifecycleStatus  
CareStatus  
RiskLevel  
EventSource  
TimeSource  
VerificationMethod

## Detail Schemas

FeedingDetails  
MedicationDetails  
ChangingDetails  
RepositioningDetails  
CareNoteDetails

## Core Schemas

EvaluationMetadata  
CareEvent

## Policy Configuration

EventPolicy  
EventPolicyRegistry

Each EventPolicy contains:

risk_level  
auto_log_eligible  
proposal_timeout

The production registry is the default dependency.

Test registries may override individual policies without mutating production configuration.

Production Step 2 policy:

ALL supported event types  
→ risk_level = HIGH  
→ auto_log_eligible = False

## Domain Rules

EventSource human/AI classification  
verification-method compatibility  
confirmed-event validation

policy-derived risk  
policy-derived auto-log eligibility  
injectable policy registry

amendment target existence  
same-recipient amendment validation  
one-active-amendment rule

risk derived from current event type  
fresh policy lookup for amendments  
effective timeline resolver

timezone/time validation  
proposal expiry

## Storage

in-memory repository only

The Step 2 in-memory repository receives the active policy registry/provider.

Production code uses the default production registry.

Tests may construct repositories with isolated test registries.

## Minimal API

create event  
confirm event  
deny event  
amend event  
get effective timeline

No generic CRUD is required in Step 2.

API callers provide event facts.

They do not authoritatively provide:

risk_level  
auto_log_eligible

Those come from the active policy registry.

---

# 61. Step 2 Acceptance Suite — A Through Y

## A — Medication Confirmation

Create a proposed medication event.

The production policy derives:

risk_level = HIGH

Human-confirm it.

The resulting event is valid and effective.

---

## B — Basic Amendment

A = repositioning  
B = changing  
B amends A

B confirmed.

Effective timeline returns B.

Both risks are independently derived from their own event types.

---

## C — Amendment Chain

A → B → C

Latest confirmed C is returned.

---

## D — Denied False Positive

A proposed feeding event is denied with no correction.

It remains stored but does not appear in the effective timeline.

---

## E — Invalid Domain Data

Reject invalid values including:

negative medication dose  
invalid enum  
invalid timestamps

---

## F — Denied or Expired Amendment

Confirmed A exists.

B amends A but becomes denied or expired.

Effective timeline continues to return A.

---

## G — HIGH-Risk Auto-Logging Rejected

Using the production policy registry, create an AI-derived care event using:

verification_method = auto_logged

The policy derives HIGH risk.

The event is rejected.

---

## H — Branching Prevention

A already has an active amendment B.

A second active amendment directly against A is rejected.

---

## I — Late / Approximate Event Time

A caregiver may report an earlier approximate event.

Example:

started_at < created_at  
time_source = caregiver_reported_approximate

Valid.

---

## J — Pending Amendment

Confirmed A exists.

Proposed B amends A.

The timeline still shows A until B is confirmed.

---

## K — Denied Original + Confirmed Correction

A = denied AI proposal  
B = confirmed correction  
B amends A

Effective timeline returns B.

---

## L — Missing Amendment Target

An amendment referencing a nonexistent event is rejected.

---

## M — Cross-Recipient Amendment

An amendment targeting an event belonging to another recipient is rejected.

---

## N — Risk Recalculation

An amendment's risk must always be derived from the amended event's own event type.

It must never be copied from its parent event.

Because every production Step 2 event type is HIGH risk, this behavior is tested using an injected test-only policy registry.

### Case 1

Test registry:

repositioning  
→ LOW

medication  
→ HIGH

Create:

A = repositioning

Expected:

A.risk_level = LOW

Then:

B = medication  
B amends A

Expected:

B.risk_level = HIGH

The child must not inherit A's LOW risk.

### Case 2

Use a test registry where:

medication  
→ HIGH

repositioning  
→ LOW

Create:

A = medication

Expected:

A.risk_level = HIGH

Then:

B = repositioning  
B amends A

Expected:

B.risk_level = LOW

The child must not inherit A's HIGH risk.

Both directions are required.

Otherwise, an implementation that accidentally copies parent risk could pass a one-direction test by coincidence.

The production policy registry remains unchanged and continues to map every supported event type to HIGH.

---

## O — Manual HIGH-Risk Event

Create a human-initiated medication event using:

source = voice  
verification_method = manual_entry

The production policy derives HIGH risk.

The event is valid.

The same principle applies to other human-initiated HIGH-risk care events.

---

## P — Auto-Log Validator Can Allow Explicit Eligibility

This is a generic validator test only.

Create an injected test policy registry containing:

repositioning:  
  risk_level = LOW  
  auto_log_eligible = True

Then create:

event_type = repositioning  
source = vision  
verification_method = auto_logged

Using that test registry:

derived risk_level = LOW  
derived auto_log_eligible = True

The event is valid.

This exists only to prove that the generic validator behaves correctly when an injected policy explicitly permits automatic logging.

The test does not mutate the production registry.

Production Step 2 remains:

repositioning  
→ HIGH  
→ auto_log_eligible = False

The `auto_logged` branch is therefore intentionally unreachable in production Step 2.

The validator is intentionally retained as a guardrail for any deliberate future policy change.

---

## Q — Optional Evaluation Metadata

Manual event without `evaluation_metadata` is valid.

---

## R — Naive Datetime

Timezone-naive datetime is rejected.

---

## S — Invalid End Time

ended_at < started_at

is rejected.

---

## T — Future Event

A materially future `started_at` is rejected.

A small configured clock-skew tolerance is allowed.

---

## U — Proposal Expiry

An overdue proposal becomes:

expired

when the expiry function or relevant read runs.

The timeout comes from the active policy registry.

---

## V — Human Source Cannot Auto-Log

These sources:

manual  
dashboard  
voice

cannot use:

auto_logged

even if a test policy were otherwise auto-log eligible.

---

## W — Confirmed Requires Verification Metadata

Any confirmed event missing:

verified_at  
or  
verification_method

is rejected.

---

## X — Verification Method / Source Compatibility

`manual_entry` is valid only for human-initiated sources.

Invalid:

source = vision  
verification_method = manual_entry

Also verify that:

confirm_button  
dashboard

may be used with human-initiated or AI-derived sources when all other rules are satisfied.

---

## Y — Production Step 2 Auto-Logging Is Truly Disabled

Use the real default production policy registry.

Do not manually supply:

risk_level  
auto_log_eligible

Create:

event_type = repositioning  
source = vision  
verification_method = auto_logged

The production registry must derive:

risk_level = HIGH  
auto_log_eligible = False

The event must therefore be rejected.

This proves the actual production configuration rather than a hand-built test representation of it.

Together:

P  
→ the generic validator can technically permit auto-logging when an injected test policy explicitly allows it

Y  
→ the real default CareRelay production policy permits no automatic logging

---

# 62. Step 2 Development Workflow

Step 2 is built test-first.

1. Save `docs/ARCHITECTURE.md`

2. Commit frozen architecture

3. Define EventPolicy and injectable EventPolicyRegistry

4. Preserve the production policy registry as the default

5. Write failing acceptance tests A–Y

6. Use isolated test registries for N and P

7. Ensure Y uses the untouched default production registry

8. Implement enums

9. Implement five detail schemas

10. Implement CareEvent + validators

11. Derive event risk through the active policy registry

12. Implement in-memory repository with injected policy dependency

13. Implement amendment rules

14. Perform a fresh policy lookup for every amendment event

15. Implement effective timeline resolver

16. Implement proposal expiry

17. Implement minimal API endpoints

18. Run tests until A–Y all pass

19. Commit Step 2

20. Move to PostgreSQL

Any new design issue discovered from this point becomes a failing test rather than another architecture-planning cycle.

---

# 63. Step 3 — PostgreSQL

Replace in-memory persistence with:

SQLAlchemy  
+  
PostgreSQL

Persist:

events  
amendment relationships  
verification metadata  
evaluation metadata  
derived event risk snapshot

The application/domain layer continues to use the production EventPolicyRegistry as its default policy source.

PostgreSQL persistence must not become a second independent source of policy truth.

---

# 64. Step 4 — XIAO Smoke Test

May overlap with Step 3.

Test:

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

The goal is discovering hardware problems early.

---

# 65. Step 5 — Identity Models

Add:

CareRecipient  
Caregiver  
Device  
recipient timezone  
current caregiver

---

# 66. Step 6 — Device State

Persist:

heartbeat  
online/offline  
sensing on/off  
sensing intervals

---

# 67. Step 7 — Care Plan

Add:

scheduled tasks  
recurring tasks  
PRN tasks  
instructions  
task-event matching

---

# 68. Step 8 — Rules Engine

Implement:

upcoming  
completed  
late  
overdue  
missed  
unknown  
unresolved

---

# 69. Step 9 — Dashboard

Build:

Today  
Timeline  
Recap  
Care Plan

---

# 70. Step 10 — Voice LOG Workflow

LOG  
↓  
audio  
↓  
speech-to-text  
↓  
structured extraction  
↓  
event type  
↓  
production policy lookup  
↓  
CareEvent  
↓  
read-back  
↓  
CONFIRM / DENY

---

# 71. Step 11 — Correction Workflow

DENY  
↓  
voice correction  
↓  
speech-to-text  
↓  
structured amendment  
↓  
corrected event type  
↓  
fresh production policy lookup  
↓  
confirmation

---

# 72. Step 12 — Deterministic Recap

Build the full recap system from structured facts without an LLM.

---

# 73. Step 13 — Validated LLM Recap

Optional layer:

fact packet  
↓  
LLM  
↓  
fact validator  
↓  
fallback if invalid

---

# 74. Step 14 — Speaker Integration

Complete the physical assistant loop.

At this point:

CARERELAY FUNCTIONAL MVP COMPLETE

Capabilities include:

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

---

# 75. Explicit MVP Boundary

STEPS 1–14  
=  
COMPLETE PRODUCT MVP

CareRelay is still a complete project if vision is not finished.

---

# 76. Advanced Intelligence Layer

After the MVP:

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

At Step 20, automatic logging may be reconsidered only as a deliberate future policy change supported by strong evaluation data.

No event type is pre-approved for automatic logging.

If policy changes later, the production EventPolicyRegistry is deliberately changed.

A future policy change may alter:

risk_level  
and/or  
auto_log_eligible

based on measured:

model performance  
false-positive rate  
correction rate  
confirmation burden  
confirmation latency  
proposal frequency  
safety considerations

Changing production policy must not require rewriting validator logic.

That is one reason the policy registry remains injectable and separate from the generic validation rules.

---

# 77. Demo Honesty

Before vision exists:

use LOG  
use real speech  
use explicitly labeled scripted proposals

Never present simulated computer-vision events as real detections.

After vision exists:

real activity  
↓  
real model prediction  
↓  
candidate event  
↓  
policy lookup  
↓  
CONFIRM / DENY

---

# 78. Documentation

Full architecture source of truth:

docs/ARCHITECTURE.md

README remains shorter and includes:

Problem  
Solution  
Architecture  
MVP features  
Hardware  
Privacy model  
Evaluation  
Limitations  
Demo

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

12. Event policies are accessed through an injectable EventPolicyRegistry/provider.

13. The production EventPolicyRegistry is the default dependency.

14. Validators and the Step 2 repository must not depend exclusively on an immutable module-level policy constant.

15. Test-only policy registries may be injected without mutating production configuration.

16. All five currently supported production Step 2 care event types are HIGH risk.

17. `auto_log_eligible` is False for every production Step 2 event type.

18. No care event type is assumed safe for automatic confirmation.

19. LOW and MEDIUM remain valid `RiskLevel` enum values for test-only overrides and possible deliberate future policy changes.

20. Production Step 2 policy must not assign LOW or MEDIUM to any supported care event.

21. Risk is derived through policy lookup rather than trusted from an incoming event payload.

22. Auto-log eligibility is derived through policy lookup rather than trusted from an incoming event payload.

23. A caller cannot make an event safer by supplying a different risk value.

24. Amendments perform a fresh policy lookup from the new event's own event type.

25. An amendment never inherits risk from the event it amends.

26. Auto-log eligibility is explicit configuration and is never inferred from LOW risk or from an event type's name.

27. EventSource explicitly distinguishes human-initiated from AI-derived sources.

28. `voice` is human-initiated.

29. Every confirmed event requires `verified_at` and `verification_method`.

30. `manual_entry` is valid only for human-initiated sources.

31. `confirm_button` may verify human-initiated or AI-derived events.

32. `dashboard` may verify human-initiated or AI-derived events.

33. `auto_logged` is valid only when the source is AI-derived, policy-derived risk is not HIGH, and the active policy has `auto_log_eligible=True`.

34. The `auto_logged` branch is intentionally unreachable under the production Step 2 policy.

35. Scenario P exercises the `auto_logged` validator through an injected test-only policy registry so the guardrail remains tested.

36. Scenario Y must use the untouched default production policy registry.

37. Scenario Y must not manually supply `risk_level` or `auto_log_eligible`.

38. Scenario Y proves that the real production policy derives HIGH risk and disabled auto-logging for repositioning.

39. AI-derived HIGH-risk events require explicit human verification.

40. Human-initiated HIGH-risk events may be manually entered.

41. Manual logging always exists through LOG.

42. Event time and record time are separate.

43. Late event reporting is valid.

44. Approximate event times are represented honestly.

45. All datetimes are timezone-aware.

46. Persisted timestamps use UTC.

47. `ended_at` cannot precede `started_at`.

48. Materially future event times are rejected.

49. `evaluation_metadata` is optional.

50. Denied AI proposals remain available for evaluation.

51. Proposal expiry is deterministic and testable.

52. Proposal timeout comes from the active event policy.

53. Scenario N tests risk recomputation in both directions using an injected test-only LOW/HIGH policy registry.

54. Scenario N Case 1 requires parent LOW and child HIGH.

55. Scenario N Case 2 requires parent HIGH and child LOW.

56. Both Scenario N directions are required so a copy-from-parent implementation cannot pass accidentally.

57. Scenario P proves that the generic validator can support auto-logging under an explicit test-only policy override.

58. Scenario Y proves that auto-logging is OFF under the real Step 2 production policy.

59. If auto-logging is ever introduced later, it is a deliberate policy change that must be justified by evaluation evidence.

60. No event type is currently pre-approved for future auto-logging.

61. Confirmation burden is a first-class product metric because every AI-derived event currently requires human confirmation.

62. Confirmation rate, confirmation latency, correction rate, and proposal frequency must be measured during evaluation.

63. Missed and unknown are different states.

64. Sensing coverage influences care-state conclusions.

65. Ambient audio alone does not initially create care events.

66. Continuous raw media is not the primary care record.

67. Raw media is discarded by default after useful structured information is extracted.

68. V1 privacy is honestly described as software-controlled sensing/privacy mode.

69. Device API requests are authenticated.

70. Device tokens are stored hashed.

71. V1 is single-recipient and single-primary-device.

72. Recap always works without an LLM.

73. LLMs may phrase facts but may not establish facts.

74. MVP functionality does not depend on computer vision.

75. Vision is an automation layer on top of a trustworthy event-record system.

76. AI should reduce caregiver workload rather than add it.

77. Policy configuration and generic validation logic remain separate so future policy changes do not require rewriting domain validators.

78. Tests must not mutate shared global production policy state.

79. Any new issue discovered from this point becomes a failing test rather than another architecture-planning cycle.