# PRD — Agents (§15 Harness, Hermes, Paperclip, Honcho)

**D-47 implementation, 2026-10-17:** the owner authorizes the private GHCR
candidate publisher implementation, separately from publication. The
[publisher contract](plans/API_CANDIDATE_PUBLISHER.md) adds isolated build/scan
and daemonless package-write jobs, encrypted artifact transfer, source/owner/
expiry checks, private-package/digest read-back and named reproducibility-gap
handling. M7-E011 records 56 scoped offline tests (24 new publisher cases) and
lint/format/strict typing. Exact-head CI is recorded on the feature PR.
The checked-in package ID, age recipient and access-review fields remain unset:
no operational configuration or publication pass is implied. Merge, dedicated
publication-environment/key/package verification and any actual build/push need
their separate gates. Parent delivery stays IN_PROGRESS. No workflow dispatch,
VPS, deployment, real-secret provisioning or provider action; live M7/Qwen denied.
The earlier D-46 design-only status is historical, superseded for implementation
scope only; its captured build evidence and unresolved gaps remain valid.


> Source of truth for all AI agent specifications.

## Current Orchestration Checkpoint (D-42 through D-46, 2026-10-17)

**D-46 review, 2026-10-17:** the single secret-free API build passed in
[run 38995824366](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38995824366),
attempt 1, at source/workflow SHA `0c96e33ac887b536ef4f947b9f4c7cbb395b80f9`.
M7-E010 and the [evidence review](reports/API_BUILD_EVIDENCE_REVIEW_20261017.md)
verify source/download/config-ID correlation and scoped cleanup. The image was
removed; a rebuild needs new artifact-specific evidence. Publication remains
BLOCKED pending the [proposed contract](plans/API_CANDIDATE_PUBLICATION_GATE.md),
target/access decisions, scoped publisher and image security/provenance evidence.
Parent delivery stays IN_PROGRESS pending handoff acceptance. Merge, a new build
and publication remain separate gates. This records-only review repeats no
dispatch, touches no VPS and calls no provider. Live M7/Qwen stay disabled.
Earlier preparation checkpoints below are historical.

**D-45:** PR #26 merged at `f8e7cb9a548e9956a0f1f74edc6f73e8fd2a76ef`;
post-merge CI 38924063418 passed all five jobs. The
[manual build route](plans/API_IMAGE_BUILD_ONLY.md) is prepared through a new PR,
with 31 offline cases (M7-E009). It binds owner/main/source, uses no application
secrets, prepares a local image without publication/start, and records receipts
and scoped cleanup. Exact-head CI, merge and actual dispatch remain separate.
Delivery stays IN_PROGRESS; live M7/Qwen and provider/VPS actions remain denied.
Earlier D-44 preparation statements are historical.

**Controlling closeout, 2026-10-16 (D-42):** Staging Secret Availability is
**COMPLETE for DeepSeek presence only**, supported by M7-E006 and
[run 38903102158](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38903102158) on reviewed merge `bc135b8b605cd96c2bacaf228953d1cbf14ba3ca`.
The selected key was available to its GitHub Actions step; provider validity,
dedicated ownership, target injection, effective egress, spending enforcement and
trusted live authorization remain unverified. OpenRouter presence was skipped,
not accepted. Live M7 and Qwen remain **BLOCKED**; D-33 remains pending.

**D-44 continuation, 2026-10-16:** after PR #25 merge and post-merge CI, the
owner authorizes the next API preparation stage. The
[delivery preparation contract](plans/API_DELIVERY_PREPARATION.md) implements
an isolated context from committed Git objects, existing API hash-lock consumption
and synthetic Compose/settings validation. M7-E008 records 16 passing offline
tests and scoped lint/format/strict-type checks. Exact resulting-head CI must be
recorded on the feature PR after execution; review and merge remain separate.
The parent delivery task is IN_PROGRESS because image build/download provenance,
the bounded manual build route and later acceptance remain unfinished.

The accepted DeepSeek presence gate remains complete under M7-E006; do not rerun
accepted presence/database/VPS proofs. No API guard is weakened and no production
contract is invented. No real-secret dispatch/injection, image start/publication,
VPS/service/synthetic activation, deployment, provider call, live M7 or Qwen
execution is included. D-33 and manual refund approval remain controlling.

