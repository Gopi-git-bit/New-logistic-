# Zippy Production Execution Tracker

## Control Rules

- Current verdict: **BLOCKED FOR PRODUCTION — SAFE TO PLAN M1**.
- Only one tracker row may be active at a time.
- M1 is documentation/configuration planning only until separately approved.
- All M2 and later tasks remain `BLOCKED` until M1 exit criteria and explicit owner approval are recorded.
- A status in this tracker is not permission to modify systems. The `Authorized scope` column is controlling.

`docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md` was imported after M0 discovery and is the owner-approved production execution source of truth established at commit `cee3307861fc4d19c5a85c7bbce3ca1367c9a6a2`. Conflicting legacy documents are historical until reconciled. Their business rules must not be silently rewritten or discarded. Architecture deviations require a proposed `docs/DECISIONS.md` entry and owner approval. Legacy documents are not edited by this tracker update.

## Status Values

- `COMPLETE`: Evidence exists for the authorized scope.
- Active: currently authorized work; exactly one tracker row uses the active status token.
- `PENDING`: Sequenced but not started; remains within planning scope.
- `BLOCKED`: Cannot begin until dependencies and human approvals are satisfied.

## Canonical Milestone Structure

| Milestone | Canonical name |
|---|---|
| M0 | Discovery and baseline |
| M1 | Repository, contracts and CI baseline |
| M2 | Databases and tenancy |
| M3 | Deterministic operational core |
| M4 | Payments, dispatch, POD and Odoo staging |
| M5 | Paperclip governance |
| M6 | Langfuse observability |
| M7 | Agent activation |
| M8 | Staging E2E and resilience |
| M9 | Production readiness review |
| M10 | Controlled production rollout |

## Tracker

