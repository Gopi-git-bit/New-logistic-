# M0 Production Discovery Report

## Document Control

| Field | Value |
|---|---|
| Discovery date | 2026-09-08 |
| Documentation timestamp | 2026-09-08T04:59:35Z |
| Repository | `/opt/new-logistic` |
| Branch | `master` |
| Commit | `a6aee5294145eb9c12ffd93a1b63431ca6631bd4` |
| Discovery mode | Read-only |
| Verdict | **BLOCKED FOR PRODUCTION — SAFE TO PLAN M1** |

Secret values, credentials, private keys, database URLs, authorization headers, and sensitive SSH connection details are intentionally excluded.

## Production PRD Precedence

`docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md` was imported after M0 discovery and is the production execution source of truth pending final owner approval and commit. It was not present during discovery. Conflicting legacy documents are historical until reconciled. Their business rules must not be silently rewritten or discarded, and any architecture deviation requires a proposed `docs/DECISIONS.md` entry and owner approval. No legacy document was edited during this correction task.

## Executive Verdict

**BLOCKED FOR PRODUCTION — SAFE TO PLAN M1.**

This is a verified planning baseline, not production-readiness evidence. The repository contains substantial API, worker, schema, governance, and test artifacts, but the production runtime has not yet been provisioned or verified. Required production configuration, current runtime evidence, backups, and several user-facing and integration implementations are absent or incomplete.

Apache listening on ports 80 and 443 is expected. It is the current ServerAvatar-managed public web server and is not itself a defect. No firewall, Apache, port, container, database, or service changes were authorized or performed during discovery.

## Evidence Labels

- **VERIFIED FACT**: Observed directly during read-only discovery.
- **DOCUMENTED CLAIM**: Found in repository documentation but not freshly reproduced.
- **INFERENCE**: A conclusion derived from verified facts and clearly identified as such.
- **MISSING EVIDENCE**: Required proof was unavailable or did not exist.

## Connection and Git Baseline

| Item | Result | Classification |
|---|---|---|
| Hostname | `srv1943844` | VERIFIED FACT |
| Repository root | `/opt/new-logistic` | VERIFIED FACT |
| Branch | `master` | VERIFIED FACT |
| Commit | `a6aee5294145eb9c12ffd93a1b63431ca6631bd4` | VERIFIED FACT |
| Remote | GitHub repository `Gopi-git-bit/New-logistic-` | VERIFIED FACT |
| Working tree at discovery start | Clean | VERIFIED FACT |
| SSH session | Remote SSH connection present; endpoint values redacted | VERIFIED FACT |

## Repository Inventory

### Major Components

| Path | Purpose | Observed depth |
|---|---|---|
| `api/` | FastAPI application API, auth, idempotency, POD lifecycle, Paperclip and Hermes clients | Partial implementation |
| `apps/portal/` | Next.js customer portal and Razorpay webhook handling | Webhook code present; customer UI placeholder |
| `apps/console/` | Vite/React admin and driver console | Placeholder |
| `workers/` | Python task kernel, handlers, capabilities, state machine, tracing, Odoo client | Substantial source; runtime unverified |
| `packages/shared-types/` | Shared TypeScript database and pricing types | Present |
| `packages/ui/` | Shared UI package | Placeholder |
| `packages/ts-config/` | Shared TypeScript configuration | Present |
| `infra/supabase/migrations/` | Numbered PostgreSQL/PostGIS/pgvector migrations | Present; unapplied on this VPS |
| `paperclip/01_governance_schema.sql` | Proposed dedicated governance schema | Present; application state unverified |
| `infra/odoo/` | Odoo integration directories | Addons/data placeholders; config directory absent |
| `docs/` | PRDs, decisions, authority matrix, security and orchestration documents | Present but contains stale and placeholder claims |

### Languages, Frameworks, and Runtime Requirements

- Python 3.11/3.12, FastAPI, Pydantic, httpx, SQLAlchemy, Supabase client, Redis/RQ, Langfuse SDK, structlog, and Typer are declared.
- TypeScript uses Node.js 20+, pnpm 9.14.0, Turbo, Biome, Next.js, Vite, and React.
- PostgreSQL 16 with PostGIS and pgvector is specified for the operational database container.
- Odoo 18 CE and Redis 7 are specified in Compose.
- Root `pnpm-lock.yaml` is absent.

All items above are VERIFIED FACTS from manifests and repository files. Their presence does not establish a working production runtime.

### Docker and Deployment Artifacts