The presence result grants no agent, tool, assignment or financial capability.
The next phase prepares source/build/manifest evidence, not runtime registration
or a change to the orchestration authority model. See M7-E006 in
[TEST_EVIDENCE.md](TEST_EVIDENCE.md) and the current
[tracker](EXECUTION_TRACKER.md).

## Historical Development Boundary (D-37/D-38, 2026-10-09)

M6 is development complete under D-36; staging/live acceptance remains
UNVERIFIED. M7 live activation is BLOCKED and D-33 remains pending.
The synthetic shadow harness grants only
`order_management / recommend_drivers / recommend_drivers`, checked against
the existing `read:drivers` capability before execution. Broader legacy
capability rows below do not grant shadow access. It accepts only synthetic
numeric fixtures and a built-in fake, reuses `recommendations.py`, and compares
advisory ranks against backend shortlist order without rematching or assignment.
There is no active API/worker registration, operational port, live provider or
persistence. This is neither runtime authentication nor an in-process sandbox.

### Synthetic recommendation reviews (D-38)

`workers/src/zippy_workers/recommendation_reviews.py` adds an unregistered
`FakeReviewStore`, reusing `evaluate_shadow` and `RecommendationResult`.
`create` takes an immutable `SyntheticCandidateSnapshot` (explicit synthetic
version and ordered `SyntheticMatch` features), built-in fake agent, creation
time, expiry and recommendation timeout. The stored ranking is generated by
the existing shadow contract; callers cannot inject a review result.

Reviews start `pending`. Only `FakeReviewer.HUMAN_A` and `HUMAN_B` may submit
`accepted` or `rejected`; fake agents, outsiders and identity strings are denied.
Acceptance requires a candidate reference from the stored recommendation and
records only `advisory_preference`. Rejection records no preference. It grants
no assignment, financial or Paperclip authority.

`review` requires the exact current snapshot, including version, candidate order,
distance and score. Positional candidate references alone do not bind a review.
Changed versions, reordered/changed features and different candidate counts are
stale even if candidate references are reused. `get` or a decision attempt at
or after `expires_at` transitions a pending record to `expired`; reads before
that boundary remain pending. Timestamps must be timezone-aware; backwards
transition time is rejected. Expiry never reverses an accepted/rejected review.

Review IDs deduplicate identical creation inputs without resetting the current
record. Submission `idempotency_key` values are store-wide and bind review ID,
exact snapshot, fake reviewer, decision and preference. Identical retries return
the original result, including after expiry; mismatched keys, new submissions
against terminal records, stale snapshots and unauthorized replay attempts raise
explicit errors. Retry time is not part of the payload. Fake storage is memory
only, single-process and non-durable; caller-supplied fake identity, snapshot and
time are test inputs, not runtime authentication, provenance or a trusted clock.

Customers book; vendors supply vehicles/drivers; transport companies may act as
either role per transaction. Deterministic backend assignment remains
authoritative. Every refund requires manual approval; settlement and Paperclip
decision-lock controls are unchanged. No live providers, hosting changes,
deployment, shared-database SQL, agent activation or merge are authorized.

### Isolated OMS staging bridge (D-39)

`workers/src/zippy_workers/recommendation_provider.py` implements the existing
recommendation protocol for an explicitly configured OpenAI-compatible HTTPS
endpoint, dedicated provider key and exact model ID. There are no endpoint/model
defaults, retries, redirects, provider routing or automatic activation.

`workers/scripts/run_oms_recommendation.py --run-synthetic-shadow` is a separate
finite runner, not an API route, worker CLI command or registry entry. It uses
three already-eligible synthetic numeric fixtures in shortlist order and reuses
the existing deterministic baseline and complete-permutation validator. It does
not run the SQL matcher, establish live eligibility, assign a driver or confer
review/governance authority. D-37/D-38's built-in fake restrictions are unchanged.

The CLI rejects every environment variable except its five dedicated
configuration names and a small interpreter/locale allowlist; it never loads
`.env`. Candidate/configuration preflights precede serialization; responses use
bounded raw identity-encoded bytes, without decoder/chunker buffering. Each run
permits one request under a single deadline: half the configured budget is
reserved for cancellation and concurrent response/client cleanup. Cleanup is
shielded from caller cancellation and failures are explicit, not successful
reports. Reports contain only opaque rankings and explicit
fallback/provider outcomes. No telemetry adapter or legacy tracer is created.
This is an isolation preflight, not a sandbox for untrusted Python; staging must
also restrict process identity, filesystem access and network egress.

