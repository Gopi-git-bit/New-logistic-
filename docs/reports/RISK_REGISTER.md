# Zippy Production Risk Register

## Document Control

| Field | Value |
|---|---|
| Baseline | M0 production discovery |
| Date | 2026-09-08 |
| Commit | `a6aee5294145eb9c12ffd93a1b63431ca6631bd4` |
| Verdict | **BLOCKED FOR PRODUCTION — SAFE TO PLAN M1** |
| Scope | Verified findings and proposed remediations only |

No remediation in this register is approved for implementation. Configuration, infrastructure, database, service, application, firewall, Apache, and port changes require separate authorization.

## Production PRD Precedence

`docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md` was imported after M0 discovery and is the production execution source of truth pending final owner approval and commit. Conflicting legacy documents are historical until reconciled. Their business rules must not be silently rewritten or discarded. Architecture deviations require a proposed `docs/DECISIONS.md` entry and owner approval. No legacy document is changed by this register.

## Priority Definitions

- **HIGH**: Blocks production provisioning, security assurance, recoverability, or core user operation.
- **MEDIUM**: Must be resolved or explicitly accepted before production, but does not alone prevent documentation/configuration planning.
- **INFORMATIONAL/EXPECTED**: An observed and expected condition that should be documented and monitored, not treated as a defect.

## High Risks

### RISK-H01: Production Compose Definition Missing

| Field | Detail |
|---|---|
| Evidence | `docker-compose.production.yml` is absent at commit `a6aee5294145eb9c12ffd93a1b63431ca6631bd4`. |
| Impact | There is no reviewed production service, network, volume, health-check, restart, or port-binding definition. |
| Proposed remediation | Design and review a production-specific Compose file after the production PRD and network decision are approved. |
| Approval required | Owner approval of production topology and authorization to modify configuration. |
| Verification criteria | `docker compose -f docker-compose.production.yml config` succeeds using a redacted validation environment; reviewed bindings keep public traffic at Apache and databases private. |

### RISK-H02: Deployment Workflow Depends on Missing Compose File

| Field | Detail |
|---|---|
| Evidence | `.github/workflows/deploy-hostinger.yml` runs `docker compose -f docker-compose.production.yml config`, but that file is absent. |
| Impact | A manual production deployment dispatch cannot pass its declared configuration-validation step. |
| Proposed remediation | After H01 is resolved, align the workflow with the approved Compose path and branch policy. |
| Approval required | Owner approval to modify workflow/configuration and production-environment settings. |
| Verification criteria | A pull-request workflow run validates the approved production Compose file without deploying; a separately approved dry run resolves the intended ServerAvatar target. |

### RISK-H03: Migration Source-of-Truth Ambiguous

| Field | Detail |
|---|---|
| Evidence | Numbered SQL migrations are under `infra/supabase/migrations/`; additional migration/seed/verification artifacts are under `supabase/`; `supabase/migrations` is a documentation file; development Compose references `./supabase/migrations`. |
| Impact | Initializing a database before choosing a canonical sequence could apply the wrong files, omit migrations, or create divergent environments. |
| Proposed remediation | Document one canonical migration directory and exact ordered manifest during M1. Do not move or apply files until separately approved. |
| Approval required | Database owner and application owner approval of canonical path and migration ordering. |
| Verification criteria | Approved manifest maps every migration filename, checksum, order, purpose, and target database; a staging initialization plan references only that manifest. |

### RISK-H04: Required PostgreSQL Databases Not Deployed

| Field | Detail |
|---|---|
| Evidence | No Docker containers or volumes exist; no host PostgreSQL service/data directory exists; Zippy Operational, Odoo, and Paperclip databases were not found. |
| Impact | Operational state, accounting truth, governance decisions, queues, and integration persistence cannot run or be verified. |
| Proposed remediation | Define isolated database ownership, credentials, volumes, health checks, and staged initialization/rollback procedures before provisioning. |
| Approval required | Owner approval to provision containers, create databases, generate credentials, and execute migrations. |
| Verification criteria | Separate database identities and persistence are demonstrated in approved staging; no cross-database foreign keys; no public database bindings; migration state and health captured as fresh evidence. |

### RISK-H05: No Application Backup or Restore Evidence

| Field | Detail |
|---|---|
| Evidence | `/var/backups` contained OS package metadata only; `/backup` was absent; no Zippy/Odoo/Paperclip backup schedule, retention record, latest-success record, or restoration evidence was found. |
| Impact | Data loss, failed deployment, or corruption could be unrecoverable or recovery time unknown. |
| Proposed remediation | Define per-system backup scope, encryption, destination, retention, monitoring, restore procedure, and periodic restoration test. |
| Approval required | Owner approval for storage, retention, encryption-key custody, and backup execution. |
| Verification criteria | A separately approved staging restore completes from a backup; checksums, timestamps, retention, and restore acceptance results are recorded without exposing data. |

### RISK-H06: Complete Git Checkout Under Apache Public Root

