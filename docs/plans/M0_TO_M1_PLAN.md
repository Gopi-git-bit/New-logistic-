# M0 to M1 Production Planning Plan

## Status and Constraint

**Verdict:** BLOCKED FOR PRODUCTION — SAFE TO PLAN M1.

M1 remains documentation and configuration-design work only until separately approved. This plan does not authorize edits to application code, Compose files, workflows, migrations, infrastructure, services, databases, environment files, Apache, firewall rules, ports, permissions, or running processes. It does not authorize container startup, dependency installation, tests, migrations, commits, or pushes.

`docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md` was imported after M0 discovery and is the production execution source of truth pending final owner approval and commit. Conflicting legacy documents are historical until reconciled. Their business rules must not be silently rewritten or discarded. Architecture deviations require a proposed `docs/DECISIONS.md` entry and owner approval. This task does not edit legacy documents.

## Planning Principles

1. Fresh runtime evidence outranks milestone labels and historical test counts.
2. Production configuration is designed and reviewed before it is implemented.
3. PostgreSQL tasks/outbox/workers provide durable execution; Temporal remains excluded.
4. Zippy owns operational state; Odoo owns accounting and financial truth.
5. Paperclip owns governance decisions and grants; Hermes executes allowlisted actions after a valid grant.
6. Langfuse is observability only; Honcho is contextual memory only.
7. Governance failure must fail closed.
8. Databases remain isolated, with no cross-database foreign keys and no raw SQL writes to Odoo core tables.
9. Every implementation step must be small, reversible, evidence-producing, and separately authorized.

## Ordered M1 Tasks

### M1-01: Establish the Production Source of Truth

**Action:** Review the imported `docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md` and establish it as the canonical production execution PRD pending final owner approval and commit.

**Documentation/configuration-only output:**

- Scope, environments, owners, service boundaries, network topology, data ownership, release flow, security gates, evidence requirements, rollback standards, and human approvals.
- Explicit status for each requirement: approved, proposed, unresolved, or out of scope.

**Acceptance criteria:**

- Owner identifies the source document and version.
- The document states that it supersedes conflicting production claims.
- No placeholder language remains in the canonical source.
- No application or infrastructure implementation occurs.

**Rollback:** Remove the unapproved draft before commit, or revert the documentation commit after approval through normal Git review.

### M1-02: Reconcile Legacy Documentation

**Action:** Compare the approved production PRD against `docs/soul.md`, `docs/memory.md`, `MILESTONES.md`, milestone PRDs, and the placeholder PRD.

**Documentation/configuration-only output:**

- Conflict matrix identifying stale, historical, compatible, and superseded claims.
- Proposed wording changes; no legacy file edits until specifically authorized.

**Acceptance criteria:**

- Historical test counts are labeled historical and not current evidence.
- Claims about running containers, databases, applied migrations, and table counts require fresh evidence.
- Ownership and prohibited-technology boundaries remain explicit.

**Rollback:** Delete the draft reconciliation artifact before commit, or revert its documentation commit.

### M1-03: Record Proposed Architecture Decisions

**Action:** Draft entries for `docs/DECISIONS.md`, marked **PROPOSED**, covering production networking, database isolation, migration ownership, deployment roots, dependency locking, backup policy, and evidence retention.

**Required proposed network decision:**

- Apache remains public on ports 80/443.
- Application containers do not publish ports 80/443.
- Apache later proxies approved routes to services bound to `127.0.0.1`.
- PostgreSQL and Redis remain private.
- Docker Redis does not publish host port 6379 in production.
- PostgreSQL may bind only to `127.0.0.1:54322` if host access is required.
- No firewall, Apache, or port changes occur without separate approval.

**Acceptance criteria:**

- Every entry has status `PROPOSED`, owner, rationale, alternatives, security impact, rollback, and approval gate.
- No proposed decision is represented as approved or implemented.

**Rollback:** Remove or revise unapproved proposals.

### M1-04: Select a Canonical Migration Directory

**Action:** Create an inventory and proposed ordered manifest for all schema, migration, seed, and verification files. Select one canonical directory without moving files.

**Questions to resolve:**

- Whether `infra/supabase/migrations/` is canonical.
- The role of `supabase/00000000000007_operational_completion.sql`.
- Whether seeds are development-only.
- Which verification scripts target each milestone and database.
- How checksums and applied migration state will be recorded.

**Acceptance criteria:**

- One proposed source-of-truth path and ordered manifest are documented.
- Duplicate/conflicting files are mapped, not silently discarded.
- Zippy, Odoo, Paperclip, and Langfuse targets are explicitly separated.
- No migration file is moved, modified, or executed.

**Rollback:** Revise the proposed manifest before implementation approval.

### M1-05: Design a Staging-Only Deployment Route

**Action:** Document a staging-only deployment route and future production constraints, but do not create or run Compose configuration.

**Design requirements:**

- Define an isolated staging route that does not alter Apache, DNS, firewall, TLS, or production traffic.
- Record the proposed future constraint that Apache remains the public TLS endpoint on ports 80/443.
- Record that future application services bind only to `127.0.0.1` where host proxy access is required.
- Record that Redis and PostgreSQL remain private and use separate credentials and persistence per authoritative system.
- Define staging health, rollback, secret-injection, and evidence requirements without provisioning services.
- Do not represent Honcho, Langfuse, Paperclip, Odoo, or other placeholders as operational.

**Acceptance criteria:**

- Architecture review confirms the staging-only boundary and future port/network constraints.
- A proposed route matrix identifies staging host/path ownership without changing live proxy configuration.
- No Compose file is created or executed before separate authorization.

**Rollback:** Revise or discard the design document.

