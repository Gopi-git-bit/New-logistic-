# M5 Paperclip Discovery and Governance Review

## Result

**Date:** 2026-09-25

**Baseline:** `/opt/new-logistic`, `master`, `588c46a44aa9d18b144eef0313dc0f44ff7b56c6`, author `Gopinathan <gopinathdisp@gmail.com>`.

**Review scope:** Read-only discovery, source comparison, runtime inventory, and governance assessment only. No application, migration, dependency, service, container, database, external-system, or preserved-source operation was performed.

**Recommendation:** **GO FOR BOUNDED M5 IMPLEMENTATION.** D-27 authorizes only the isolated, disposable and synthetic implementation boundary recorded below; implementation remains unbegun pending its separate exact preflight.

## Preflight and Controlling Sources

- Local `HEAD`, `origin/master`, and `git ls-remote origin refs/heads/master` each resolved to `588c46a44aa9d18b144eef0313dc0f44ff7b56c6`.
- The worktree and index were clean before this report; local author configuration was `Gopinathan <gopinathdisp@gmail.com>`.
- `M4-OPERATIONS-FINANCE` is `COMPLETE`; `M5-PAPERCLIP` is the only `IN_PROGRESS` tracker row.
- The committed deployment workflow remains job-disabled with `if: ${{ false }}` in `.github/workflows/deploy-hostinger.yml`.
- Reviewed controlling sources: `.github/copilot-instructions.md`, `docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md`, `docs/DECISIONS.md`, `docs/EXECUTION_TRACKER.md`, `docs/TEST_EVIDENCE.md`, the M1 owner gate report, M3 and M4 implementation reports, `paperclip/01_governance_schema.sql`, and existing Zippy Paperclip references.

The production PRD and D-17 require a separate Paperclip database with immutable external references rather than cross-database foreign keys. Paperclip decides whether a proposed action may execute; it does not own operational, financial, or Odoo truth and cannot perform unrestricted mutations. D-22 defers agent activation, while D-26 continues to prohibit unrestricted Paperclip execution, live payments, live Odoo, and production deployment.

## Preserved Source Status and Provenance

`/opt/paperclip` exists as a directory owned by `paperclip:paperclip` with mode `0755`. It is not a Git worktree, so it has no branch, commit, remote, or Git status from which to establish version provenance or identify pre-existing uncommitted changes. Its deterministic initial inventory digest was:

```text
dc3d4355e502d4fc678b6b3b43a4e70deb86b09109fd4c0aeccd29a055fdad4
```

No existing Paperclip Git changes exist because the directory is not Git-backed. This does not establish source authenticity: the missing version, origin, commit, signature, and SBOM/provenance record are a governance blocker for deployment or integration.

The directory contains a JavaScript/TypeScript monorepo with `pnpm-lock.yaml`, root and workspace `package.json` files, database migrations under `packages/db/src/migrations/`, server/UI packages, agent and adapter packages, Docker files, and compose files. Dependency installation, builds, tests, formatting, migrations, and runtime configuration were not run. Environment names observed without values were `DATABASE_URL`, `BETTER_AUTH_SECRET`, `PAPERCLIP_TOOL_ACTION_SIGNING_SECRET`, `PAPERCLIP_CONFIG`, `PAPERCLIP_DEPLOYMENT_EXPOSURE`, `PAPERCLIP_DEPLOYMENT_MODE`, `PAPERCLIP_MIGRATION_AUTO_APPLY`, `PAPERCLIP_PUBLIC_URL`, `PAPERCLIP_HOME`, `PAPERCLIP_INSTANCE_ID`, `HEARTBEAT_SCHEDULER_ENABLED`, `HOST`, `PORT`, `NODE_ENV`, and `SERVE_UI`.

## Redacted Runtime Inventory

No Paperclip-named process, systemd unit, container, image, named volume, or Docker network was found. No Paperclip listener was identified. The host has unrelated MySQL and Redis services and listening ports; no read-only evidence connects either to Paperclip. Paperclip source compose files exist, but none was invoked. Logical database names, credentials, endpoints, environment values, and command arguments were deliberately not inspected or recorded.

Consequently, Paperclip runtime state, service user, database engine/name, network isolation, persistence, health, backups, production-resource connectivity, and effective configuration are all **NOT VERIFIED**. There is no evidence that Paperclip is connected to production resources, and no evidence that it is safely isolated from them.

