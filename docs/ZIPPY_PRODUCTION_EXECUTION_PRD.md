# Zippy Logistics Production Execution PRD

**Version:** 1.0
**Status:** Authoritative execution guide with human gates
**Date:** 2026-09-03
**Owner:** Gopinathan
**Target:** Zippy Logistics production foundation on the Hostinger VPS

**Repository adoption status:** Owner-approved and established as the production execution source of truth at commit `cee3307861fc4d19c5a85c7bbce3ca1367c9a6a2`. This document supersedes conflicting production claims; conflicting legacy documents remain historical until reconciled, and their business rules must not be silently rewritten or discarded. Architecture deviations require a proposed `DECISIONS.md` entry and owner approval.

## 1. Purpose

This document is the controlling build and deployment contract for the Zippy Logistics repository. It consolidates the latest PRD, Paperclip governance schema, Zippy operational schema completion, and Odoo ownership blueprint into one instruction set for VS Code GitHub Copilot and other coding agents.

The system is **ready to begin controlled implementation and staging validation**. It is **not yet authorized for unrestricted production cutover**. Production activation requires all gates in this document and an explicit human approval from the owner.

## 2. Agent operating rule

For each task, the coding agent must follow this lifecycle:

`DISCOVER → PLAN → IMPLEMENT → TEST → VERIFY → READY_FOR_REVIEW → HUMAN_APPROVAL → COMPLETE`

The agent must stop when:

- a high-impact requirement is missing or contradictory;
- a requested action could affect production data, security, DNS, firewall rules, payments, accounting, or service availability;
- tests fail twice for the same cause;
- the current server or repository state differs materially from this PRD;
- a secret may have been exposed;
- an irreversible action would be required.

The agent must never silently choose a business rule, security exception, financial threshold, or destructive operation.

## 3. Source-of-truth hierarchy

### 3.1 Business and architecture decisions

1. The owner's explicit current instruction.
2. Human-approved entries in `DECISIONS.md` that post-date this PRD.
3. This PRD.
4. `01_paperclip_governance.sql` for governance ownership and controls.
5. `02_zippy_operational_completion.sql` plus the validated operational migrations.
6. `03_odoo_ownership_relationships.md` for Odoo integration boundaries.
7. Older PRDs, Obsidian notes, and supporting documents.
8. Agent assumptions, which are never authoritative.

### 3.2 External interfaces

The actual supported behavior of Odoo, Razorpay, Mapbox, model providers, Supabase, Langfuse, and other external systems controls wire formats and error behavior. A mismatch with this PRD must be documented in `DECISIONS.md`; it does not authorize changing Zippy business rules.

### 3.3 Known superseded directions

- Temporal is excluded unless a new human-approved decision explicitly restores it.
- Durable asynchronous work uses PostgreSQL-backed tasks, workers, row locking, retries, idempotency keys, and outbox processing.
- Paperclip must not share the Zippy operational database or Odoo database.
- Composio is not a database synchronization bus.
- Agents must not write directly to Odoo PostgreSQL.
- Do not introduce Kafka, Celery, Django, or Kubernetes into the production core without approved change control.
- The existing n8n messaging pilot may remain isolated, but it is not the authoritative transaction engine.

## 4. Product outcome

Zippy Logistics is a multi-tenant freight orchestration platform for Tamil Nadu and South India. It coordinates customers, drivers, vehicle owners, transport companies, dispatch, tracking, POD, payments, invoicing, settlement, compliance, and return-trip opportunities while using human-controlled AI automation.

The platform must prioritize:

- reliable order fulfilment;
- low empty-running distance;
- deterministic pricing and state transitions;
- verified driver and vehicle compliance;
- payment and settlement integrity;
- Tamil-capable customer operations;
- auditable agent decisions;
- low operating cost with human intervention focused on exceptions.

## 5. Current verified infrastructure state

| Item | Verified state |
|---|---|
| Hostinger VPS | KVM 4, running, Ubuntu 24.04, 4 CPU, 16 GB RAM, 200 GB disk |
| Management | ServerAvatar connected through SSH; server health reported good |
| Domain | `zippylogitech.com` active |
| Existing web stack | Apache 2 registered by ServerAvatar |
| Existing application | `zippy_logitech`, GitHub framework, active |
| Paperclip | Manually installed; location, process, database, ports, and persistence not yet verified |
| Docker | Installation and runtime state not yet verified |
| Langfuse | Not yet verified as installed |
| Production readiness | Blocked pending discovery, staging validation, security tests, backup/restore proof, and human approval |

Do not replace Apache with nginx, reinstall Docker, move Paperclip, or add Langfuse until M0 discovery proves the current topology and an approved plan addresses conflicts.

