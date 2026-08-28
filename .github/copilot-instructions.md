# Zippy Logistics — Copilot Agent Guardrails

> This file instructs AI coding agents (Copilot, Cursor, Claude Code, etc.) on how to behave in this repository.

## Core Rules

1. **Never mutate `orders.status` directly.** Always use the `transition_order()` RPC.
2. **Never bypass Row Level Security.** Never add `SECURITY DEFINER` unless defined in `docs/PRD-database.md`.
3. **Never hardcode business logic.** Prices, tax rates, commission percentages live in `packages/pricing/`.
4. **Idempotency is mandatory.** Every mutation must be idempotent. Use `idempotency_key` for bookings, payments, webhooks.
5. **No Kubernetes, Kafka, Celery, Django, FastAPI, or n8n.** Per PRD v2 canonical decisions.
6. **Agents don't approve themselves.** No agent can approve its own HITL decisions or bypass Paperclip decision-locks.
7. **Odoo is system of record.** All financial data flows through Odoo 18 CE.

## File Structure

```
New-logistic-/
├── .github/copilot-instructions.md    # You are here
├── docs/soul.md                       # Source of truth — read first
├── docs/memory.md                     # Current state
├── docs/HEARTBEAT.md                  # Agent orchestration state
├── docs/DECISIONS.md                  # Change control log
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
