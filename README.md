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

## Automated Releases

`Automated Release` creates GitHub version tags (`vX.Y.Z`) and release notes, **not
deployments**. `master` is the actual default branch and the sole stable release
branch; the reference workflow's `main` is intentionally not used.

- A completed **CI** run must succeed, originate from a **push** to this
  repository's `master`, and test the exact SHA checked out by the release job.
  PR/fork runs cannot release. All existing CI jobs must pass; there are no path
  filters or ignored failures. Stale completions are skipped if `master` has
  advanced, checked immediately before publishing. Releases are serialized with
  a 15-minute timeout; repeated completions use existing tags rather than
  republishing the same commits.
- Root `release.config.cjs` explicitly allows only commit analysis, release-note
  generation, and GitHub publishing. No npm publication, npm token, deployment
  hooks, changelog/source commits, or version-file rewrites are enabled.
  `package.json` remains private and its `2.0.0-m0` version is **not** the release
  version. Versioning derives from reachable release tags and subsequent commits.
- At implementation, `git ls-remote origin 'refs/tags/*'` returned no tags and
  GitHub listed no releases. With no valid prior `vX.Y.Z` release tag on `master`,
  the first release-worthy history produces **1.0.0**, even for a breaking
  change. No release-worthy commits means no release. Future runs increment from
  the last valid reachable release tag; do not seed fake tags or force `2.0.0`
  from the manifest.
- Default workflow permission is `contents: read`; only the release job gets
  `contents: write`. Checkout does not persist credentials. `GITHUB_TOKEN` is
  supplied only to the final freshness-check/publishing step; issue/PR comments,
  failure issues, and labels are disabled, so no issue/PR write scope is needed.
  Repository/organization Actions policies must permit that token permission
  and tag creation. Protected branches/tag rules remain authoritative: a denial
  fails the job, not a PAT or branch-protection bypass. Releases made with this
  token do not trigger other release workflows.

Use Conventional Commits in the message that lands on `master`:

| Message | Release |
|---------|---------|
| `fix(api): handle an empty response` | Patch |
| `feat(portal): add a tracking view` | Minor |
| `feat(api): change response schema` with a body/footer `BREAKING CHANGE: remove the legacy field` | Major |
| `docs: ...`, `chore: ...`, `test: ...` (without a breaking-change footer) | None |

For squash merges, the **squash commit's title/body** must carry this message;
individual PR commit messages are not retained. The highest release type since
the last release wins.

### Safe release validation

Release tooling is isolated in `tools/release`, outside the pnpm workspace. Its
exact pins and npm lockfile do not change frontend dependencies. The chosen
Node **22.23.3** satisfies semantic-release 25.0.9 and GitHub plugin 12.0.10
engines (`^22.14.0 || >=24.10.0`); the reference's Node 20 does not.
The tooling audit currently reports inherited vulnerabilities in the bundled
dependencies of the **disabled** npm publishing plugin, plus an unpatched `braces`
[pattern-recursion advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm);
release patterns are trusted configuration, not PR-supplied patterns. Recheck
the tooling audit when updating pins; do not silence the existing CI scan.

From the repository root with that Node runtime:

```bash
npm ci --prefix tools/release --ignore-scripts --no-audit --no-fund
npm test --prefix tools/release
```

These tests validate the allowlist, lock pins, commit analysis, and generated
notes without credentials, network publishing, tags, or releases. An optional
maintainer-only preview, from a full-history checkout of trusted current
`master`, is:

```bash
# Supply GITHUB_TOKEN securely in the environment; never paste it into a command.
node tools/release/node_modules/semantic-release/bin/semantic-release.js \
  --extends ./release.config.cjs --dry-run --no-ci
```

Dry-run may perform remote authentication/read checks but skips tag creation
and publishing. Never omit `--dry-run` for local validation. There is no manual
production-release trigger. See the upstream [configuration](https://semantic-release.org/usage/configuration/)
and [GitHub plugin options](https://github.com/semantic-release/github#options).

## License

UNLICENSED — internal Zippy Logistics use only.