- `docker-compose.yml` defines `db`, `redis`, `odoo`, `honcho-api`, `workers`, `api`, `nginx`, `portal`, and `console` services. VERIFIED FACT.
- Dockerfiles exist for the API, workers, portal, console, and database image. VERIFIED FACT.
- `docker-compose.production.yml` is absent. VERIFIED FACT.
- `.github/workflows/deploy-hostinger.yml` requires `docker-compose.production.yml` during manual deployment validation. VERIFIED FACT.
- `.github/workflows/ci.yml` triggers on pushes and pull requests to `master` and `main`. It declares Compose validation, Python lint/format checks, API tests, Trivy scanning, and a basic secret scan. VERIFIED FACT.
- The deployment workflow is manual (`workflow_dispatch`) and defaults to a non-master branch value unless overridden. VERIFIED FACT.

### Database Artifacts and Migration Ambiguity

- Numbered migration SQL files exist under `infra/supabase/migrations/`. VERIFIED FACT.
- Verification SQL files `verify_m1.sql` through `verify_m6.sql` exist under both `infra/supabase/` and `supabase/`. VERIFIED FACT.
- `supabase/test_full_integration.sql`, `supabase/seed.sql`, and `supabase/00000000000007_operational_completion.sql` exist. VERIFIED FACT.
- `supabase/migrations` is a documentation file, while `infra/supabase/migrations/` is a directory containing SQL migrations. VERIFIED FACT.
- Development Compose references `./supabase/migrations`. VERIFIED FACT.

**Conclusion:** Migration source-of-truth is ambiguous and must be resolved during M1 before any database initialization. The existence of two locations alone does not prove migrations are broken.

### API Surface

The observed FastAPI routes are:

- `GET /api/v1/health`
- `GET /api/v1/ready`
- `POST /api/v1/orders`
- `GET /api/v1/orders/{order_id}`
- `POST /api/v1/orders/{order_id}/pod/verify`

The API includes JWT role checks, idempotency support, lifecycle handling, Paperclip governance calls, and Hermes execution calls. Paperclip failures reject decisions and therefore appear designed to fail closed. The production API was not running and no endpoint was called during discovery. VERIFIED FACT.

### Frontend Depth

- The portal has a Razorpay webhook implementation and tests, but no discovered customer pages or layouts; its root source index is a name export. VERIFIED FACT.
- The console source contains only a name export; no discovered admin or driver screens exist. VERIFIED FACT.
- The shared UI package contains only an application-name export. VERIFIED FACT.

### Worker and Integration Depth

- Workers include a PostgreSQL/Supabase-backed task source, kernel loop, capability controls, loop protection, state transitions, Odoo client, OCR provider, and handlers. VERIFIED FACT.
- Notification providers default to a stub, and Twilio/Resend paths contain TODO markers. VERIFIED FACT.
- Document-download handling contains a production TODO. VERIFIED FACT.
- Paperclip and Hermes have typed API clients, but no corresponding running Zippy integration services were found. VERIFIED FACT.
- Odoo has an XML-RPC client and ownership blueprint, but no custom addons and no runtime container. VERIFIED FACT.
- Langfuse is represented by optional client-side tracing configuration only. VERIFIED FACT.
- Honcho is represented in development Compose by an explicit Python HTTP-server placeholder. VERIFIED FACT.

### Tests Present, Not Executed

- API security and integration test source exists.
- Worker tests for agent core and M4-M6 handlers exist.
- Razorpay webhook tests exist.
- SQL verification files exist for M1-M6.

No application, SQL, container, integration, build, lint, or security test was executed during M0 discovery. Historical counts in `MILESTONES.md`, `docs/memory.md`, and `docs/HEARTBEAT.md` are not current evidence.

### Documentation Presence

Present before this documentation task:

- `docs/soul.md`
- `docs/memory.md`
- `docs/HEARTBEAT.md`
- `docs/DECISIONS.md`
- `docs/AUTHORITY-MATRIX.md`
- `docs/API-RELIABILITY-SECURITY.md`
- `docs/ALGORITHM-TRIAGE.md`
- `docs/DEPLOYMENT-KEY-OWNERSHIP.md`
- Milestone PRDs under `docs/PRD/`

Absent at discovery time:

- `docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md`
- `docs/EXECUTION_TRACKER.md`
- `docs/TEST_EVIDENCE.md`
- `docs/reports/`
- `docker-compose.production.yml`

The nominal canonical PRD file under `docs/PRD/` is itself labeled a placeholder. VERIFIED FACT.