## 6. Authoritative architecture

### 6.1 Deterministic application plane

- **Client applications:** preserve the committed applications during M0. Older sources disagree between Next.js/Vite/PWA and FlutterFlow clients; this is a recorded decision point before frontend restructuring.
- **Switch Point API:** FastAPI with Pydantic validation and a versioned OpenAPI contract.
- **Order acceptance:** `POST /api/v1/orders` persists a `PENDING` request durably and returns `202 Accepted` with a `workflow_id`. The `workflow_id` identifies a PostgreSQL-backed workflow/task, not a Temporal workflow.
- **Durable processing:** PostgreSQL tasks/outbox, `FOR UPDATE SKIP LOCKED`, retry limits, leases, idempotency, and dead-letter/human-exception handling.
- **Operational data:** PostgreSQL 15+ with PostGIS; Supabase-compatible Auth, Realtime, RLS, and RPCs where the repository actually uses them.
- **ERP/finance:** Odoo 18 CE through supported API/ORM methods only.

### 6.2 Agent plane

- **Paperclip:** governance truth. Decides whether a proposed consequential action may execute.
- **CEO Agent:** supervises agent performance, reviews evidence and exceptions, assigns corrective tasks, pauses unsafe agents, and escalates high-risk decisions. It cannot override human-only controls.
- **Harness/orchestrator:** decomposes approved initiatives into tasks and routes models. It has no financial execution authority.
- **Hermes:** execution adapter for narrow allowlisted tools. It must present a valid Paperclip execution grant before consequential actions.
- **DeepSeek:** primary configurable model for matching, extraction, or agent reasoning where approved.
- **Claude:** configured fallback or specialist model where approved; not a second independent source of business truth.
- **Honcho:** contextual memory only; it cannot override current operational, financial, or governance records.
- **Langfuse:** AI trace, prompt, evaluation, latency, token, and cost telemetry only.
- **Composio/MCP:** controlled tool connectivity. It does not own data and must not synchronize databases.
- **Crawl4AI/TinyFish:** optional browsing/research capabilities, isolated from authoritative transaction flows unless explicitly approved.

### 6.3 Infrastructure plane

- Hostinger VPS supplies compute.
- ServerAvatar supplies server/application management.
- Docker Compose may package services after Docker and the existing Paperclip installation are verified.
- The currently installed Apache reverse proxy remains in place until a human-approved proxy decision.
- Public exposure is limited to HTTPS endpoints and required SSH administration. Databases, Redis-like queues, internal workers, Paperclip internals, and Langfuse storage remain private.

## 7. System-of-record boundaries

| System | Authoritative ownership | Must not own |
|---|---|---|
| Zippy Operational DB | companies, users, customers, vendors, drivers, vehicles, orders, trips, dispatch offers, locations, POD metadata and verification, service commitments, operational exceptions/events, gateway events, idempotency, outbox, external references, financial requests | accounting ledger, Odoo invoice truth, governance approvals |
| Odoo DB | partners, CRM, quotations, sale/purchase orders where used, invoices, vendor bills, credit notes, taxes, journals, payments, reconciliation, accounting balances | high-frequency tracking, Paperclip approvals, operational event stream |
| Paperclip DB | tenants, agent registry, policies, initiatives, tasks, proposals, invariants, decision locks, human approvals, execution grants/attempts, heartbeats, loop-guard events, token-cost ledger, governance log/outbox | orders, trips, vehicle location, invoice balances, GL entries |
| Langfuse storage | traces, spans, generations, prompt versions, evaluations, latency, tokens, model cost | legal/business audit truth or operational state |
| Honcho memory | contextual memory and preference modeling | authoritative current business state |

Rules:

- No cross-database foreign keys.
- Cross-system links use immutable external IDs, idempotency keys, correlation IDs, and versioned events.
- Odoo is accessed through supported API/ORM only—never raw SQL against core tables.
- Zippy may store `odoo_*_id` references and gateway evidence, but not a competing financial ledger.
- Paperclip answers “may this action execute?”; it does not perform unrestricted business mutations.

## 8. Core invariants

### 8.1 State changes

- Order status changes only through a validated transition service/RPC.
- Direct agent updates to `orders.status` are forbidden.
- State transition plus operational event must commit atomically.
- Duplicate requests must return the earlier result or become a safe no-op.

### 8.2 Safety and compliance

- `ORD-INV-003`: reject cargo that exceeds vehicle capacity or violates body/special-handling compatibility.
- `DSP-INV-001`: no assignment when required insurance or fitness documents are expired.
- Hazardous cargo is rejected until a compliant specialized workflow is approved.