## Existing Capabilities

The preserved source has broad generic capabilities: database migrations, agent/task/heartbeat concepts, policies, decisions, connections, tool gateways, authentication, and Docker deployment artifacts. It is not evidence of a Zippy-approved implementation.

The checked-in Zippy governance schema defines tenants, agents, versioned policies with checksums, proposals, invariant results, decision locks, human approvals, execution-grant fields, attempts, heartbeats, loop-guard events, token ledger, activity log, and outbox. It correctly uses external identifiers in proposals rather than cross-database foreign keys.

The only Zippy integration code is a generic HTTP `PaperclipClient`. It sends an evaluation request and converts any client error to `REJECT`, which is a safe caller-side fallback. It does not create or validate a durable execution grant, bind execution to a proposal/grant, use decision locks, enforce HITL, or prove a Paperclip API contract.

## Authority Boundary Matrix

| Boundary | Required authority | Current assessment |
|---|---|---|
| Zippy operational state | Zippy PostgreSQL and validated RPC/service | No M5 integration may mutate it directly; unimplemented enforcement |
| Accounting and ERP | Odoo API/ORM | No direct Paperclip-to-Odoo database access permitted; no such approved integration exists |
| Governance decision | Isolated Paperclip DB/service | Schema intent exists; effective runtime isolation and enforcement unverified |
| Consequential execution | Hermes allowlisted tool after validated grant | No grant-validation or narrow executor integration exists |
| Human approval | Authorized human distinct from proposing agent | Schema records a role/reference but has no enforcement shown |
| Outbox | Durable governance event publication | Table intent exists; publisher, consumer, replay handling, and n8n non-authority are unimplemented |

## Security Findings

| Severity | Finding | Effect and required disposition |
|---|---|---|
| CRITICAL | `paperclip/01_governance_schema.sql` defines no RLS, `FORCE ROW LEVEL SECURITY`, policies, role ownership, or least-privilege grants. | Tenant isolation and database access control are absent from the proposed schema. Design and prove restricted roles/RLS before use. |
| CRITICAL | No transaction/API is supplied to atomically validate decision, tenant/action/target/payload hash, expiry, revocation, nonce, and single consumption of a grant. | Grants are replayable by schema alone: `consumed_at` is mutable and not uniquely protected as a one-time state transition. Implement an atomic fail-closed consume path with concurrency proof. |
| CRITICAL | Human approvals have no constraint preventing self-approval, no approver identity/role verification, no quorum, and no enforced high-risk classification. | An agent or unauthorized actor could approve a proposal unless an absent service layer prevents it. Define and prove policy. |
| HIGH | Decision locks only have a per-proposal partial unique index. There is no lock lease/expiry/owner contract or atomic decision-state transition. | Concurrent evaluators can duplicate or race authorization. Define lock key scope, lifecycle, and serialization proof. |
| HIGH | Governance activity and outbox tables are described as append-only but lack immutable triggers, revoked update/delete privileges, sequencing, or hash chaining. | Audit records can be modified or removed by a sufficiently privileged writer. Enforce append-only behavior and prove it. |
| HIGH | Budget trigger runs `AFTER INSERT`, checks spending without locking, and pauses only after a cost row is inserted. | Concurrent costs can exceed ceilings; budget does not fail closed before work. Use an atomic reservation/ledger design and test races. |
| HIGH | Loop guard stores events but has no fail-closed threshold enforcement or binding from heartbeat/task execution to grants. | A heartbeat can continue/retry without a demonstrated guard. Heartbeats must never create authority. |
| HIGH | Policy checksum is stored but not verified or made immutable; activation and policy evaluation logic are absent. | Policy substitution/version drift is possible. Add canonical serialization, checksum verification, activation controls, and audit. |
| MEDIUM | The PL/pgSQL budget function has no explicit `search_path` hardening. | Although it is not `SECURITY DEFINER`, ownership/execution and object-resolution policy are unspecified. Apply least-privilege function controls and explicit safe search path if retained. |
| MEDIUM | Proposal payload is mutable by database privilege and the Zippy client truncates `arguments_hash` to 16 hex characters. | Payload substitution/collision resistance is insufficient for execution authorization. Use a full canonical payload hash and immutable proposal/grant binding. |
| MEDIUM | The preserved source has no Git provenance and exposes generic adapters/deployment modes. | Unreviewed runtime authority and unsafe defaults cannot be ruled out. Pin, review, and attest an approved source release before deployment. |
| MEDIUM | Rollback/forward compatibility for the checked-in standalone governance SQL is unproven. | It has no paired canonical migration/down manifest or disposable rollback evidence. |