| Field | Detail |
|---|---|
| Evidence | `/home/<serveravatar-user>/zippy_logitech/public_html` contains a full Git checkout. Apache serves this directory; Basic Auth is configured. |
| Impact | Web-server or override misconfiguration could expose repository metadata or source. The deployment root also mixes source control with public content. |
| Proposed remediation | Design a deployment layout with a non-public source/release directory and a minimal public document root; explicitly deny access to dotfiles and repository metadata. |
| Approval required | Owner and ServerAvatar/Apache administrator approval before changing document roots or virtual-host policy. |
| Verification criteria | Approved security review confirms `.git`, environment files, source files, and internal docs return denial/not-found from all public hostnames; source lives outside the public root. |

### RISK-H07: Production Governance Documents Missing from GitHub Baseline

| Field | Detail |
|---|---|
| Evidence | At the verified baseline commit, `docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md`, `docs/EXECUTION_TRACKER.md`, `docs/TEST_EVIDENCE.md`, and `docs/reports/` were absent. The current files are local documentation changes and have not been committed or pushed. |
| Impact | Production scope, authorization, evidence, sequencing, and risk decisions are not yet reviewable from the shared canonical repository. |
| Proposed remediation | Complete owner review of the M0 documentation and the production PRD imported after discovery, then commit through the normal reviewed process. |
| Approval required | Owner approval of document content and explicit authorization to commit/push. |
| Verification criteria | Approved documents are present on the intended GitHub branch at a recorded commit and cross-reference one canonical source of truth. |

### RISK-H08: UI and Integration Placeholders

| Field | Detail |
|---|---|
| Evidence | Portal and console roots contain name exports but no discovered user screens; UI package is minimal; Honcho is an explicit HTTP-server placeholder; notification providers contain TODOs; Hermes server is absent; Odoo addons/config are incomplete; Langfuse has client configuration only. |
| Impact | Customer, driver, administrator, governance execution, financial integration, notifications, observability, and memory workflows are not production-ready. |
| Proposed remediation | Define acceptance contracts per capability in the production PRD, then implement in approved milestones with current evidence. |
| Approval required | Product owner approval of scope; system-owner approval for Odoo, Paperclip/Hermes, Langfuse, Honcho, and notification providers. |
| Verification criteria | Each capability passes approved UI, API contract, authorization, failure-mode, idempotency, and integration tests in staging; placeholder markers are resolved or explicitly accepted. |

### RISK-H09: Paperclip Source Worktree Is Not a Reproducible Deployment Source

| Field | Detail |
|---|---|
| Status | Unresolved |
| Evidence | Read-only M0 discovery reported `/opt/paperclip` as heavily dirty or containing deleted entries at commit `109d81db4fba684edbdba586ec0a3a3dbea6ae9e`. No further inspection was performed during this correction task. |
| Impact | Resetting, pulling, or deploying from this checkout could destroy unknown work or produce an unreproducible build. |
| Proposed remediation | Perform a separately authorized read-only Git inventory and preserve all changes before selecting a clean, immutable deployment source. |
| Prohibition | Do not reset, clean, checkout, pull, stash, delete, or modify `/opt/paperclip`. |
| Approval required | Paperclip worktree owner and production owner approval are required before preservation or deployment actions. |
| Verification criteria | Commit identity, branch, status, remotes, changed-file ownership, and preservation method are reviewed before deployment. |

## Medium Risks

### RISK-M01: Host Redis Conflicts with Development Compose Binding

| Field | Detail |
|---|---|
| Evidence | Host Redis listens on loopback port 6379; development Compose publishes container port 6379 to host port 6379. |
| Impact | Starting the development Compose service unchanged would encounter a port-binding conflict. |
| Proposed remediation | In production, keep Redis private on the Docker network and publish no host port. Decide separately whether development Compose should use another host port. |
| Approval required | Owner approval before modifying Compose or host Redis. |
| Verification criteria | Production Compose renders with no Redis host binding; application containers reach Redis over the private network; host socket inventory shows no new public Redis listener. |

### RISK-M02: Odoo Config Directory Missing

| Field | Detail |
|---|---|
| Evidence | Development Compose mounts `./infra/odoo/config:/etc/odoo:ro`; `infra/odoo/config` is absent. |
| Impact | Odoo startup behavior is undefined and may fail or use unintended defaults. |
| Proposed remediation | Specify and review the minimum Odoo configuration, ownership, addons path, proxy mode, database filtering, and secrets injection approach. |
| Approval required | Odoo owner approval and authorization to add configuration files. |
| Verification criteria | Compose config resolves the mount; Odoo starts in approved staging with expected config and no secret committed to Git. |

### RISK-M03: Development Nginx API Routing Appears Incorrect

