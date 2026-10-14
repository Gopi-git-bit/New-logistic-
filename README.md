# Zippy Logistics Control Plane

> Monorepo for the Zippy Logistics multi-agent logistics platform (PRD v2.0).

## Quick Start

```bash
# 1. Read the soul (source of truth)
cat docs/soul.md

# 2. Install prerequisites
#    Node.js 20+, pnpm 9+, Docker 24+

# 3. Install dependencies
pnpm install

# 4. Copy environment template and fill secrets
cp .env.example .env

# 5. Verify compose file parses
docker compose config

# 6. Start dev mode
pnpm dev
```

## Repository Structure

```
New-logistic-/
├── .github/copilot-instructions.md    # Agent guardrails
├── docs/
│   ├── soul.md                        # Source of truth — read first
│   ├── memory.md                      # Current state
│   ├── HEARTBEAT.md                   # Agent orchestration state
│   ├── DECISIONS.md                   # Change control log
│   ├── PRD-frontend.md                # Frontend specs
│   ├── PRD-backend.md                 # Backend specs
│   ├── PRD-database.md                # Database specs
│   └── PRD-agents.md                  # Agent specs
├── apps/
│   ├── portal/                        # Next.js 15 App Router (Customer)
│   └── console/                       # Vite 6 + React 19 (Admin + Driver)
├── workers/                           # Python 3.11/3.12 Agent Workers
├── packages/
│   ├── shared-types/                  # TypeScript database types
│   ├── ui/                            # Shared UI components
│   ├── pricing/                       # Pricing engine
│   └── ts-config/                     # Shared tsconfig.json presets
├── supabase/
│   ├── migrations/                    # SQL migrations (00–12c)
│   └── seed.sql                       # Seed data
├── tests/
│   ├── unit/                          # Unit tests
│   ├── integration/                   # Integration tests
│   ├── contract/                      # Contract tests
│   ├── security/                      # Security tests
│   └── failure/                       # Failure mode tests
├── docker-compose.yml                 # Local orchestration
├── .env.example                       # 30+ environment variables
└── README.md                          # You are here
```

## Apps & Packages

| Path | Runtime | Role |
|------|---------|------|
| `apps/portal` | Next.js 15 | Customer/shipper web portal |
| `apps/console` | Vite 6 + React 19 | Admin + Driver console (`/admin/*`, `/driver/*`) |
| `workers` | Python 3.11/3.12 | Agent workers, heartbeat kernel, Hermes/Paperclip execution |
| `packages/shared-types` | TypeScript | Cross-app schemas generated from Supabase and contracts |
| `packages/ui` | TypeScript/React | Shared UI components and design tokens |
| `packages/pricing` | TypeScript | Pricing engine (rate × distance + tolls + loading + GST) |
| `packages/ts-config` | JSON | Shared `tsconfig.json` presets |

## Infrastructure

| Path | Role |
|------|------|
| `infra/docker` | Dockerfiles, nginx config |
| `infra/supabase` | SQL migrations, Edge Functions, seed data |
| `infra/odoo` | Odoo 18 CE addons and custom configuration |

## Milestones

| # | Status | Description |
|---|--------|-------------|
| M0 | ✅ | Repository & toolchain skeleton |
| M1 | ✅ | Supabase schema + seed + RLS + types (18 tables) |
| M2 | ✅ | RPCs, pricing engine, driver matching, payment rules |
| M3 | ✅ | Heartbeat kernel + LoopGuardian + agent execution harness |
| M4 | ✅ | Odoo pipeline + webhook router + idempotent task queue |
| M5 | ✅ | Document/POD + notification agents |
| M6 | ✅ | E2E order lifecycle (place → assign → deliver → settle) |
| M7 | ⏳ | Hermes (DeepSeek) + Paperclip + Honcho memory |

## Test Suites

```bash
# SQL verification (all pass)
docker cp supabase/verify_mN.sql zippy-db:/tmp/vN.sql
docker exec zippy-db psql -U postgres -d postgres -f /tmp/vN.sql

# Python tests (60/60)
cd workers && .\.venv\Scripts\python.exe -m pytest tests -q

# Node TS webhook tests (8/8)
node --experimental-strip-types apps/portal/scripts/test-webhooks.mts
```

## Scripts

- `pnpm dev` — start all app dev servers in parallel
- `pnpm build` — production build for all apps/packages
- `pnpm lint` / `pnpm format` — Biome
- `pnpm typecheck` — TypeScript
- `pnpm test` — run all test suites

## Dev Notes

- **Source of truth**: [`docs/soul.md`](./docs/soul.md)
- **Current state**: [`docs/memory.md`](./docs/memory.md)
- **Decisions log**: [`docs/DECISIONS.md`](./docs/DECISIONS.md)
- **PRD v2 source**: `docs/PRD/PRD-Zippy-Logistics-Control-Plane-v2.0.md`
- Deterministic business logic must be implemented before agent autonomy (M7+ gates)
- No Kubernetes, Kafka, Celery, Django, or n8n per PRD v2 canonical decisions

## License

UNLICENSED — internal Zippy Logistics use only.