After discovery, `docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md` was imported for owner review. Its later presence does not change the discovery-time absence evidence. VERIFIED FACT.

## VPS and Runtime Inventory

### Operating System and Capacity

| Item | Observed value | Classification |
|---|---|---|
| OS | Ubuntu 24.04.4 LTS (`noble`) | VERIFIED FACT |
| Kernel | Linux 6.8.0-139-generic, x86_64 | VERIFIED FACT |
| CPU | 4 vCPUs, AMD EPYC 9354P | VERIFIED FACT |
| Memory | 15 GiB total; approximately 13 GiB available at discovery | VERIFIED FACT |
| Swap | 1 GiB; unused at discovery | VERIFIED FACT |
| Root filesystem | 193 GiB total; 13 GiB used; 181 GiB available | VERIFIED FACT |
| Docker Engine | 29.8.0 | VERIFIED FACT |
| Docker Compose | 2.40.3 | VERIFIED FACT |

### Services and Ports

| Service/process | State | Binding or role | Classification |
|---|---|---|---|
| Docker | Active | Container engine | VERIFIED FACT |
| Apache | Active | Public ports 80/443; ServerAvatar-managed site | VERIFIED FACT |
| PostgreSQL host service | Inactive/not installed | No host PostgreSQL data directory observed | VERIFIED FACT |
| MySQL 8.0 | Active | Listens on all interfaces at 3306/33060; UFW blocks these ports externally | VERIFIED FACT |
| Redis host service | Active | Loopback port 6379 | VERIFIED FACT |
| Supervisor | Active | Loopback port 9001; no child configs found | VERIFIED FACT |
| ServerAvatar agent | Active | Port 43210; explicitly allowed by UFW | VERIFIED FACT |
| SSH | Active | Port 22 | VERIFIED FACT |

### Containers, Networks, and Volumes

- No running or stopped containers were listed. VERIFIED FACT.
- No named Docker volumes existed. VERIFIED FACT.
- Only default Docker networks (`bridge`, `host`, `none`) existed. VERIFIED FACT.
- Cached images included Nginx Alpine, Odoo 18, Python 3.12 slim, and Redis 7 Alpine. VERIFIED FACT.

**Runtime conclusion:** Production runtime has not yet been provisioned or verified. This is not classified as corruption.

### Apache and TLS

- Apache serves `zippylogitech.com`, `www.zippylogitech.com`, and a ServerAvatar alias from `/home/<serveravatar-user>/zippy_logitech/public_html`. VERIFIED FACT.
- HTTP Basic Authentication is configured for that document root; the credential file exists and its contents were not read. VERIFIED FACT.
- No Zippy application reverse-proxy target was found in the inspected virtual-host files. VERIFIED FACT.
- The Let's Encrypt certificate covers `zippylogitech.com` and `www.zippylogitech.com` and expires on 2026-12-01. VERIFIED FACT.
- `certbot.timer` is present. VERIFIED FACT.

### Firewall and Scheduling

- UFW is active, defaults to deny incoming, and allows ports 22, 80, 443, and 43210 for IPv4 and IPv6. VERIFIED FACT.
- Standard system timers for certificate renewal, package updates, logs, filesystem trim, and system statistics were found. VERIFIED FACT.
- No Zippy, database, or application backup schedule was found. VERIFIED FACT.

### Application Directories and Checkouts

- `/opt/new-logistic` is the working repository. VERIFIED FACT.
- `/opt/paperclip` contains a Paperclip source checkout. VERIFIED FACT.
- A second Zippy checkout exists under Apache `public_html` at `/home/<serveravatar-user>/zippy_logitech/public_html`. VERIFIED FACT.
- The second checkout was at the same Zippy commit during discovery and did not contain a `.env` file. VERIFIED FACT.
- `/opt/new-logistic` was not connected to a running application. VERIFIED FACT.

## Implementation Completion Matrix

| Capability | Classification | Fresh evidence |
|---|---|---|
| Repository and Git baseline | Complete | Clean expected commit verified |
| Production deployment definition | Absent | `docker-compose.production.yml` missing |
| Development Compose definition | Partial | Service definitions exist; production suitability unverified |
| Operational database schema source | Partial | SQL exists; canonical path unresolved; no deployed DB |
| Operational DB runtime | Absent | No host service/container/volume |
| Odoo DB/runtime | Absent | No Odoo container or database |
| Paperclip DB/runtime | Absent | Source checkout only |
| FastAPI | Partial | Five routes and service clients found; not running |
| Customer portal | Placeholder | Webhook support but no customer UI found |
| Admin/driver console | Placeholder | Source index only |
| Worker engine | Partial | Substantial source exists; not running or freshly tested |
| Hermes | Placeholder | Client contract only; executor service absent |
| Odoo integration | Partial/placeholder | Client exists; addons/config/runtime absent |
| Langfuse | Placeholder | Optional instrumentation configuration only |
| Honcho | Placeholder | Explicit development HTTP-server placeholder |
| Application backups | Absent | No backup schedule, artifacts, retention, or restore evidence |
| Current test evidence | Absent | Tests were not executed during discovery |

