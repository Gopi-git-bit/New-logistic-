# PRD — Backend (§7, §8, §9 Supabase, RPCs, Webhooks, Idempotency)

> Source of truth for all backend specifications.

## 1. Backend Architecture

**Primary**: Supabase (Postgres RPC, RLS, Realtime)
**Secondary**: Next.js API routes (portal webhooks)
**Workers**: Python 3.11/3.12 headless runners

**Forbidden**: Django, FastAPI, n8n, Kafka, Celery (per PRD v2 canonical decisions)

## 2. Supabase RPC Functions

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

## 3. Webhook Integration

### Razorpay Webhooks
- **Endpoint**: `/api/webhooks/razorpay` (public, POST)
- **Verification**: HMAC-SHA256 constant-time compare
- **Replay safety**: `webhook_events.idempotency_key` unique constraint
- **Flow**: Verify → Classify event → ACK 200 → Enqueue agent task

### Event Types
- `payment.captured` → Advance payment received → transition to `payment_succeeded`
- `payment.failed` → Payment failed → retry logic
- `payment.refunded` → Refund processed → update financial records

## 4. Idempotency Patterns

| Operation | Idempotency Key | Table |
|-----------|----------------|-------|
| Order booking | `idempotency_key` | `orders` |
| Payment capture | Razorpay `payment_id` | `payments` |
| Webhook processing | `event_id` | `webhook_events` |
| Agent task creation | `dedupe_key` | `agent_tasks` |
| Notification | `idempotency_key` | `notification_queue` |
| Document upload | `order_id + document_type` | `order_documents` |

## 5. Worker Architecture

### Kernel (Heartbeat Loop)
- 15-second tick interval
- Claims tasks via `claim_agent_task()` (SKIP LOCKED)
- Dispatches to agent-specific handlers
- LoopGuardian gates: cap, malformed, hallucination, infinite-loop

### Handlers
- `place_order(payload, db)` → Quote → Validate → Status 'pending'
- `assign_driver(payload, db)` → Match → Assign → Status 'driver_assigned'
- `update_delivery_status(payload, db)` → Status advance (pickup/delivered)
- `process_document_upload(payload, db)` → OCR → Upsert → Auto-transition
- `process_notification_job(payload, db)` → Deliver → Mark sent/failed

### Agent Capabilities
| Agent | Allowed Tools |
|-------|---------------|
| customer_service | place_order, update_delivery_status, send_notification |
| order_management | place_order, assign_driver, update_delivery_status, generate_quote |
| transportation | update_delivery_status, match_drivers |
| resource_management | match_drivers, assign_driver |
| payment_settlement | validate_payment_plan |
| platform_administration | All (oversight) |
| communication | send_notification |
| document_processing | process_document_upload |

## 6. Security

### Row Level Security (RLS)
- Users read/update only their own `users` row
- Customers see only their own orders and profiles
- Drivers see only their own profile, assigned orders, telemetry
- Transport companies see their own company and assigned orders
- Admins have full read access
- Telemetry INSERT open to authenticated service accounts

### Authentication
- Supabase Auth (JWT tokens)
- `auth.uid()` / `auth.role()` stubs for vanilla Postgres

### API Security
- Service role key never exposed to client
- Webhook HMAC verification
- Rate limiting on public endpoints