M7-E003 is mocked HTTP development evidence only. See
[the configuration and bounded live plan](plans/M7_OMS_STAGING_BRIDGE.md).
Live provider/model/credential approval and M6 staging gates remain separate;
M7 activation stays BLOCKED and D-33 pending. Deterministic assignment, manual
approval for every refund, settlements and Paperclip controls are unchanged.

## 1. Agent Architecture

### 7 + 1 Agent System

| # | Agent | Role | Goal |
|---|-------|------|------|
| 1 | Customer Service | Unified customer interface | Single point of contact for all customer needs |
| 2 | Order Management | Lifecycle orchestration | Order-to-provider matching, workflow automation |
| 3 | Transportation | Route optimization | Real-time tracking, ETA calculation, incident response |
| 4 | Resource Management | Fleet + company relationships | Vehicle/driver availability, inter-company coordination |
| 5 | Payment & Settlement | Financial transactions | Payment processing, commission calculation, settlements |
| 6 | Platform Administration | Governance + compliance | System oversight, policy enforcement, AI regulation |
| 7 | Communication | Multi-channel notifications | Push, SMS, email, in-app messaging |
| 8 | Document Processing | OCR + document management | POD capture, document verification, cloud storage |

## 2. Correct Target Flow

```
Client / FlutterFlow / Next.js
    ↓
FastAPI / Switch Point API
    ↓
validation + authentication + authorization
    ↓
Supabase/PostgreSQL operational transaction
    ↓
queue / worker / background execution where required
    ↓
Paperclip governance
    ↓
Hermes approved tool execution
    ↓
Odoo / Razorpay / communications / other external system
    ↓
result persisted into Zippy operational state
    ↓
API / realtime update to clients
```

## 3. Component Roles

| Component | Role | Scope |
|-----------|------|-------|
| **Qoder Wake** | Backend engineering/execution | Code generation, API implementation, tests, migrations |
| **Paperclip** | Governance authority | Approve/reject high-impact decisions |
| **Hermes** | Approved tool execution | Execute approved API calls, tool invocations |
| **Odoo 18** | ERP / financial system of record | Invoices, payments, settlements |
| **Apidog/OpenAPI** | API contract | Endpoint definitions, schemas, responses |

### Qoder Wake Role

Qoder Wake is the backend engineering and autonomous execution environment responsible for:
- Backend code generation and maintenance
- API implementation
- Service-layer implementation
- Database-access-layer implementation
- Integration adapters
- Background worker implementation
- Tests
- Migrations
- Operational bug fixing
- Implementation of Paperclip/Hermes interfaces
- Implementation of Apidog/OpenAPI contracts

Qoder Wake must obey the system boundaries defined in this architecture.

**Qoder Wake is NOT:**
- The system of record
- The governance authority
- The financial ledger
- The API contract owner
- A replacement for PostgreSQL transaction guarantees

## 4. Agent Service Layer

### Base Class

```python
class BaseAgentService(ABC):
    agent_name: str  # Auto-derived from class name
    
    @abstractmethod
    def process_task(self, task_data: dict) -> dict:
        """Process a task assigned to this agent"""
        pass
    
    def log_activity(self, action, details, user=None):
        """Log agent activity to ai_agent_activities"""
        pass
    
    def communicate_with_agent(self, target_agent, message_data):
        """Send message to another agent via Redis queue"""
        pass
```

### Communication

- **Transport**: Redis message queue (`agent_messages`)
- **Format**: JSON with `from_agent`, `to_agent`, `message_data`, `timestamp`, `message_id`
- **Processing**: Background task (`process_agent_messages`) polls queue
- **Logging**: All communications logged to `agent_communication_log`

## 5. LoopGuardian (Safety Gates)

Every agent task passes through LoopGuardian before execution:

| Gate | Description | Action on Failure |
|------|-------------|-------------------|
| **Cap** | Max tool calls per tick (default: 20) | Pause agent, log intervention |
| **Malformed** | Invalid/malformed query detection | Reject task, log intervention |
| **Hallucination** | Output anomaly detection | Suspend agent, notify admin |
| **Infinite Loop** | Repetitive action detection | Break loop, log intervention |
| **Budget** | Daily USD spend limit | Pause agent until next day |