| Field | Detail |
|---|---|
| Evidence | `infra/docker/nginx.conf` defines an API upstream indirectly through services but routes `/api/` to `http://portal`, not the FastAPI service. |
| Impact | Requests intended for FastAPI may reach Next.js; health, API, and webhook routing may differ from documented architecture. |
| Proposed remediation | Confirm intended routing contract and document it before any config change. Production routing should be owned by Apache under the proposed network strategy. |
| Approval required | Application owner approval of path ownership; separate authorization to edit proxy configuration. |
| Verification criteria | Approved route matrix maps hostname/path to service; staging contract tests confirm each route and reject unintended exposure. |

### RISK-M04: Dependency Lockfile Missing

| Field | Detail |
|---|---|
| Evidence | Root `package.json` declares pnpm 9.14.0 and CI uses `pnpm install --frozen-lockfile`, but root `pnpm-lock.yaml` is absent. |
| Impact | Reproducible Node dependency installation and the documented M0 verification command cannot be guaranteed. |
| Proposed remediation | Approve a lockfile policy and generate the lockfile in a controlled dependency-resolution step. |
| Approval required | Owner approval to resolve dependencies and add the generated lockfile. |
| Verification criteria | Clean checkout completes `pnpm install --frozen-lockfile`; lockfile version matches approved pnpm; dependency review/security scan evidence is captured. |

### RISK-M05: MySQL Listens on All Interfaces

| Field | Detail |
|---|---|
| Evidence | `mysqld` listens on `0.0.0.0:3306` and `*:33060`; UFW currently allows only 22, 80, 443, and 43210, so MySQL is blocked externally by current policy. |
| Impact | A future firewall change could unintentionally expose MySQL; the service is not part of the declared Zippy architecture. |
| Proposed remediation | Identify service ownership and necessity, then propose loopback/private binding or removal through the host owner. |
| Approval required | VPS/service owner approval; no MySQL, UFW, or binding change is currently authorized. |
| Verification criteria | Ownership is documented; approved binding/firewall state is confirmed by `ss` and UFW inspection from the host and, where authorized, an external reachability test. |

### RISK-M06: Duplicate Checkout Creates Deployment Drift

| Field | Detail |
|---|---|
| Evidence | Zippy checkouts exist at `/opt/new-logistic` and `/home/<serveravatar-user>/zippy_logitech/public_html`; both were at the same commit during discovery. |
| Impact | Future updates may target different paths, creating unclear deployment ownership and stale public code. |
| Proposed remediation | Select the authoritative source, release, and deployment paths in the production PRD; document promotion mechanics. |
| Approval required | Owner and ServerAvatar administrator approval. |
| Verification criteria | Deployment runbook names one source checkout and one immutable release/public path; runtime process metadata points to the approved release. |

## Informational / Expected Conditions

### INFO-01: Apache Owns Public Ports 80/443

| Field | Detail |
|---|---|
| Evidence | Apache is active and serves the ServerAvatar-managed site on ports 80 and 443. |
| Impact | Expected constraint for production network design; containers must coexist rather than bind public ports. |
| Proposed remediation | Keep Apache public; later proxy approved routes to services bound to `127.0.0.1`. |
| Approval required | Owner approval of the proposed network architecture; Apache changes require separate authorization. |
| Verification criteria | Approved production Compose has no application binding on public 80/443; Apache remains the sole public HTTP/TLS listener. |

### INFO-02: Zippy Containers Are Not Running

| Field | Detail |
|---|---|
| Evidence | Docker listed no running or stopped containers and no named volumes. |
| Impact | Production behavior and data state cannot yet be verified. This is expected because provisioning has not begun. |
| Proposed remediation | Complete and approve M1 documentation/configuration design before any provisioning. |
| Approval required | Explicit owner authorization to start containers or create volumes. |
| Verification criteria | None during documentation-only M1; later provisioning evidence must include container identity, health, mounts, ports, and restart policy. |

### INFO-03: Paperclip Source Is Cloned but Not Deployed

| Field | Detail |
|---|---|
| Evidence | `/opt/paperclip` contains source at commit `109d81db4fba684edbdba586ec0a3a3dbea6ae9e`; no service, container, bound port, database, or proxy route was found. |
| Impact | Governance decisions and grants are unavailable at runtime; no production action should depend on Paperclip yet. |
| Proposed remediation | Define Paperclip version, database isolation, migration, backup, health, approval mode, and proxy requirements before deployment. |
| Approval required | Governance owner approval and separate authorization to deploy. |
| Verification criteria | Later staging evidence demonstrates fail-closed behavior, separate storage, health checks, approval mode, and grant validation without exposing secrets. |

## Proposed Production Network Decision

**Status: PROPOSED, NOT APPROVED**

- Apache remains public on ports 80/443.
- Application containers do not publish ports 80/443.
- Apache later proxies approved routes to services bound to `127.0.0.1`.
- PostgreSQL and Redis remain private.
- Docker Redis does not publish host port 6379 in production.
- PostgreSQL binds only to `127.0.0.1:54322` if host access is required.
- No firewall, Apache, or port changes are authorized by this register.
