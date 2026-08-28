# Zippy Logistics Control Plane

> Monorepo for the Zippy Logistics multi-agent logistics platform (PRD v2.0).

## Apps & Packages

| Path | Runtime | Role |
|------|---------|------|
| `apps/portal` | Next.js 15 | Customer/shipper web portal |
| `apps/console` | Vite 6 + React 19 | Admin + Driver console (`/admin/*`, `/driver/*`) |
| `apps/workers` | Python 3.12 | Agent workers, heartbeat kernel, Hermes/Paperclip execution |
| `packages/shared-types` | TypeScript | Cross-app schemas generated from Supabase and contracts |
| `packages/ui` | TypeScript/React | Shared UI components and design tokens |
| `packages/ts-config` | JSON | Shared `tsconfig.json` presets |

## Infrastructure

| Path | Role |
|------|------|
| `infra/docker` | Local Docker Compose (Postgres/PostGIS/pgvector, Redis, Odoo 18, nginx, worker skeleton) |
| `infra/supabase` | SQL migrations, Edge Functions, seed data |
| `infra/odoo` | Odoo 18 CE addons and custom configuration |

## Milestones

- **M0** (current): Repository & toolchain skeleton.
- **M1**: Supabase schema + seed + RLS + types.
- **M2**: RPCs, pricing engine, deterministic state machine.
- **M3**: Heartbeat kernel + LoopGuardian + agent execution harness.
- **M4**: Odoo pipeline + webhook router.
- **M5**: Document/POD + notification agents.
- **M6**: End-to-end order flow (portal + console).

See [`docs/PRD/M0.md`](./docs/PRD/M0.md) for the M0 exit criteria.

## Quick Start

```bash
# 1. Install prerequisites
#    Node.js 20+, pnpm 9+, Docker 24+

# 2. Install dependencies
pnpm install

# 3. Copy environment template and fill secrets
cp .env.example .env

# 4. Verify compose file parses
docker compose -f infra/docker/docker-compose.yml config

# 5. Start dev mode
pnpm dev
```

## Scripts

- `pnpm dev` — start all app dev servers in parallel.
- `pnpm build` — production build for all apps/packages.
- `pnpm lint` / `pnpm format` — Biome.
- `pnpm typecheck` — TypeScript.
- `pnpm test` — run all test suites.
- `pnpm m0:verify` — M0 exit-criteria smoke test.

## Dev Notes

- PRD v2 source of truth: `docs/PRD/PRD-Zippy-Logistics-Control-Plane-v2.0.md` (to be added).
- Deterministic business logic must be implemented before agent autonomy (M7+ gates).
- No Kubernetes, Kafka, Celery, Django, FastAPI, or n8n per PRD v2 canonical decisions.

## License

UNLICENSED — internal Zippy Logistics use only.
