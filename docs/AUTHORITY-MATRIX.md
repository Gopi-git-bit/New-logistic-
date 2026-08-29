# Zippy Logistics — AUTHORITY MATRIX

> **Every agent MUST consult this matrix before proposing or executing any state-changing operation.**
> Violations are treated as governance failures and escalated to Paperclip for blocking.

---

## 1. System-of-Record Hierarchy

| System | Role | Owns (Source of Truth) | Trust Level |
| --- | --- | --- | --- |
| **Zippy (Supabase/PostgreSQL)** | Operational Truth | Users, drivers, vehicles, orders, trips, telemetry, matching, operational events, agent tasks, POD state. | Full — operational data |
| **Odoo 18 CE** | Financial/ERP Truth | Invoices, general ledger, accounting, verified ERP partners, financial settlements, tax state. | Full — financial records |
| **Paperclip** | Governance Truth | Decision IDs, agent IDs, proposed actions, risk levels, policy results, HITL approvals, decision locks. | Full — governance decisions |
| **Hermes** | Approved Execution | Tool execution within allowlisted capabilities, decision-linked mutations only. | Delegated — never source of truth |
| **Langfuse** | Observability | LLM traces, token costs, tool execution telemetry, reasoning logs. | Append-only — never mutated |
| **Honcho** | Agent Memory | Conversation context, customer preferences, long-term interaction memory. | Advisory — DB state always wins |

### Authority Inheritance Rule

Authority is **domain-specific**, not absolute. Each system is supreme in its domain:

| Domain | Supreme Authority | Why |
| --- | --- | --- |
| Financial/accounting state | **Odoo** | Odoo owns the ledger, invoices, reconciliation |
| Operational state | **Zippy DB** | Orders, trips, drivers, POD, delivery state |
| Governance decisions | **Paperclip** | Whether an action was permitted |
| Execution capability | **Hermes** | Delegated tool execution with grants |

When two systems disagree about a fact in **their own domain**, that system wins.
When a system tries to mutate **another system's domain**, governance blocks it.

```text
Paperclip decides WHAT MAY execute.
Hermes executes WHAT WAS APPROVED.
Odoo owns financial truth.
Zippy owns operational truth.
Honcho is advisory only.
Langfuse is evidence only.
```

---

## 2. Read/Write Permission Matrix

### 2.1 System Write Permissions

| System | Can Write To | Must NOT Write To |
| --- | --- | --- |
| **Zippy DB** | Operational state, operational payment references (`odoo_invoice_id`), agent tasks, POD status transitions. | Odoo ledger truth, Paperclip governance decisions, financial settlement amounts. |
| **Odoo DB** | Invoices, ledger, accounting, ERP partners, settlements, tax records. | Operational trip state, driver telemetry, Zippy user profiles, POD status. |
| **Paperclip DB** | Governance decisions, approvals, locks, policy results, HITL queues. | Orders, invoices, vehicle state, business logic, operational state. |
| **Hermes** | Proposals/tasks through approved, narrowly-scoped tools (via Composio/MCP). | **Direct DB mutation** (no raw SQL, no direct API calls bypassing Paperclip). |
| **Langfuse** | Traces, costs, tool telemetry (append-only). | Business transactions, financial records, operational state. |
| **Honcho** | Contextual memory (advisory only). | Authoritative business state (DB state always overrides Honcho memory). |

### 2.2 Agent Write Permissions

| Agent | Can Propose | Can Execute (via Hermes) | Cannot Touch |
| --- | --- | --- |--- |
| **order_management** | Place order, assign driver, update delivery status | `place_order`, `assign_driver`, `update_delivery_status` | Financial instruments, invoices, settlements |
| **payment_settlement** | Process payment, record payment, reconcile | `process_payment`, `record_payment`, `reconcile_payment` | Order assignment, driver matching |
| **transportation** | Match drivers, confirm picking | `match_drivers`, `confirm_picking` | Financial instruments, user management |
| **communication** | Send notification, process document | `send_notification`, `process_document` | Financial instruments, order modification |
| **resource_management** | Create partner, find partner | `create_partner`, `find_partner` | Financial instruments, order state |
| **platform_administration** | CRUD operations within scope | All allowlisted tools | Financial instruments (requires HITL) |
| **customer_service** | Read-only queries, escalate to HITL | `send_notification` only | Direct state mutation |

---

## 3. The Golden Rule of Execution Flow

For **high-risk/financial operations** (e.g., creating an invoice, processing a settlement):

```
1. Hermes PROPOSES the action with required parameters.
2. Paperclip EVALUATES the proposal against policy (AUTO / HITL / BLOCKED).
3. If APPROVED → approved capability is passed to the target system (Odoo API / Zippy DB).
4. Target system EXECUTES and becomes the authoritative record.
5. Zippy DB records ONLY the operational reference (e.g., odoo_invoice_id = "INV-123").
6. Langfuse RECORDS the trace of the entire sequence.
```