### 8.3 Payments, POD, and Odoo

- `PAY-INV-002`: no vendor payment authorization without verified acceptable POD evidence.
- Razorpay webhook signatures must be verified server-side; client confirmation is never financial proof.
- Every payment, invoice, posting, refund, and reconciliation side effect requires idempotency.
- Odoo determines posted/reconciled accounting state.
- Governed Odoo posting/payment/refund actions require a valid, unexpired, payload-bound Paperclip execution grant.
- Financial thresholds and rate/commission policies may not be changed by a coding or runtime agent.

### 8.4 Agent safety

- Governance evaluation errors fail closed to `HOLD` or `HITL_REQUIRED`.
- Three repeated identical failures or a semantic loop with no state change blocks the task and alerts a human.
- Tool calls are allowlisted and capability checked before execution.
- An agent cannot approve its own high-risk action.
- Budget ceilings pause agents automatically; overrides require human approval.

## 9. Security contract

- Never print, paste, commit, or log secret values.
- Copilot may inspect environment-variable names and whether values are present, but not reveal values.
- `.env*`, private keys, database dumps, credentials, and generated tokens must be ignored by Git.
- Use separate credentials per service and environment.
- Production keys are available only to the service that consumes them.
- Rotate any key found in Git history, terminal output, chat, logs, or screenshots.
- Use a non-root deployment user and key-based SSH. Do not disable existing root access until the replacement login is tested.
- Apply least privilege, tenant scoping, RLS, server-side RBAC, rate limiting, input validation, and audit logging.
- Database ports must not be internet-accessible.
- Do not modify UFW, DNS, TLS, SSH, Apache, Docker daemon, or production environment configuration without a reviewed plan and human approval.
- Do not collect raw model reasoning. Store trace metadata, inputs/outputs as policy permits, hashes, summaries, and redacted evidence.

## 10. Observability and audit

Business audit and AI observability are separate:

- Zippy operational events and Paperclip governance logs record who/what/when and authoritative state changes.
- Langfuse records how an AI execution behaved: model, prompt version, tools, latency, tokens, cost, errors, evaluation, and outcome.

Every agent execution must correlate:

`tenant_id → initiative_id → task_id → heartbeat_id/trace_id → proposal_id → execution_grant_id → execution_attempt_id → operational_event_id`

Langfuse failure must not corrupt or block deterministic business transactions. Trace delivery must be buffered/retried and errors surfaced operationally.

## 11. Environment and configuration

Repository files may contain `.env.example` with names and safe placeholders only. Expected categories include:

- Zippy operational database and Supabase-compatible services;
- Paperclip database and signing/grant configuration;
- Odoo URL/database/user/API key;
- Langfuse public/secret keys and host;
- model-provider keys and explicit model IDs;
- Razorpay test/live keys and webhook secret;
- Mapbox server/client keys;
- Hermes internal authentication;
- Honcho configuration if the deployment model is approved;
- alerting, backup, and CI security tokens.

Do not hardcode hypothetical model names such as `deepseek-v4-pro`. Validate actual provider model IDs at startup and keep them configurable.

## 12. Repository expectations

The agent must first inspect the existing repository. It may propose, but must not blindly impose, this logical layout:

```text
apps/                   client applications
services/api/           FastAPI Switch Point API
workers/                durable workers and integrations
packages/contracts/     schemas, events, shared types
packages/domain/        deterministic pricing and state rules
db/zippy/               operational migrations and seeds
db/paperclip/           governance migrations and seeds
odoo/custom_addons/     supported Odoo extensions only
infra/compose/           development/staging/production Compose files
infra/proxy/             approved Apache or nginx configuration
tests/                   unit, contract, integration, E2E, security, failure tests
docs/                    PRD, decisions, runbooks, evidence
```

If the actual repository differs, preserve working structure and record a proposed migration in `DECISIONS.md`.

## 13. Milestones and gates

### M0 — Discovery and baseline

Read-only only. Inventory:

- repository path, remotes, branches, current commit, dirty state, languages, dependency locks, CI, migrations, tests, TODOs;
- Docker/Compose versions, containers, images, networks, volumes, Compose files;
- Paperclip location, process/container/service, version, ports, database, volumes, health, logs, backup status;
- Apache vhosts/TLS and occupied ports;
- PostgreSQL instances and database separation;
- existing application processes and scheduled jobs;
- environment-variable names and file permissions without exposing values.

Deliver `docs/reports/M0_DISCOVERY_REPORT.md`, `docs/reports/RISK_REGISTER.md`, and `docs/plans/M0_TO_M1_PLAN.md`. Make no system or repository changes unless the owner approves the plan.