## Paperclip Topology and Health

| Item | Finding | Classification |
|---|---|---|
| Source path | `/opt/paperclip` | VERIFIED FACT |
| Upstream | `paperclipai/paperclip` | VERIFIED FACT |
| Commit | `109d81db4fba684edbdba586ec0a3a3dbea6ae9e` | VERIFIED FACT |
| Source worktree | Heavily dirty/deleted entries reported | VERIFIED FACT |
| Process/container/systemd | None found | VERIFIED FACT |
| Bound port/health | None; not running | VERIFIED FACT |
| Apache route | None found | VERIFIED FACT |
| Database | None found | VERIFIED FACT |
| Persistent volume | None found | VERIFIED FACT |
| Backup coverage | None found | VERIFIED FACT |
| Migration state | No applied-state evidence | MISSING EVIDENCE |
| Recent errors | No runtime logs because no runtime was found | MISSING EVIDENCE |
| Zippy governance schema | SQL file exists in Zippy repository; no application proof | VERIFIED FACT |
| Agent capabilities/budgets | Repository definitions exist; runtime state unavailable | VERIFIED FACT / MISSING EVIDENCE |

## Hermes, Odoo, Langfuse, and Honcho

| System | Repository state | Runtime state | Conclusion |
|---|---|---|---|
| Hermes | Typed allowlisted execution client | No service/container found | Placeholder/incomplete |
| Odoo | Compose entry, XML-RPC client, ownership blueprint | No service/container/database found | Partial source; not deployed |
| Langfuse | Optional worker tracing and environment names | No service/container/proxy/database found | Placeholder configuration |
| Honcho | Environment names and explicit placeholder Compose service | No service/container/proxy/database found | Placeholder configuration |

## Database Ownership and Isolation Map

| Ownership boundary | Intended authority | Discovered runtime | Isolation assessment |
|---|---|---|---|
| Zippy Operational DB | Operational orders, trips, queues, external references | Not deployed | Cannot verify runtime isolation |
| Odoo DB | Accounting and financial truth | Not deployed | Cannot verify runtime isolation |
| Paperclip DB | Governance decisions and execution grants | Not deployed | Cannot verify runtime isolation |
| Langfuse storage | Observability only | Not deployed | Cannot verify runtime isolation |
| Honcho storage | Contextual memory only | Not deployed | Cannot verify runtime isolation |

Source review found documented boundaries prohibiting cross-database foreign keys and raw SQL writes to Odoo core tables. No live databases existed to verify those properties. No public PostgreSQL or Redis ports were observed. MySQL is unrelated to the declared Zippy architecture based on available evidence.

## Intended Production Network Strategy (Proposed Decision)

This is a proposal for owner review, not an approved or implemented configuration:

1. Apache remains public on ports 80 and 443.
2. Application containers do not publish ports 80 or 443.
3. Apache later proxies approved routes to services bound to `127.0.0.1`.
4. PostgreSQL and Redis remain private.
5. Docker Redis does not publish host port 6379 in production.
6. PostgreSQL binds only to `127.0.0.1:54322` if host access is required.
7. No firewall, Apache, or port changes are authorized during M0 or documentation-only M1 planning.

## Security Findings

1. A complete Git checkout is located beneath Apache `public_html`. HTTP Basic Authentication currently protects the configured directory, but source publication and Apache override behavior require a deliberate security review. VERIFIED FACT.
2. `/opt/new-logistic/.env` exists with mode `0600` and root ownership. Values were not read or reported. VERIFIED FACT.
3. `.gitignore` protects common `.env` variants, private keys, Docker data, Odoo data, caches, logs, and build outputs. It does not explicitly enumerate generic database dumps or backup archives. VERIFIED FACT.
4. MySQL listens on all interfaces, although UFW currently blocks external access to its ports. VERIFIED FACT.
5. Host Redis listens only on loopback. VERIFIED FACT.
6. No application backup, retention, or restoration evidence was found. VERIFIED FACT.