### Execution Chain Diagram

```
┌─────────┐     ┌───────────┐     ┌──────────┐     ┌────────┐     ┌─────────┐
│  Agent   │────▶│  Hermes   │────▶│Paperclip │────▶│ Odoo / │────▶│ Langfuse│
│ (propose)│     │ (validate)│     │ (govern) │     │ Zippy  │     │ (trace) │
└─────────┘     └───────────┘     └──────────┘     └────────┘     └─────────┘
                     │                  │                │
                     │                  ▼                │
                     │            ┌──────────┐          │
                     │            │   HITL   │          │
                     │            │ (human)  │          │
                     │            └──────────┘          │
                     │                                  │
                     └──────── FAIL CLOSED ─────────────┘
                     (Paperclip error → REJECT, not ALLOW)
```

### Forbidden Execution Paths

```text
❌ Hermes → Direct Supabase SQL → Direct Odoo SQL → Paperclip record
❌ Agent → Direct DB mutation → Paperclip after-the-fact
❌ Any system → Financial settlement without Paperclip APPROVE
❌ Hermes → Odoo write without decision_id
❌ Zippy DB → Financial ledger mutation (only Odoo owns ledger)
❌ Honcho → Override DB state (memory is advisory only)
```

### Allowed Execution Paths

```text
✅ Agent → Hermes → Paperclip → Hermes execute → Odoo API → Zippy DB ref
✅ Agent → Hermes → Paperclip → Hermes execute → Zippy DB operational write
✅ Agent → Zippy DB direct read (no governance needed for reads)
✅ Any system → Langfuse trace append (observability, no governance)
✅ Any system → Honcho memory write (advisory, no governance)
```

---

## 4. Failure Handling Rules

### 4.1 Paperclip Failures

| Failure Type | Behavior | Rationale |
| --- | --- | --- |
| Paperclip timeout | **REJECT** the proposal | Fail closed — unknown governance = blocked |
| Paperclip network error | **REJECT** the proposal | Fail closed — cannot verify policy |
| Paperclip 5xx error | **REJECT** the proposal | Fail closed — service degraded |
| Paperclip returns HOLD | **Wait** for HITL resolution | Respect governance decision |
| Paperclip returns HUMAN_REVIEW | **Queue** for human review | Do not auto-escalate |

### 4.2 Hermes Failures

| Failure Type | Behavior | Rationale |
| --- | --- | --- |
| Tool not in allowlist | **REJECT** — never execute | Security boundary |
| Hermes timeout | **REJECT** — retry via idempotency key | Deterministic replay |
| Hermes network error | **REJECT** — retry via idempotency key | Deterministic replay |
| Hermes execution fails | **Record** failure, do not retry | Agent handles error |

### 4.3 Target System Failures

| Failure Type | Behavior | Rationale |
| --- | --- | --- |
| Odoo API error | **Record** `odoo_failed` in Zippy DB | Preserve attempt state |
| Odoo timeout | **Record** `odoo_pending`, alert human | Financial system needs attention |
| Zippy DB write fails | **Mark** idempotency key as failed | Allow retry via idempotency |
| Razorpay webhook fails | **Record** `payment_pending` | Payment reconciliation needed |

### 4.4 Idempotency Guarantees

```
- Duplicate request with same key  → return cached response (NO re-execution)
- Duplicate request with different payload → 409 CONFLICT
- Failed request with same key → re-execute (idempotency marked failed)
- Expired idempotency key (> 24h) → treat as new request
```

---

## 5. HITL Escalation Paths

### When HITL Is Required

| Risk Level | Threshold | Trigger | Escalation Target | SLA |
| --- | --- | --- | --- | --- |
| **CRITICAL** | ≥ ₹100,000 | Any financial settlement | Finance head + Admin | 1 hour |
| **HIGH** | ≥ ₹25,000 | Invoice creation, refund, credit note | Finance team | 4 hours |
| **MEDIUM** | ≥ ₹5,000 | Vendor bill, payment reconciliation | Operations lead | 12 hours |
| **LOW** | < ₹5,000 | Standard operations | Auto-approve (no HITL) | N/A |
| Any | — | New driver onboarding | Operations team | 24 hours |
| Any | — | Invoice dispute | Finance team | 12 hours |
| Any | — | Agent budget exhaustion | Admin team | Immediate |
| Any | — | Paperclip HOLD decision | Assigned reviewer | Per policy |
| Any | — | Unknown tool invocation | Security team | Immediate |

### Risk Level Assignment

