# Zippy Production Execution Tracker

## Control Rules

- Current verdict: **BLOCKED FOR PRODUCTION — M4 OPERATIONS-FINANCE COMPLETE IN DISPOSABLE TEST ENVIRONMENTS; M5 ACTIVE BUT NOT BEGUN**.
- Only one tracker row may be active at a time.
- M1 is complete and owner-approved for the bounded M2 implementation recorded below.
- Every milestone still requires its own dependency-correct scope and approval; no tracker transition authorizes production work.
- A status in this tracker is not permission to modify systems. The `Authorized scope` column is controlling.



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
| M1-LOCK-STRATEGY | M1 | Define dependency-lock strategy | COMPLETE | M1-PRD | Documentation only | Dependency/runtime declaration inventory, locking policy, source/manifest reconciliation, and reproducibility risks | Engineering owner approval required before implementation | Revert documentation edits | No package installation, update, removal, or lockfile generation occurred |
| M1-DB-REQUIREMENTS | M1 | Define M2 database initialization and rollback requirements | COMPLETE | M1-MIGRATIONS, M1-STAGING-ROUTE | Requirements documentation only | 30-domain MVP database requirements, ownership, security, reliability, deferrals, and migration gate checklist | Database owner approval required before implementation | Revert documentation edits | No database was created, accessed, migrated, seeded, or modified |
| M1-BACKUPS | M1 | Define backup, retention, monitoring, and restoration requirements | COMPLETE | M1-PRD, M1-STAGING-ROUTE | Policy documentation only | RPO/RTO, schedule, retention, and future restore criteria | Owner and data custodian approval recorded 2026-09-09 | Revise policy | Minimal-Cost MVP policy and initial custodian approved; no backup/restore execution occurred |
| M1-EVIDENCE | M1 | Define fresh CI, security, contract, database, and restore evidence | COMPLETE | M1-PRD, M1-MIGRATIONS, M1-LOCK-STRATEGY, M1-BACKUPS | Evidence-matrix documentation only | Required commands, environments, result fields, gate owners | Evidence package ready for owner review 2026-09-09 | Revise matrix | Review distinguishes documentation/static/host evidence from unverified runtime, restore, and production evidence |
| M1-OWNER-GATE | M1 | Review all M1 artifacts and authorize or reject implementation | COMPLETE | All prior M1 tasks | Review and decision recording only | Explicit per-artifact decisions and exact implementation scope | Owner approval recorded 2026-09-09 | Keep M2 blocked and revise M1 artifacts | Approved controlled backend database progression only; production and unrestricted integration remain excluded |
| M2-DATABASES | M2 | Databases and tenancy | COMPLETE | M1-OWNER-GATE | Security-focused correction and proof in a network-isolated disposable PostgreSQL environment only | Restricted-login RLS/privilege proof, safe schema rollback, separately guarded role teardown, immutable image identity, fresh apply/reapply, behavior/concurrency and cleanup evidence | Database implementation authorized under approved M1 owner gate; corrected evidence recorded for owner review | Schema down removes database-local objects only; separate confirmed disposable-only role teardown; production recovery remains forward-fix | Corrected current-workspace proof exited zero; no production database or deployment was accessed |
| M3-CORE | M3 | Deterministic operational core | COMPLETE | M2-DATABASES | Deterministic operational core in network-isolated disposable environments only | Order intake, `202 + workflow_id`, pricing, transitions, idempotency, outbox, retry, recovery, lock and cleanup evidence | Authorized execution completed; production approval remains required | Application rollback plus disposable migration down and separate guarded role teardown | Test/dev auth and pricing only; agents remain outside pricing/state authority; no deployment or external integration |
| M4-OPERATIONS-FINANCE | M4 | Payments, dispatch, POD and Odoo staging | COMPLETE | M3-CORE | Sandbox/synthetic Razorpay, authenticated webhook ingress, deterministic dispatch, POD settlement gate, draft-only Odoo fake-transport adapter, and ORD-INV-003 trusted body-type compatibility in network-isolated disposable environments only | Owner-authorized acceptance audit passed every gate: Razorpay webhook security, evidence-only refund reconciliation, manual settlement, dispatch body-type compliance, POD gate, draft-only Odoo, secret redaction, RLS/privilege posture, M4 proof (116 passed) and M2 regression (all markers PASS), cleanup verified | D-26 product/finance/Odoo owner approval (Gopinathan, 2026-09-11) plus final owner-authorized acceptance audit recorded 2026-09-24 | Disposable migration down and separate guarded role teardown; production recovery remains forward-fix | Live payments, live Odoo, production deployment, autonomous finance, and accounting-authority changes remain prohibited and unverified |
| M5-PAPERCLIP | M5 | Paperclip governance | IN_PROGRESS | M4-OPERATIONS-FINANCE, preserved immutable Paperclip source | Owner-approved M5 implementation active; M5-A governance database foundation complete; M5-B authenticated service contract and narrow executor integration not begun. | Isolated schema, decision lock/HITL, grant, fail-closed, loop, budget, audit, concurrency, rollback, and reapply evidence | D-27/D-28 owner approvals recorded 2026-09-25; M5-A disposable proof passed and recorded | Approved isolated service/database rollback | `/opt/paperclip` must not be modified or deployed; sole active task |
| M6-LANGFUSE | M6 | Langfuse observability | BLOCKED | M5-PAPERCLIP | None currently authorized | Isolated storage, trace correlation, audit separation, cost reconciliation, and non-fatal failure evidence | Observability and owner approval required | Disable instrumentation without affecting transactions | Observability only |
| M7-AGENTS | M7 | Agent activation | BLOCKED | M6-LANGFUSE, open provider decisions | None currently authorized | Model/provider validation, capability/allowlist, shadow, HITL, and narrow-automation evidence | Product, governance, and owner approval required | Pause agents and revoke capabilities | Honcho remains contextual only |
| M8-STAGING-E2E | M8 | Staging E2E and resilience | BLOCKED | M7-AGENTS | None currently authorized | Clean-environment unit/integration/contract/E2E/security/failure and backup-restore evidence | Engineering, security, operations approval required | Restore/tear down staging per runbook | Includes outage, retry, duplicate, lock, and rollback drills |
| M9-READINESS | M9 | Production readiness review | BLOCKED | M8-STAGING-E2E | None currently authorized | No unresolved critical/high security findings; secrets, monitoring, backups, restores, runbook, rollback, external-system evidence | Owner, security, finance, and operations approval required | Remain in staging | Explicit human go-live decision required |
| M10-ROLLOUT | M10 | Controlled production rollout | BLOCKED | M9-READINESS | None currently authorized | Shadow, internal pilot, canary, monitored expansion, thresholds, smoke, and rollback evidence | Explicit per-stage human approval required | Execute approved stage rollback | Live payments, DNS, financial autonomy, and irreversible actions need explicit approval |

## Current Authorized Work

`M4-OPERATIONS-FINANCE` is complete for its authorized sandbox/synthetic disposable-environment scope, including deterministic dispatch with ORD-INV-003 trusted body-type compatibility (`zippy.dispatch_requirements`), Razorpay webhook ingress, evidence-only refund reconciliation, manual settlement, POD settlement gate, draft-only Odoo fake-transport adapter, and secret redaction. Evidence covers the owner-authorized acceptance audit (2026-09-24): final M4 proof (116 passed), M2 regression (all markers PASS), RLS/privilege posture, manifest checksums, and verified cleanup. `M5-PAPERCLIP` is the sole active task. M5-A (isolated governance database foundation) is complete with a passing disposable proof and evidence recorded as `M5-E008`; M5-B (authenticated service contract and narrow executor integration) is not begun and remains blocked until separately authorized. `/opt/paperclip` must not be modified or deployed until preserved and reviewed. No production database mutation, live payment, deployment, Odoo/Paperclip/n8n integration, agent activation, or infrastructure change occurred.