### M1 — Repository, contracts, and CI baseline

- resolve architecture conflicts through approved `DECISIONS.md` entries;
- establish `.env.example`, secret scanning, dependency locks, lint/type/test commands;
- validate OpenAPI/event/schema contracts;
- establish a staging-only deployment route.

### M2 — Databases and tenancy

- build fresh staging databases independently;
- apply validated migrations in dependency order;
- prove RLS/tenant isolation and migration rollback;
- ensure there are no cross-database FKs or Odoo core SQL modifications.

### M3 — Deterministic operational core

- validate order intake, pricing, state transitions, idempotency, outbox, retries, and failure recovery;
- test the FastAPI `202 + workflow_id` contract;
- keep agents out of pricing and state-machine authority.

### M4 — Payments, dispatch, POD, and Odoo staging

- use test/sandbox credentials only;
- prove duplicate delivery prevention;
- prove compliance exclusions and manual fallback;
- prove POD gate, draft invoice, governed posting, and reconciliation without ledger mirroring.

### M5 — Paperclip governance

- apply the isolated governance schema;
- prove proposal → invariant evaluation → decision lock/HITL → grant → execution attempt;
- prove fail-closed behavior, loop blocking, budget pause, and audit completeness.

### M6 — Langfuse observability

- deploy separately from Paperclip and operational/Odoo data;
- instrument agent traces with correlation IDs;
- prove audit/trace separation and cost-ledger reconciliation;
- keep Langfuse failure non-fatal to deterministic operations.

### M7 — Agent activation

- resolve actual model IDs, OCR provider, permit verification, and Honcho deployment;
- enforce capability matrices and tool allowlists;
- begin shadow mode, then human-reviewed recommendations, then narrowly approved automation.

### M8 — Staging E2E and resilience

- run clean-environment unit, integration, contract, E2E, security, and failure tests;
- test service outage, timeout-after-success, duplicate webhooks, worker crash/retry, stale locks, and rollback;
- perform backup and restore drills for every stateful system.

### M9 — Production readiness review

- no unresolved critical defects or HIGH/CRITICAL security findings;
- all production environment names present and secrets validated without disclosure;
- monitoring, alerts, backups, restores, runbook, and rollback proven;
- live external systems validated with approved credentials;
- human go-live approval recorded.

### M10 — Controlled production rollout

`shadow → internal pilot → canary → monitored expansion → full rollout`

Each step requires predefined success/rollback thresholds. Live payment activation, autonomous financial actions, DNS cutover, and irreversible changes always require explicit human approval.

## 14. Required test evidence

Production readiness requires fresh evidence, regardless of previously reported test counts:

- unit tests for deterministic pricing, state machines, scoring, and policy rules;
- migration up/down tests on fresh databases;
- tenant-isolation and capability-denial tests;
- API/event/Odoo/Razorpay contract tests;
- idempotency tests for order intake, webhook receipt, assignment, invoice creation, payment, posting, refund, and reconciliation;
- HITL approve/reject/timeout/bypass tests;
- worker lease/retry/dead-letter/loop tests;
- Langfuse trace completeness and ledger-cost comparison;
- backup restoration and production rollback drill;
- end-to-end booking → dispatch → tracking → POD → governed invoice → settlement in staging.

Tests may not be skipped, muted, rewritten to accept broken behavior, or replaced with assertions unsupported by execution evidence.

## 15. Open human decisions

These decisions block only the milestones that depend on them:

1. Confirm the committed frontend topology before frontend restructuring.
2. Confirm actual DeepSeek/Claude model IDs and provider routing.
3. Choose the POD OCR provider behind a stable interface.
4. Choose National Permit verification method; default is manual HITL when unverified.
5. Confirm Honcho cloud/self-hosted deployment or defer it.
6. Complete WhatsApp Business onboarding before live notifications.
7. Confirm Razorpay KYC and authorize live keys only at production gate.
8. Select SonarCloud/self-hosted scanning or an approved equivalent.
9. Choose phase-one tenant onboarding; admin-provisioned is the current safe default.
10. Confirm required Odoo custom modules and seed/master data.
11. Choose whether Apache remains the production reverse proxy or is migrated through a tested cutover.

## 16. Definition of done

A milestone is done only when its code, tests, security evidence, observability, rollback, documentation, and required human approval are complete. “The code was generated,” “the container started,” or “the agent said it succeeded” is not completion.

## 17. Immediate authorization

The coding agent is authorized now to execute **M0 read-only discovery** and prepare its reports. It is not authorized by this document to install packages, change the server, migrate a database, expose a port, modify secrets, deploy Langfuse, replace Paperclip, activate payments, change DNS, or cut over production.
