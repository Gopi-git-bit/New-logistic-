# Zippy Logistics — Soul (§0 Source of Truth)

> **Every agent MUST read this file before starting any task.**

## Core Philosophy

Zippy Logistics is an AI-augmented logistics platform that connects MSMEs/shippers with verified drivers and transport companies. The platform replaces the fragmented, phone-based logistics industry with a deterministic, auditable, and intelligent system.

## Business Goals

1. **Zero-touch order lifecycle** — Customer books → system prices → driver assigned → tracking → delivery → POD → settlement, fully automated with human-in-the-loop for exceptions only.
2. **Deterministic pricing** — Every quote is reproducible from inputs. No LLM hallucinated prices. Formula: `rate_per_km × distance + toll_bands + 3% loading + 5% GST`.
3. **Multi-role transport companies** — A single entity can be customer (place orders when under-capacity) and provider (accept orders when over-capacity). Role switching is explicit and audited.
4. **Commission transparency** — Drivers: 10% of total. Transport companies as providers: ₹700 flat service fee. Customers pay zero commission.
5. **Agent governance** — All AI agents operate under LoopGuardian constraints (cap, malformed-query, hallucination, infinite-loop detection). No agent can self-approve or bypass HITL.

## Non-Negotiables

| Rule | Description |
|------|-------------|
| **RLS is sacred** | Never bypass Row Level Security. Never add `SECURITY DEFINER` unless defined in PRD-database.md |
| **State machine is law** | Never mutate `orders.status` directly. ALWAYS use `transition_order()` RPC |
| **No hardcoded business logic** | Prices, tax rates, commission percentages live in the pricing engine (`packages/pricing/`) |
| **Idempotency is mandatory** | Every mutation must be idempotent. Use `idempotency_key` for bookings, payments, webhooks |
| **Agents don't approve themselves** | No agent can approve its own HITL decisions or bypass Paperclip decision-locks |
| **Odoo is system of record** | All financial data (invoices, payments, settlements) flows through Odoo 18 CE |
| **No Temporal** | Background execution via PostgreSQL queues + Python workers only |

## Architecture Decisions (Canonical)

- **No Kubernetes** — VPS + Docker Compose
- **No Kafka/Celery** — PostgreSQL LISTEN/NOTIFY + Python workers
- **No Temporal** — Background execution via PostgreSQL queues + Python workers
- **No n8n** — Python-native workflow orchestration
- **Razorpay primary, Stripe failover** — Payment processing
- **Hostinger VPS + Vercel** — Deployment

## Backend Execution Model

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

### Component Roles

| Component | Role |
|-----------|------|
| **FastAPI** | Application API layer |
| **Supabase/PostgreSQL** | Operational database |
| **Qoder Wake** | Autonomous backend engineering/execution layer |
| **Paperclip** | Governance authority |
| **Hermes** | Approved tool/API execution |
| **Odoo 18** | ERP / financial system of record |
| **Apidog/OpenAPI** | API contract |
| **Background Workers** | Async jobs where required by implemented architecture |

## Stack

| Layer | Technology |
|-------|------------|
| Frontend (Customer) | Next.js 15 App Router |
| Frontend (Admin/Driver) | Vite 6 + React 19 |
| Backend API | FastAPI |
| Backend Engineering | Qoder Wake |
| Governance | Paperclip |
| Tool Execution | Hermes |
| Database | PostgreSQL 16 + PostGIS + pgvector |
| AI Models | DeepSeek (primary), OpenRouter routing |
| Observability | Langfuse |
| ERP | Odoo 18 CE (system of record) |
| API Contract | Apidog/OpenAPI |
| Payments | Razorpay (primary), Stripe (failover) |
| Maps | Mapbox |
| Orchestration | Docker Compose (local), VPS (production) |

## Agent Hierarchy

```
1. Customer Service Agent     — Unified customer interface
2. Order Management Agent     — Lifecycle orchestration + matching
3. Transportation Agent       — Route optimization + real-time execution
4. Resource Management Agent  — Fleet + transport company relationships
5. Payment & Settlement Agent — Financial transactions + commissions
6. Platform Administration    — Governance, compliance, oversight
7. Communication Agent        — Multi-channel notifications
8. Document Processing Agent  — OCR, POD, document management
```

All agents operate under LoopGuardian constraints. No agent has unilateral power. The Platform Administration Agent has oversight authority over all other agents.

## Qoder Wake Scope

Qoder Wake is the backend engineering and autonomous execution environment. It is responsible for:

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

Qoder Wake must NOT:
- Be the system of record
- Be the governance authority
- Be the financial ledger
- Be the API contract owner
- Replace PostgreSQL transaction guarantees
- Sit inside every runtime business transaction

## Background Execution Review Criteria

For each asynchronous workflow, identify:

1. Triggering event
2. Persisted state
3. Worker/consumer
4. Retry policy
5. Idempotency mechanism
6. Locking/concurrency protection
7. Terminal failure state
8. Recovery mechanism
9. Audit/observability
10. Compensation behavior where applicable