| Task ID | Milestone | Task | Status | Dependencies | Authorized scope | Evidence required | Human approval | Rollback | Notes |
|---|---|---|---|---|---|---|---|---|---|
| M0-DISCOVERY | M0 | Read-only repository and VPS production discovery | COMPLETE | Verified Git baseline | Read-only inspection only | Discovery commands, commit, environment inventory, findings | Discovery authorization received | None; no mutation occurred | Secret values and sensitive SSH details redacted |
| M0-DOCS | M0 | Document discovery report, risk register, M0-to-M1 plan, tracker, evidence ledger, and imported PRD provenance | COMPLETE | M0-DISCOVERY | Six authorized Markdown files only | `git diff --check`, `git status --short`, `git diff --stat`; owner review | Current documentation-only authorization | Remove uncommitted documentation files or revert later reviewed documentation commit | No commit or push authorized |
| M1-PRD | M1 | Review and establish the imported `docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md` | COMPLETE | M0-DOCS | Documentation review only | Approved source/version and owner sign-off | Required before final canonical designation | Revert/remove unapproved draft documentation | Owner-approved at commit `cee3307861fc4d19c5a85c7bbce3ca1367c9a6a2` |
| M1-RECONCILE | M1 | Reconcile `soul.md`, `memory.md`, `MILESTONES.md`, milestone PRDs, and placeholder claims | COMPLETE | M1-PRD | Documentation analysis and approved edits only | Conflict matrix and reviewed wording | Required before changing legacy claims | Revert documentation edits | Matrix records historical claims without changing legacy sources |
| M1-DECISIONS | M1 | Draft and record approved architecture decisions | COMPLETE | M1-PRD, M1-RECONCILE | Documentation only | D-11 through D-24 owner-approved records and technical directions | Owner approval recorded 2026-09-08 | Revert documentation edits | No implementation, infrastructure, database, or runtime activation authorized |
| M1-MIGRATIONS | M1 | Select canonical migration directory without moving files | COMPLETE | M1-PRD, M1-DECISIONS | Inventory and manifest documentation only | Expanded static inventory: 37 executable/state-mutating artifacts, 12 references, checksums, ownership classification, conflict analysis, and logical MVP manifest | Owner-authorized completeness correction completed; database execution remains blocked | Revert documentation edits | No migration was run, moved, or created; existing scripts remain non-executable legacy sources |
| M1-STAGING-ROUTE | M1 | Design a staging-only deployment route and future production network constraints | COMPLETE | M1-PRD, M1-DECISIONS, M1-MIGRATIONS | Design documentation only | Verified topology, route matrix, staging isolation, approval gates, health, rollback, and evidence review | Infrastructure owner approval required before implementation | Revert documentation edits | No Compose implementation, provisioning, proxy change, service action, or database access occurred |
| M1-LOCK-STRATEGY | M1 | Define dependency-lock strategy | IN_PROGRESS | M1-PRD | Documentation only | Package-manager and lock policy review | Engineering owner approval | Revise policy | No package installation or lockfile generation; work has not begun |
| M1-DB-REQUIREMENTS | M1 | Define M2 database initialization and rollback requirements | PENDING | M1-MIGRATIONS, M1-STAGING-ROUTE | Requirements documentation only | Environment gates, ordering, rollback, and future verification plan | Database owner approval | Revise requirements | Database creation and migration execution belong to M2 |
| M1-BACKUPS | M1 | Define backup, retention, monitoring, and restoration requirements | PENDING | M1-PRD, M1-STAGING-ROUTE | Policy documentation only | RPO/RTO, schedule, retention, and future restore criteria | Owner and data custodian approval | Revise policy | Backup/restore execution belongs to later milestones |
| M1-EVIDENCE | M1 | Define fresh CI, security, contract, database, and restore evidence | PENDING | M1-PRD, M1-MIGRATIONS, M1-LOCK-STRATEGY, M1-BACKUPS | Evidence-matrix documentation only | Required commands, environments, result fields, gate owners | Engineering/security owner approval | Revise matrix | No tests executed under planning authorization |
| M1-OWNER-GATE | M1 | Review all M1 artifacts and authorize or reject implementation | PENDING | All prior M1 tasks | Review and decision recording only | Explicit per-artifact decisions and exact implementation scope | Owner approval required | Keep M2 blocked and revise M1 artifacts | Approval must name files/services/environments/commands |
| M2-DATABASES | M2 | Databases and tenancy | BLOCKED | M1-OWNER-GATE | None currently authorized | Fresh isolated DB, migration, tenancy/RLS, rollback, no-cross-FK, and no-Odoo-core-SQL evidence | Database and owner approval required | Approved disposable staging or restoration procedure | No assumed table count |
| M3-CORE | M3 | Deterministic operational core | BLOCKED | M2-DATABASES | None currently authorized | Order intake, `202 + workflow_id`, pricing, transitions, idempotency, outbox, retry, and recovery evidence | Application owner approval required | Approved application/data rollback | Agents remain outside pricing/state authority |
| M4-OPERATIONS-FINANCE | M4 | Payments, dispatch, POD and Odoo staging | BLOCKED | M3-CORE | None currently authorized | Sandbox payment, duplicate prevention, compliance, POD, Odoo draft/posting, and reconciliation evidence | Product, finance, and Odoo owner approval required | Sandbox reset and staged rollback | No live credentials or ledger mirroring |
| M5-PAPERCLIP | M5 | Paperclip governance | BLOCKED | M4-OPERATIONS-FINANCE, preserved immutable Paperclip source | None currently authorized | Isolated schema, decision lock/HITL, grant, fail-closed, loop, budget, and audit evidence | Governance and owner approval required | Approved isolated service/database rollback | `/opt/paperclip` must not be modified or deployed until preserved/reviewed |
| M6-LANGFUSE | M6 | Langfuse observability | BLOCKED | M5-PAPERCLIP | None currently authorized | Isolated storage, trace correlation, audit separation, cost reconciliation, and non-fatal failure evidence | Observability and owner approval required | Disable instrumentation without affecting transactions | Observability only |
| M7-AGENTS | M7 | Agent activation | BLOCKED | M6-LANGFUSE, open provider decisions | None currently authorized | Model/provider validation, capability/allowlist, shadow, HITL, and narrow-automation evidence | Product, governance, and owner approval required | Pause agents and revoke capabilities | Honcho remains contextual only |
| M8-STAGING-E2E | M8 | Staging E2E and resilience | BLOCKED | M7-AGENTS | None currently authorized | Clean-environment unit/integration/contract/E2E/security/failure and backup-restore evidence | Engineering, security, operations approval required | Restore/tear down staging per runbook | Includes outage, retry, duplicate, lock, and rollback drills |
| M9-READINESS | M9 | Production readiness review | BLOCKED | M8-STAGING-E2E | None currently authorized | No unresolved critical/high security findings; secrets, monitoring, backups, restores, runbook, rollback, external-system evidence | Owner, security, finance, and operations approval required | Remain in staging | Explicit human go-live decision required |
| M10-ROLLOUT | M10 | Controlled production rollout | BLOCKED | M9-READINESS | None currently authorized | Shadow, internal pilot, canary, monitored expansion, thresholds, smoke, and rollback evidence | Explicit per-stage human approval required | Execute approved stage rollback | Live payments, DNS, financial autonomy, and irreversible actions need explicit approval |

## Current Authorized Work

`M1-LOCK-STRATEGY` is the sole active task. `M1-STAGING-ROUTE` produced `docs/reports/M1_STAGING_ROUTE_PLAN.md` through read-only discovery and an approval-gated route design. Dependency-lock work has not begun and does not authorize package installation, lockfile generation, Compose implementation, provisioning, proxy changes, database execution, or production changes.