## 6. Agent Capabilities Matrix

| Agent | place_order | assign_driver | update_delivery | match_drivers | generate_quote | validate_payment | process_document | send_notification |
|-------|:-----------:|:-------------:|:---------------:|:-------------:|:--------------:|:----------------:|:----------------:|:-----------------:|
| customer_service | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| order_management | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| transportation | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| resource_management | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| payment_settlement | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| platform_administration | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| communication | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| document_processing | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |

## 7. Task Queue

### Durable Queue (`agent_tasks`)

- **Claim**: `SKIP LOCKED` for concurrent safety
- **Priority**: 1 (critical) → 5 (background)
- **Retry**: 3 attempts before dead-letter
- **Deduplication**: `dedupe_key` unique constraint
- **Timeout**: Configurable per agent

### Task States

```
pending → claimed → completed
                  → failed → retry → failed → retry → failed → dead_letter
```

## 8. Hermes (DeepSeek Integration)

### Features

- DeepSeek V4 Pro for complex planning
- DeepSeek V4 Flash for fast execution
- OpenRouter routing for model selection
- Fallback chain: DeepSeek → OpenAI → Anthropic

### Model Routing

| Task Type | Model | Rationale |
|-----------|-------|-----------|
| Complex planning | `deepseek-v4-pro` | Accuracy priority |
| Fast execution | `deepseek-v4-flash` | Speed priority |
| Vision tasks | `MODEL_VISION` | PRD R1 TBD |

### Hermes Constraints

- Gets narrowly scoped capabilities only
- Never receives admin credentials
- Cannot bypass Paperclip governance
- Must read `Retry-After` headers and respect rate limits
- Cannot hammer services blindly

## 9. Paperclip (Decision Framework)

### Features

- Deterministic decision trees for business logic
- HITL (Human-in-the-Loop) for high-impact decisions
- Decision locks to prevent agent self-approval
- Audit trail for all decisions

### Decision Categories

| Category | Auto/HITL | Examples |
|----------|-----------|----------|
| Pricing | Auto | Quote generation, commission calculation |
| Assignment | Auto | Driver matching, vehicle selection |
| Payment | HITL | Refunds > ₹10,000, disputes |
| Suspension | HITL | User/account suspension |
| Compliance | HITL | Policy violations, fraud alerts |

### Paperclip Enforcement

`X-Decision-ID` header is **mandatory** for actions requiring Paperclip approval. This reinforces the governance model:
1. Hermes proposes
2. Paperclip approves
3. Only then does Zippy or Odoo execute

## 10. Honcho (Memory System)

### Features

- Long-term memory for agent interactions
- Customer preference learning
- Context retention across sessions
- Semantic search over conversation history

### Deployment Options

| Option | Pros | Cons |
|--------|------|------|
| Self-hosted | Full control, no vendor lock | Infrastructure overhead |
| Managed | Easy setup, maintenance included | Vendor dependency, cost |

**Decision**: R9 pending — Self-hosted recommended for control.

## 11. Agent Activity Monitoring

### Activity Log (`ai_agent_activities`)

- Agent name + type
- Activity type + details
- Input/output data
- Confidence score
- Execution time (ms)
- Status (pending/completed/failed/interrupted)

### Intervention Log (`ai_agent_interventions`)

- Intervention type (hallucination, error_correction, performance_issue, anomaly_detection)
- Detection method
- Original vs corrected output
- Confidence scores before/after
- Resolution status

### Admin Dashboard

- Real-time agent performance metrics
- Hallucination detection alerts
- Model retraining triggers
- Algorithm adjustment interface

## 12. Integration Points

| System | Agent | Integration |
|--------|-------|-------------|
| Odoo 18 CE | order_management, resource_management | JSON-RPC, invoice sync |
| Razorpay | payment_settlement | Webhook + API |
| Mapbox | transportation | Directions + Traffic API |
| Langfuse | All agents | Observability + tracing |
| DeepSeek | All agents | LLM inference via OpenRouter |
| Tesseract | document_processing | OCR extraction |
| Twilio/Resend | communication | SMS + Email delivery |
| Apidog | All agents | API contract enforcement |

