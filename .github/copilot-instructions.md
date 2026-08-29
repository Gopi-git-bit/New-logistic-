# Zippy Logistics — Copilot Agent Guardrails

> This file instructs AI coding agents (Copilot, Cursor, Claude Code, etc.) on how to behave in this repository.

## Core Rules

1. **Never mutate `orders.status` directly.** Always use the `transition_order()` RPC.
2. **Never bypass Row Level Security.** Never add `SECURITY DEFINER` unless defined in `docs/PRD-database.md`.
3. **Never hardcode business logic.** Prices, tax rates, commission percentages live in `packages/pricing/`.
4. **Idempotency is mandatory.** Every mutation must be idempotent. Use `idempotency_key` for bookings, payments, webhooks.
5. **No Kubernetes, Kafka, Celery, Django, n8n, or Temporal.** Per PRD v2 canonical decisions.
6. **Agents don't approve themselves.** No agent can approve its own HITL decisions or bypass Paperclip decision-locks.
7. **Odoo is system of record.** All financial data flows through Odoo 18 CE.
8. **No Temporal.** Background execution via PostgreSQL queues + Python workers only.

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

## Component Roles

| Component | Role |
|-----------|------|
| **FastAPI** | Application API layer |
| **Supabase/PostgreSQL** | Operational database |
| **Qoder Wake** | Autonomous backend engineering/execution layer |
| **Paperclip** | Governance authority |
| **Hermes** | Approved tool/API execution |
| **Odoo 18** | ERP / financial system of record |
| **Apidog/OpenAPI** | API contract |

## File Structure

```
New-logistic-/
├── .github/copilot-instructions.md    # You are here
├── docs/soul.md                       # Source of truth — read first
├── docs/memory.md                     # Current state
├── docs/HEARTBEAT.md                  # Agent orchestration state
├── docs/DECISIONS.md                  # Change control log
├── docs/API-RELIABILITY-SECURITY.md   # API contract requirements
├── docs/PRD-frontend.md               # Frontend specs
├── docs/PRD-backend.md                # Backend specs
├── docs/PRD-database.md               # Database specs
├── docs/PRD-agents.md                 # Agent specs
├── apps/portal/                       # Next.js 15 App Router
├── apps/console/                      # Vite 6 + React 19
├── workers/                           # Python 3.11/3.12 agents
├── packages/                          # Shared types, UI, pricing
├── supabase/migrations/               # SQL migrations (00–12c)
├── tests/                             # Unit, integration, contract, security
├── docker-compose.yml                 # Local orchestration
├── .env.example                       # 30+ environment variables
└── README.md                          # Entry point → docs/soul.md
```

## Testing

- **SQL verification**: `docker cp supabase/verify_mN.sql zippy-db:/tmp/vN.sql && docker exec zippy-db psql -U postgres -d postgres -f /tmp/vN.sql`
- **Python tests**: `cd workers && .\.venv\Scripts\python.exe -m pytest tests -q`
- **Node TS tests**: `node --experimental-strip-types apps/portal/scripts/test-webhooks.mts`

## Before Committing

1. Run the relevant verification suite for your milestone
2. Ensure no secrets are committed (check `.env` is in `.gitignore`)
3. Follow existing code patterns in the file you're editing
4. Add `DECISIONS.md` entry if deviating from PRD
5. Check `docs/API-RELIABILITY-SECURITY.md` for API contract requirements

## Qoder Wake Scope

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