| Risk Level | Criteria |
| --- | --- |
| **CRITICAL** | Financial amount ≥ ₹100,000 OR involves posted accounting records OR reversal of reconciled payment |
| **HIGH** | Financial amount ≥ ₹25,000 OR creates customer-facing invoice OR modifies settlement |
| **MEDIUM** | Financial amount ≥ ₹5,000 OR vendor bill OR payment matching |
| **LOW** | Financial amount < ₹5,000 AND standard operational flow |

### HITL Resolution Flow

```
1. Paperclip returns HITL / HOLD
2. Proposal queued in Paperclip HITL queue
3. Human reviewer notified via communication channel
4. Reviewer approves / rejects / modifies
5. Decision recorded in Paperclip with reviewer ID
6. Original agent receives decision via callback
7. Agent proceeds or aborts based on decision
```

### Auto-Escalation Rules

```text
- Unresolved HITL after 4 hours → escalate to admin
- Unresolved HITL after 24 hours → pause all agent operations
- Budget exhaustion → immediate pause, notify admin
- 3 consecutive governance rejections → pause agent, alert human
```

---

## 6. Migration and Rollback Rules

### Schema Migrations

| Rule | Description |
| --- | ---|
| Forward-only | No rollback migrations in production |
| Additive only | New columns, new tables — never remove columns in-place |
| Backward compatible | Old code must work with new schema |
| Validate before deploy | Run verification SQL suite before marking migration complete |

### Data Migrations

| Rule | Description |
| --- | --- |
| Idempotent | Migration scripts must be re-runnable |
| Reference preserving | Never delete records referenced by foreign keys |
| Audit logged | All data migrations logged to `migration_log` table |
| Human approval | Data migrations require Paperclip HITL approval |

### Rollback Protocol

```text
1. Stop all agent operations (pause agents)
2. Freeze the current state (snapshot)
3. Assess impact (which systems are affected)
4. Execute rollback in reverse dependency order:
   - Hermes → Paperclip → Odoo → Zippy DB
5. Verify each system's state matches pre-migration
6. Resume agent operations
7. Log rollback in DECISIONS.md
```

---

## 7. Cross-System Reference Rules

### Reference Ownership

| Reference | Owner | Consumer | Direction |
| --- | --- | --- | --- |
| `order_id` | Zippy DB | All systems | Zippy → Others |
| `odoo_invoice_id` | Odoo | Zippy DB (as reference only) | Odoo → Zippy |
| `paperclip_decision_id` | Paperclip | Hermes, Zippy DB | Paperclip → All |
| `razorpay_payment_id` | Razorpay | Zippy DB (as reference only) | Razorpay → Zippy |
| `hermes_execution_id` | Hermes | Paperclip, Zippy DB | Hermes → All |
| `driver_id` | Zippy DB | All systems | Zippy → Others |

### Reference Integrity Rules

```text
1. Never create a foreign key from Zippy DB to Odoo (Odoo owns its own IDs)
2. Store Odoo references as TEXT in Zippy DB (not as FK)
3. Paperclip decision IDs are immutable once created
4. Hermes execution IDs are unique per execution, never reused
5. All cross-system references must include a timestamp for staleness detection
```

---

## 8. Audit Trail Requirements

### Every State-Changing Operation Must Record

| Field | Source | Purpose |
| --- | --- | --- |
| `correlation_id` | Request header | End-to-end trace linking |
| `agent_id` | Agent self-identification | Accountability |
| `decision_id` | Paperclip | Governance audit |
| `execution_id` | Hermes | Execution audit |
| `timestamp` | System clock | Temporal ordering |
| `actor_id` | JWT subject | Human accountability |
| `actor_role` | JWT claim | Permission verification |

### Audit Log Retention

| System | Retention | Storage |
| --- | --- | --- |
| Zippy DB operational logs | 90 days | PostgreSQL |
| Odoo accounting logs | 7 years | Odoo DB |
| Paperclip governance logs | 1 year | Paperclip DB |
| Langfuse traces | 30 days | Langfuse |
| API request logs | 7 days | Application logs |

---

## 9. Enforcement Checklist

Before any state-changing operation, every agent MUST verify:

```text
□ Am I the correct agent for this operation? (role check)
□ Do I have a valid Paperclip decision_id? (governance check)
□ Is the target system in my write permission list? (boundary check)
□ Am I using the correct idempotency key? (determinism check)
□ Is my payload within the allowlisted tool scope? (security check)
□ Have I included all required headers? (contract check)
□ Is this operation logged to Langfuse? (observability check)
```

If ANY check fails → **ABORT** and escalate to Paperclip.

---

## 10. Decision Log Entries

This authority matrix was established as part of the following decisions:

| Decision | Document | Rationale |
| --- | --- | --- |
| D-09 | Backend Execution Model | FastAPI + Qoder Wake + Paperclip + Hermes + Odoo 18 |
| D-10 | Production API Key Wiring | Canonical env contract + config validation + secret redaction |
| D-11 | Authority Matrix | This document — system boundary enforcement |