No `SECURITY DEFINER` statement was present in the reviewed Zippy governance SQL. That absence does not compensate for the missing RLS, explicit privileges, and service-level authorization.

## Requirement Comparison

The schema's data model partially represents isolated governance, external references, policy versions/checksums, proposals, locks, approvals, grants, attempts, heartbeats, loop events, token records, audit events, and outbox rows. It does not by itself meet the required properties: tenant isolation, non-replayable grants, self-approval denial, concurrency-safe locks and budgets, append-only audit, fail-closed loop controls, restricted execution, or runtime isolation.

No evidence supports direct operational database access, direct Odoo mutation, live Odoo/Razorpay execution, production endpoints, or active external-agent execution. Those absences are not a clearance: effective configuration was intentionally not read and runtime operation is not verified.

## Schema and Integration Assessment

The approved SQL should be treated as a design input, not a migration ready for application. It lacks canonical migration placement, a down migration, an immutable manifest, role/bootstrap rules, RLS, privilege proofs, API/service contracts, and disposable test evidence. No cross-database foreign keys are present in the reviewed SQL, which is aligned with the PRD.

Zippy's existing client fails closed only for the evaluation request. It cannot establish the required proposal-to-grant-to-attempt chain and must not be wired into M4 operations until M5 defines authenticated service identities, a versioned contract, grant consumption semantics, and allowed callers. n8n remains non-authoritative; Hermes must remain the narrow allowlisted executor; Paperclip must have no Odoo database credential.

## Proposed M5 Implementation Inventory

Subject to an approved owner decision and a new exact implementation authorization, the likely inventory is:

- Canonical isolated Paperclip migration directory, manifest, reversible disposable-only migrations, bootstrap roles, RLS policies, and explicit grants.
- Governance API/service contract for proposals, invariant results, HITL, grant issue/consume/revoke, decision locks, execution attempts, audit, budgets, loop guards, and outbox.
- A Zippy-side authenticated Paperclip client that supports full SHA-256 canonical payload binding and fail-closed decisions without owning authority.
- Hermes-side allowlisted executor/grant validator; no raw SQL, no direct Odoo database access, and no agent self-approval path.
- Unit, concurrency, RLS/privilege, contract, failure, replay, rollback, and redaction tests.
- Deployment and service configuration only after separate topology/authentication approval; no adoption of the preserved source without reviewable provenance.

## Disposable Proof Strategy and Required Tests

Run only after authorization in a fresh network-isolated disposable environment with synthetic identities, generated unrecorded credentials, no published database port, read-only repository mount, exact image/source identity, and verified cleanup. Required proof includes:

- migration up/down/reapply with manifest checksums and isolated Paperclip database only;
- tenant cross-read/write denial and privilege catalog assertions under restricted roles;
- proposal invariant evaluation to decision lock, HITL approval/reject/timeout, grant issue, one-time atomic consumption, and durable execution attempt;
- replay, expired, revoked, wrong-agent, wrong-tenant, wrong-action, wrong-target, and changed-payload grant denial;
- self-approval, missing quorum/role, duplicate decision, stale-lock, and concurrent approval/consume denial;
- audit/outbox append-only, duplicate publication, consumer replay, and n8n non-authority checks;
- concurrent budget reservations and loop thresholds that fail closed before execution;
- Paperclip outage, malformed response, timeout, policy checksum mismatch, and unavailable audit/outbox behavior;
- no direct Zippy SQL, Odoo SQL, live Razorpay/Odoo, production endpoint, or external-agent call; and exact cleanup/rollback checks.

## Owner Decisions Required

The items below were **OWNER DECISION REQUIRED** at discovery time. D-27 resolves them for the Minimal MVP boundary; its values are controlling and the stronger alternatives remain unapproved.