## Documented Claims Versus Fresh Evidence

| Claim | Source | Fresh evidence | Assessment |
|---|---|---|---|
| M0-M6 complete | `MILESTONES.md`, `docs/memory.md` | Source artifacts exist, but frontends and integrations are placeholders | Historical/documented claim only |
| `zippy-db` is running with 25 tables | `docs/HEARTBEAT.md` | No Docker containers or volumes exist | Stale documented claim |
| All M1-M6 SQL suites pass | `docs/memory.md`, `docs/HEARTBEAT.md` | No SQL tests executed and no database exists | Historical claim, not reproduced |
| Worker tests pass | `MILESTONES.md`, `docs/memory.md` | Test files exist; no tests executed | Historical claim, not reproduced |
| Canonical production PRD existed during discovery | Documentation references | It was absent during discovery and imported afterward for review | Unsupported as a discovery-time claim |

No table-count target is accepted as current evidence. A fresh count must be established only after an approved staging initialization.

## Architecture and Documentation Conflicts

1. The deploy workflow requires an absent production Compose file.
2. The canonical production execution PRD is absent, while an older nominal PRD file is explicitly a placeholder.
3. `docs/HEARTBEAT.md` reports a running database that is absent from the current VPS runtime.
4. Migration source-of-truth is ambiguous between `supabase/` and `infra/supabase/` paths.
5. Development Nginx routes `/api/` to the portal upstream rather than the FastAPI upstream; intent requires confirmation.
6. Development Compose references an Odoo config directory that does not exist.
7. Repository milestone completion language exceeds currently reproducible runtime and UI evidence.
8. `/opt/paperclip` had a heavily dirty worktree or deleted entries; its ownership and preservation requirements are unresolved, so it is not a reproducible deployment source.

## Commands Executed and Results

All discovery commands were non-mutating. Compound inspection commands sometimes used `|| true` to continue after expected absence checks; the result below records the effective shell exit result and material observation.

| Command or command group | Exit | Result summary |
|---|---:|---|
| `pwd`, `hostname`, SSH presence, Git root/remote/branch/HEAD/status | 0 | Expected host, repository, branch, commit, and clean tree verified |
| `lsb_release`, `uname`, `lscpu`, `free`, `df` | 0 | OS, kernel, CPU, memory, and disk inventory captured |
| `docker --version`, `docker compose version` | 0 | Engine and Compose versions captured |
| `systemctl status/is-active` for Docker, Apache, PostgreSQL, Nginx, Caddy | 0 | Docker/Apache active; PostgreSQL/Nginx/Caddy inactive |
| `docker ps -a --no-trunc` | 0 | No containers listed |
| `docker images`, `docker volume ls`, `docker network ls` | 0 | Cached images; no named volumes; default networks only |
| `ss -tulpn` | 0 | Listening sockets and owners inventoried |
| Apache site listing and virtual-host reads | 0 | ServerAvatar document root, Basic Auth, PHP handler, TLS config observed |
| `certbot certificates` | 0 | Certificate names and expiry metadata recorded; key contents not accessed |
| `ufw status verbose` | 0 | Active policy and allowed ports recorded |
| systemd timer and cron metadata listing | 0 | Standard timers/jobs found; no Zippy backup schedule found |
| process, systemd-unit, and supervisor inspection | 0 | No Zippy/Paperclip runtime services found |
| `/opt`, `/home`, and application-directory metadata listing | 0 | Paperclip and duplicate Zippy checkouts identified |
| Paperclip Git remote/HEAD/status inspection | 0 | Upstream, commit, and dirty source state observed |
| database package/data-directory inspection | 0 | Host MySQL present; PostgreSQL absent |
| unauthenticated local `mysql -e "SHOW DATABASES;"` | 1 | Access denied; no credentials requested or exposed |
| backup-directory metadata listing | 0 | OS package metadata only; no application backup evidence |
| `.env` variable-name extraction only | 0 | Variable names inventoried; values not printed |
| repository, docs, Compose, workflow, manifest, and source reads | 0 | Inventory and implementation depth established |
| `rg` source-marker search attempt | 127 | `rg` unavailable; no installation attempted |
| read-only `grep` fallback for TODO/placeholder markers | 0 | Placeholder paths identified |

## Mutation Statement

The M0 discovery performed no repository or server mutation. It did not edit files, change permissions, install packages, start or stop services, create containers, execute migrations, run tests, call live external APIs, change firewall/Apache configuration, or expose secret values.