### M1-06: Define Dependency-Lock Strategy

**Action:** Document package-manager versions, lockfile ownership, update cadence, vulnerability review, and reproducible-install rules.

**Acceptance criteria:**

- pnpm 9.14.0 compatibility is confirmed or deliberately changed through a proposed decision.
- Root workspace lockfile policy is explicit.
- Python direct and transitive dependency strategy is documented.
- CI must reject unintended lockfile drift.
- No package resolution or installation occurs during documentation-only M1.

**Rollback:** Revise the policy before generating lockfiles.

### M1-07: Define M2 Database Initialization and Rollback Requirements

**Action:** Define the requirements and evidence contract for the M2 staging database runbook without creating a database or executing a migration.

**Required contents:**

- Preflight checks and environment identity.
- Empty-volume/database requirement.
- Canonical migration manifest and checksum capture.
- Secret handling and redaction.
- Health and readiness checks.
- Fresh schema inventory and table count without assuming the historical count of 25.
- Verification queries and RLS checks.
- Rollback decision points, backup/restore or disposable-volume strategy, and failure containment.

**Acceptance criteria:**

- Database owner reviews the requirements for the later M2 runbook.
- No command can accidentally target production without an explicit environment gate.
- Rollback requirements are defined before M2 initialization authorization.

**Rollback:** Revise the runbook; no database state exists to reverse during M1 planning.

### M1-08: Define Backup and Restoration Requirements

**Action:** Document backup architecture for Zippy Operational DB, Odoo DB, Paperclip DB, application configuration, and required persistent assets.

**Required contents:**

- Scope, schedule, retention, encryption, destination, access control, monitoring, latest-success evidence, and deletion policy.
- Restoration test frequency and acceptance criteria.
- Separation of backup credentials from application credentials.
- Odoo financial-record retention requirements.

**Acceptance criteria:**

- Owner approves recovery point and recovery time objectives.
- Each authoritative system has a backup owner and restore test.
- No backup job or restoration test runs during documentation-only M1; execution belongs to later authorized milestones.

**Rollback:** Revise policy; no storage or schedules are created.

### M1-09: Define Fresh CI, Security, and Contract Evidence

**Action:** Create an evidence matrix for future authorized execution.

**Required evidence groups:**

- Staging-route and future Compose policy checks.
- Dependency installation, lock consistency, lint, format, typecheck, and unit tests.
- M2 SQL initialization, migration-state, RLS, tenancy, and rollback verification.
- M3 deterministic order intake, `202 + workflow_id`, pricing, transition, idempotency, outbox, retry, and recovery verification.
- M4 payments, dispatch, POD, and Odoo staging verification.
- OpenAPI and consumer contract tests.
- Authentication, authorization, secret scanning, image scanning, dependency scanning, and public-route checks.
- M5 Paperclip fail-closed and grant-validation tests.
- Hermes allowlist and replay/idempotency tests.
- Odoo ORM-only integration tests with no raw SQL writes.
- M6 Langfuse trace separation and non-fatal failure evidence.
- M8 backup, restore, resilience, and end-to-end evidence.
- Portal and console workflow acceptance tests.

**Acceptance criteria:**

- Every result records command, UTC timestamp, commit, environment, exit code, result, and immutable evidence location.
- Historical results are not promoted to current evidence.
- Required gates and gate owners are named.

**Rollback:** Revise evidence requirements before CI/config implementation.

### M1-10: Request Owner Approval

**Action:** Present the production PRD, reconciliation matrix, proposed decisions, canonical migration manifest, staging-route design, lock strategy, later-milestone initialization/rollback requirements, backup requirements, and evidence matrix.

**Acceptance criteria:**

- Owner records approval, rejection, or required changes for each artifact.
- Implementation authorization names exact files, services, environments, and commands.
- Container startup, migration execution, package installation, Apache/firewall changes, commits, and pushes remain prohibited unless explicitly authorized.

**Rollback:** Keep all implementation tasks blocked and revise documentation.

## M1 Exit Criteria

M1 documentation/configuration planning is complete only when:

1. The production PRD is approved as source of truth.
2. Legacy conflicts are resolved or explicitly retained as historical context.
3. Architecture decisions are approved or rejected; none remain implicitly assumed.
4. One canonical migration path and ordered manifest are approved.
5. The staging-only deployment route and future production constraints pass review without being implemented.
6. Dependency-lock policy is approved.
7. M2 staging initialization and rollback requirements are approved.
8. Backup and restoration requirements are approved for later execution.
9. Fresh evidence requirements and owners are approved.
10. A separate, explicit authorization defines the first implementation step.

## Canonical Later-Milestone Boundaries

- **M2 — Databases and tenancy:** create isolated staging databases, apply the approved migration manifest, and prove tenancy/RLS and rollback.
- **M3 — Deterministic operational core:** verify order intake, `202 + workflow_id`, pricing, state transitions, idempotency, outbox, retries, and recovery.
- **M4 — Payments, dispatch, POD and Odoo staging:** use sandbox credentials and prove payment, dispatch, compliance, POD, Odoo, and reconciliation behavior.
- **M5 — Paperclip governance:** deploy the isolated governance system and prove decisions, locks/HITL, grants, fail-closed behavior, loop controls, budgets, and audit completeness.
- **M6 — Langfuse observability:** deploy isolated observability and prove correlation, audit separation, cost reconciliation, and non-fatal failure.
- **M7-M10:** agent activation, staging resilience, production readiness, and controlled rollout remain blocked until their canonical gates are reached.

## Exact Next Task

Complete owner review of the imported `docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md` and record approval or requested corrections. Do not begin M1 implementation, modify configuration, or start services.