| Decision | Minimal MVP recommendation | Safer/stronger alternative |
|---|---|---|
| Grant TTL | 5 minutes, one-time consumption | Per-action TTL policy no greater than 60 seconds for financial actions |
| Approval roles | Named finance or operations role per risk class | RBAC plus independent identity assurance and break-glass review |
| Approval quorum | One independent human for high-risk actions | Two-person quorum for financial and production-impacting actions |
| Budget ceilings | No autonomous spend; ceiling `0` until activation | Reserved per-agent/per-task budgets with owner-approved ceilings |
| Token-cost limits | Deny execution on missing limit | Per-model and per-task reservations with daily/monthly caps |
| Loop thresholds | Block at 3 identical failures, manual review for semantic loop | Deterministic per-action limits plus independent anomaly review |
| Heartbeat interval | Disabled until agent activation | Per-agent signed schedule with missed-heartbeat escalation |
| Stale-agent threshold | Manual review after 15 minutes | Risk-class-specific leases with automatic safe pause |
| Proposal expiry | 15 minutes for consequential actions | Risk-class-specific expiry, shorter for finance |
| High-risk classifications | All refunds, settlements, Odoo posting/payment/reconciliation, production and credential actions | Formal policy taxonomy with mandatory two-person controls |
| Revocation policy | Immediate revoke blocks unconsumed grants | Cryptographic denylist plus executor-side online revocation check |
| Data retention | Retain redacted governance evidence per owner/legal policy | Immutable retention schedule with legal hold and encrypted archival |
| Database topology | Separate disposable PostgreSQL database and credentials, private only | Separate managed instance/network/account with restore drills |
| Service authentication | Mutual authenticated service identity with short-lived credentials | mTLS plus workload identity and signed requests with rotation |

## Recommended Minimal MVP Boundary and Exclusions

Minimal MVP is an isolated, private Paperclip governance service that records proposals and policies, requires a distinct human for every consequential decision, issues short-lived single-use payload-bound grants, and permits only an allowlisted Hermes test executor in a disposable environment. It must fail closed. Agents remain inactive and cannot approve, execute, or override decisions.

Excluded: production deployment; production database access; live Odoo/Razorpay; direct Odoo SQL; live external-agent/model execution; changes to accounting authority; autonomous refunds, settlements, posting, or reconciliation; n8n authority; public Paperclip endpoints; secrets/configuration changes; and modification or deployment of `/opt/paperclip`.

## Proposed Owner-Approval Statement

> I, Gopinathan, approve a bounded M5 implementation in a network-isolated disposable environment only. The scope is an isolated Paperclip governance database and service that prove tenant isolation, policy integrity, human approval distinct from the proposing agent, decision locking, one-time expiring payload-bound grants, durable execution attempts, append-only audit/outbox, fail-closed budgets and loop guards, rollback, and cleanup. No production deployment, live payment, Odoo access, external-agent activation, unrestricted Paperclip execution, n8n authority, or modification/deployment of `/opt/paperclip` is authorized. The approved owner decision table in the M5 review is binding; all remaining values require a further explicit decision.

## Owner Disposition — 2026-09-25

D-27 records Gopinathan's owner approval for the Minimal MVP M5 Paperclip governance boundary. The former owner-decision items are resolved as follows: five-minute single-use atomic grants; Gopinathan as the single human approver; manual approval for all approved high-risk action classes; zero external-agent budget; three equivalent proposals within ten minutes as the loop threshold; no active heartbeat or agent authority; fail-closed approval, service, budget, and loop behavior; at least 365 days of immutable governance evidence; an isolated Paperclip PostgreSQL database with separate roles and credentials; and authenticated service-to-service access to be implemented and proven in disposable scope.

This disposition authorizes only documentation, isolated schema/migration implementation, least-privilege roles, RLS, governance service code, and disposable security, concurrency, rollback, and synthetic proof work. It is not implementation evidence, runtime-readiness evidence, production-readiness evidence, permission to deploy, permission to mutate `/opt/paperclip`, or permission to use live credentials or external services. It does not authorize live Odoo/Razorpay, autonomous business mutations, automatic refunds or settlements, unrestricted n8n/Paperclip execution, or any change to Zippy or Odoo data ownership.

## Production-Readiness Disclaimer

This review is neither implementation evidence nor runtime-readiness or production-readiness evidence. D-27 does not authorize deployment, `/opt/paperclip` mutation, live credentials, or external services. Production remains prohibited.