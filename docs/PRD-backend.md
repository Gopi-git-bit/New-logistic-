# PRD — Backend (§7, §8, §9 FastAPI, Supabase, RPCs, Webhooks, Idempotency)

> Source of truth for all backend specifications.

## 1. Backend Architecture

**Primary API Layer**: FastAPI
**Database**: Supabase (PostgreSQL 16 + PostGIS + pgvector)
**Backend Engineering**: Qoder Wake
**Governance**: Paperclip
**Tool Execution**: Hermes
**ERP**: Odoo 18 CE (system of record)
**API Contract**: Apidog/OpenAPI

**Forbidden**: Django, n8n, Kafka, Celery, Temporal (per PRD v2 canonical decisions)

## 2. Request Flow

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

## 3. Supabase RPC Functions

### Order Lifecycle
- `transition_order(order_id, new_status, actor_id, actor_role, reason)` — SECURITY DEFINER state machine
- `generate_order_quote(order_id)` — Calculates pricing, persists amounts, emits event
- `assign_order_provider(order_id, provider_id, provider_type)` — Sets provider, updates status
- `validate_payment_plan(mode, total_amount, advance_amount)` — Returns boolean

### Resource Management
- `match_nearby_drivers(pickup_location, radius_m, limit, required_class, cargo_weight)` — PostGIS spatial query, returns scored candidates

### Agent Control Plane
- `enqueue_agent_task(agent_name, task_type, payload, dedupe_key, priority)` — Idempotent task creation
- `claim_agent_task(agent_name)` — SKIP LOCKED claim with timeout
- `complete_agent_task(task_id, result)` — Mark success
- `fail_agent_task(task_id, error, retryable)` — Mark failure, dead-letter after 3 retries
- `spend_agent_budget(agent_name, amount_usd)` — Deduct from daily budget
- `pause_agent(agent_name, reason)` — Soft pause (fast-path skip)
- `resume_agent(agent_name)` — Remove pause

### Payment Rules
- `validate_payment_plan(p_mode, p_total_amount, p_advance_amount)` — Full=100%, partial≥50%, to_pay=0

### Document Processing
- `upsert_order_document(order_id, document_type, storage_path, ocr_text, metadata)` — Idempotent document insert
- `enqueue_notification(channel, recipient, template_key, payload, idempotency_key)` — Idempotent notification
- `grab_notification_jobs(limit)` — SKIP LOCKED batch grab
- `mark_notification_sent(job_id)` — Mark delivered
- `mark_notification_failed(job_id, error)` — Exponential backoff, permanent failure ladder

### Webhook Pipeline
- `sweep_dead_webhooks()` — Mark stuck webhooks as dead
- `revive_dead_webhooks()` — Retry dead webhooks
- `stale_processing_payments()` — Detect stuck payments

## 4. Webhook Integration

### Razorpay Webhooks
- **Endpoint**: `/api/webhooks/razorpay` (public, POST)
- **Verification**: HMAC-SHA256 constant-time compare
- **Replay safety**: `webhook_events.idempotency_key` unique constraint
- **Flow**: Verify → Classify event → ACK 200 → Enqueue agent task

### Event Types
- `payment.captured` → Advance payment received → transition to `payment_succeeded`
- `payment.failed` → Payment failed → retry logic
- `payment.refunded` → Refund processed → update financial records

## 5. Idempotency Patterns

| Operation | Idempotency Key | Table |
|-----------|----------------|-------|
| Order booking | `idempotency_key` | `orders` |
| Payment capture | Razorpay `payment_id` | `payments` |
| Webhook processing | `event_id` | `webhook_events` |
| Agent task creation | `dedupe_key` | `agent_tasks` |
| Notification | `idempotency_key` | `notification_queue` |
| Document upload | `order_id + document_type` | `order_documents` |

## 6. Background Execution Architecture

### Durability Without Temporal

The repository uses PostgreSQL queues + Python workers for background execution:

| Workflow | Trigger | State | Worker | Retry | Idempotency | Locking | Terminal State | Recovery |
|----------|---------|-------|--------|-------|-------------|---------|----------------|----------|
| Agent tasks | `enqueue_agent_task()` | `agent_tasks` table | `claim_agent_task()` | 3 attempts | `dedupe_key` | SKIP LOCKED | dead_letter | Manual review |
| Notifications | `enqueue_notification()` | `notification_queue` | `grab_notification_jobs()` | Exponential backoff | `idempotency_key` | SKIP LOCKED | permanent_failure | Manual review |
| Odoo sync | Payment event | `orders.odoo_sync_status` | `handlers.py` | 3 attempts | Order ID | SELECT FOR UPDATE | sync_failed | Retry button |
| Webhooks | External HTTP | `webhook_events` | `sweep_dead_webhooks()` | Revive once | `event_id` | SKIP LOCKED | dead | Manual review |
| Payment reconciliation | Scheduled | `payments` | `stale_processing_payments()` | None | Payment ID | SELECT FOR UPDATE | stuck | Admin alert |

### Worker Recovery

Each worker type implements:

1. **Triggering event**: What starts the job
2. **Persisted state**: Database record tracking job status
3. **Worker/consumer**: Which process handles it
4. **Retry policy**: How many retries, backoff strategy
5. **Idempotency mechanism**: How duplicates are prevented
6. **Locking/concurrency**: How concurrent access is handled
7. **Terminal failure state**: What happens when all retries exhausted
8. **Recovery mechanism**: How to recover from failure
9. **Audit/observability**: How to track job execution
10. **Compensation behavior**: How to undo if needed

## 7. Security

### Row Level Security (RLS)

- Users read/update only their own `users` row
- Customers see only their own orders and profiles
- Drivers see only their own profile, assigned orders, telemetry
- Transport companies see their own company and assigned orders
- Admins have full read access
- Telemetry INSERT open to authenticated service accounts

### Authentication

- Supabase Auth (JWT tokens) for client-facing APIs
- Service identity for internal Zippy services
- Dedicated agent identity for Hermes
- Separate governance identity for Paperclip
- Isolated integration credential for Odoo connector

### API Security

- Service role key never exposed to client
- Webhook HMAC verification
- Rate limiting on public endpoints
- See `docs/API-RELIABILITY-SECURITY.md` for full contract

## 8. Qoder Wake Integration

Qoder Wake is the backend engineering and autonomous execution environment. It implements:

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

### Qoder Wake Constraints

- Must NOT be the system of record
- Must NOT be the governance authority
- Must NOT be the financial ledger
- Must NOT replace PostgreSQL transaction guarantees
- Must NOT sit inside every runtime business transaction
