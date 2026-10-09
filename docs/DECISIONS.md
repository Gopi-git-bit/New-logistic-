# Zippy Logistics — DECISIONS (§25 Change Control)

> All deviations from the PRD must be logged here before implementation. This is mandatory.

## Format

```
| # | Date | Decision | Rationale | Impact | Approved By |
|---|------|----------|-----------|--------|-------------|
```

## Log

| # | Date | Decision | Rationale | Impact | Approved By |
|---|------|----------|-----------|--------|-------------|
| D-01 | 2026-08-01 | Tesseract as default OCR | Free, no API costs, runs locally | None — interface is engine-agnostic | @Gopi |
| D-02 | 2026-08-01 | `vector` extension name (not `pgvector`) | Postgres 16 naming convention | Migration scripts updated | @Gopi |
| D-03 | 2026-08-01 | Docker Compose over Kubernetes | Solo developer, VPS deployment | Simpler ops, single-node | @Gopi |
| D-04 | 2026-08-01 | Razorpay primary, Stripe failover | India-first payments | Dual integration | @Gopi |
| D-05 | 2026-08-15 | `match_nearby_drivers` returns `users.user_id` | Driver assignment is by user, not vehicle | D-05 alignment | @Gopi |
| D-06 | 2026-08-15 | `validate_payment_plan` full mode = 100% advance | Business rule: full payment means full advance | Handler auto-sets advance=total | @Gopi |
| D-07 | 2026-08-28 | Move workers/ to root level | PRD canonical structure | Repository reorganization | @Gopi |
| D-08 | 2026-08-29 | API Reliability & Security Contract | Autonomous-agent-safe API specification | New doc `docs/API-RELIABILITY-SECURITY.md` | @Gopi |
| D-09 | 2026-08-29 | Backend Execution Model Correction | FastAPI + Qoder Wake + Paperclip + Hermes + Odoo 18; No Temporal | Updated soul.md, PRD-backend.md, PRD-agents.md, copilot-instructions.md | @Gopi |
| D-10 | 2026-08-29 | Production API Key Wiring & Integration Hardening | Full audit + canonical env contract + FastAPI + config validation + secret redaction | New files: api/, .env.production.example, Dockerfile.api, docs/DEPLOYMENT-KEY-OWNERSHIP.md | @Gopi |

## Pending Decisions

| ID | Question | Options | Recommendation |
|----|----------|---------|----------------|
| R1 | DeepSeek model IDs | `deepseek-v4-pro` / `deepseek-v4-flash` on OpenRouter | Confirm availability first |
| R4 | Razorpay live keys | Sandbox → Live KYC | Business/compliance required |
| R5 | Permit verification API | Vahan API, SERPAPI, custom | National permit scope TBD |
| R9 | Honcho deployment | Self-hosted vs managed | Self-hosted for control |

## Bounded Development Authorizations

### D-39: Isolated OMS Recommendation Staging Bridge Development

**Status:** Owner-authorized implementation and mocked HTTP validation only,
2026-10-09, by the current user instruction.

Base the new `feat/m7-oms-staging-bridge` branch and isolated worktree on PR #9's
reviewed head `70c372fdd1f1328eb09a4175f028d4a7755fa77d`. Preserve existing
worktrees and uncommitted files; reuse discovery and completed evidence without
repeating audits. The owner selected an OpenAI-compatible chat-completions
protocol with an explicit full HTTPS endpoint and exact model ID. This is not
approval of a particular provider, endpoint, model, credential or live request.

Implement the existing `RecommendationAgent` protocol and a finite, explicitly
invoked synthetic runner outside normal API/worker registration. Reuse existing
shortlist-order fallback and complete-permutation validation; do not introduce a
matcher or assignment authority. Limit each run to one request, no retries or
redirects, bounded input/output and total timeout, cancellation and cleanup.
Send only opaque candidate references and synthetic distance/score features.
Require isolated provider configuration; reject all non-allowlisted environment
variables before running. Do not load repository environment files or give the
runner operational, service-role, payment, assignment or governance credentials.

Keep D-37/D-38 fake-only restrictions intact. Do not instantiate telemetry or the
legacy key-enabled tracer. Validate only with mocked HTTP transport, including
failure, fallback, cancellation, cleanup and noninterference. The bounded live
plan in [M7_OMS_STAGING_BRIDGE.md](plans/M7_OMS_STAGING_BRIDGE.md) is a proposal,
not execution permission. M6 staging/live gates remain UNVERIFIED; M7 activation
remains BLOCKED; D-33 remains pending. Every refund retains manual approval;
settlement, deterministic assignment and Paperclip controls remain unchanged.
No live providers, SQL execution, merge, deployment or agent activation.

**Separate finalization authorization, 2026-10-09:** The owner authorizes review
of the actual bridge diff, concrete in-scope fixes and affected checks, a scoped
commit/push on the existing feature branch, and a draft PR against master.
Identify inherited PR #9 changes in the actual base diff and verify CI on the
resulting exact head. Preserve decisions/worktrees. If terminal Git authentication
fails, preserve the commit and export a commit patch; do not repeat sign-in loops.
This is publication permission only, not live execution, merge, deployment,
financial-control changes or agent activation.

### D-38: Fake-Only Recommendation Review Contract

**Status:** Owner-authorized development, checks, feature-branch commit/push and
draft PR only, 2026-10-09, by the current user instruction.

Start from published `origin/master` at
`a3b4d97542d55fa39c5b738504783ae2f40703ba` in a new isolated worktree on
`feat/m7-recommendation-review`; preserve all existing worktrees. Reuse the
recommendation and synthetic shadow contracts without recreating their changes.
Use immutable synthetic candidate snapshots, explicit fake reviewer identities
and in-memory fake storage only. Support pending, accepted, rejected and expired
records; reject stale/mismatched snapshots and unauthorized reviewers.

The owner selected explicit per-record expiry, idempotent identical retries,
and rejection of conflicting retries or changes to terminal reviews. Acceptance
records an advisory candidate preference only, never assignment or operational
authorization. Snapshot version and ordered numeric features must both match.
This is a synthetic contract, not runtime identity authentication, durable
storage, a governance approval or an in-process sandbox.

Keep the contract outside active API/worker registration. Automatic deterministic
assignment, orders, prices, payments, every-refund manual approval, settlements
and Paperclip decisions/locks remain unchanged. No live providers, SQL, hosting
changes, deployment, activation, direct master push or merge. M6 staging/live
evidence remains UNVERIFIED; M7 live activation BLOCKED; D-33 pending. This
permission does not approve D-33 or waive any staging/governance gate.

### D-34: M7-A Provider-Neutral Recommendations Development Only

**Status:** Owner-authorized development and tests only, 2026-10-08, by the current user instruction: "I authorize development and tests for agent recommendations only."

This permits a limited M7-A development exception on `feat/m7-a-recommendation-contract`, in an isolated worktree based on `origin/master` at `3245cee5c9c872244c37f5c1ae7ad0f2483d783d`. Reuse existing OMS/TMS matching and transaction rules. Add only a provider-neutral, read-only ranking contract over a backend-supplied eligible shortlist, fake-adapter tests, bounded asynchronous timeout and deterministic fallback. No live provider or hosted service is authorized. Recommendations are not assignment commands, approval grants or permission to mutate state, and are not wired into the active worker registry or API.

Customers book; vendors provide vehicles/drivers. A transport company can act as either role per transaction. Existing deterministic backend rules retain autonomous assignment authority and must revalidate authorization, eligibility, concurrency, idempotency and state transitions before any mutation. Agents may only suggest/rank and cannot bypass those controls. Every refund retains manual owner/finance approval and no self-approval. Existing settlement requirements and Paperclip controls remain unchanged.

D-33 is already reserved for the pending combined proposal in the original user worktree and remains **Pending owner approval**; its uncommitted content is not imported or approved here. D-34 is the next unused ID across that pending work and the committed D-01 through D-32 records. This authorization does not approve D-33, Paperclip removal, cloud migration, live payments, deployment, SQL execution, M6 completion, agent activation or any unmet M6 acceptance criterion. It is not permission to merge or deploy. M6 remains `IN_PROGRESS`; M7 activation remains `BLOCKED`.

Tests must prove valid recommendations, malformed or mutation-bearing output rejection, timeout, unavailable provider, deterministic fallback and absence of operational/financial mutation. Only fake agents and synthetic data are permitted. Existing staging, provider and M6 owner-handoff gates remain outstanding; passing host tests must not be recorded as staging acceptance.

**Separate publication authorization, 2026-10-08:** The owner subsequently authorized committing and pushing only `workers/src/zippy_workers/recommendations.py`, `workers/tests/test_m6_handlers.py`, `docs/DECISIONS.md` and `docs/EXECUTION_TRACKER.md`, and opening a draft PR titled "M7-A: provider-neutral recommendations with deterministic fallback". This permits diff review, scoped defect fixes, host tests/lint and inspection of PR CI, with no weakened checks or scanner exceptions. It does not expand the development/activation authority above, approve D-33 or M6 completion, or permit SQL, live tools/integrations, payments, service activation, merge or deployment. The contract remains unwired into live assignment. Preserve the original worktree.

**Separate foundation merge authorization, 2026-10-08:** The owner subsequently authorized merging PR #7's four-file foundation after verifying its initial head `fa20a174af236a87a73968531881e6311a8cbefb`, inspecting actual review findings, fixing scoped defects and obtaining fresh green CI for any revised head. Mark ready and merge normally with the exact final reviewed SHA only after checking effective branch requirements and merge-triggered workflows; stop if deployment would be triggered. This is repository integration permission only, not live agent activation, approval of D-33, M6 completion, SQL execution, live integrations/payments, service activation or deployment. Preserve the original worktree. D-34's development scope and all milestone/financial/governance gates remain unchanged.

### D-36: M6 Development Acceptance and Guarded Repository Integration

**Owner acceptance status:** OWNER ACCEPTED — 2026-10-09 — Gopinathan

The owner explicitly accepts M6-E005 as synthetic development evidence and approves limiting M6 development completion to D-31's development scope plus that supplemental evidence. Development acceptance is not staging or live acceptance. Live instrumentation, deployed storage/credential isolation, exporter recovery, and real provider/financial-ledger reconciliation remain mandatory gates before the corresponding live features are enabled. They are deferred, not waived or marked PASS.

The owner authorizes final review of PR #8, initially at `8711c87ba7359e3626dc822b19196537485f44c1`, including actual review findings and surgical in-scope fixes. Any revised head requires fresh green CI. Mark ready and merge normally only if review is clear, all five checks pass for the exact reviewed head, effective branch requirements are satisfied, and merging triggers no deployment. Use an exact-SHA guard; never bypass checks or reviews. Inspect resulting master CI. After successful merge, reconcile the PRD, tracker and evidence to label M6 explicitly development complete, retaining a separate staging acceptance checklist and M7 live activation BLOCKED.

D-36 is the next unused ID after committed D-35 and reserved, uncommitted D-33. All previous decisions are preserved. D-33 remains **Pending owner approval**; this acceptance does not approve its proposal or change Odoo/Paperclip authority. Deterministic assignment, every-refund manual approval, settlement, idempotency and governance controls remain unchanged.

Identify only the smallest next M7 development slice from the existing approved plan and its specific owner choices; do not begin implementation or live activation. Preserve existing worktrees and uncommitted work. No shared-database SQL, payments, service activation or deployment is authorized. D-31's disabled defaults, synthetic-only sampling, redaction, zero external telemetry spending and separately approved hosting/credentials/residency/retention/sampling gates remain controlling.

**Superseding repository-action restriction, 2026-10-09:** The owner's subsequent instruction permits scoped code edits, tests, commit/push of PR #8's feature branch and PR updates, but explicitly prohibits merge unless separately authorized. This supersedes D-36's earlier conditional merge permission. Do not mark M6 development complete in the tracker or reconcile completion after an unperformed merge. The synthetic development acceptance above remains recorded; staging/live gates, D-33 pending status and business controls remain unchanged.

**Renewed conditional authorization and post-merge reconciliation, 2026-10-09:** The owner now explicitly directs reconciliation after PR #8 and recording renewed conditional merge authorization. D-36's earlier exact-head, green-check, review, branch-requirement and no-deployment conditions are retained; the intervening no-merge instruction above remains historical, not deleted. PR #8 was merged by Gopi-git-bit at `2026-10-09T06:34:11Z`; local Git verifies merge commit `dfd3f35167972755322a3746c5628ac9e0b7189f` with parents `f885444ac9bdd85dce9afcd012d234d56c713c69` and `e6973e505aed61d2d7f950ae0553e10c3dd5c0e6`. GitHub CI run [37894212090](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/37894212090) completed successfully for that exact master SHA. Under D-36, M6 is **DEVELOPMENT COMPLETE** for D-31 plus accepted M6-E005 only. This does not retrospectively certify external deployment configuration or repeat accepted audits/proofs.

Staging/live evidence remains **UNVERIFIED**, M7 live activation **BLOCKED**, and D-33 **Pending owner approval**. Current task authorization explicitly prohibits performing any merge, regardless of the recorded historical/renewed conditional authorization; this branch must remain a draft PR. No live providers, hosting changes, deployment, shared-database SQL or agent activation are authorized.

### D-37: M7 Capability/Allowlist and Synthetic Shadow Development

**Status:** Owner-authorized bounded development, tests, scoped commit/push and draft PR only — 2026-10-09 — Gopinathan.

Start from current `origin/master` at `dfd3f35167972755322a3746c5628ac9e0b7189f` on new isolated branch `feat/m7-shadow-allowlist`. Preserve all existing worktrees and uncommitted files. Reuse `capabilities.py`, the backend's already eligible deterministic shortlist order and D-34 `recommendations.py`; do not add another matcher or ranking authority. The smallest development allowlist is `order_management / recommend_drivers / recommend_drivers`, requiring the existing `read:drivers` capability. Other agents/actions/tools are denied before execution, including agents with broader production financial or oversight permissions.

The harness accepts synthetic numeric fixtures and its built-in fake agent only, compares advisory rankings with the deterministic baseline, and proves malformed/mutation-bearing output, timeout and unavailable/failed providers preserve the baseline. No arbitrary adapters, operational database ports, external clients, registry entries, API routes or persistence are added. This is a development harness, not authentication or a sandbox for hostile in-process Python. Human-reviewed recommendations, provider selection and activation remain separately gated.

Customers book; vendors supply vehicles/drivers; transport companies may play either role per transaction. Deterministic backend assignment remains authoritative. Every refund requires manual approval; settlement, idempotency, state transitions, Paperclip decision locks and financial system-of-record controls remain unchanged. Vercel and Zoho CRM connections are available for later separately approved integration; Razorpay is pending. Availability is not permission to call or configure them.

No live provider calls, hosting changes, deployment, shared-database SQL, agent activation or merge. M6 development completion under D-36 does not waive UNVERIFIED staging/live evidence, unblock M7 live activation or approve reserved D-33. Accepted audits and disposable proofs are reused, not repeated.

### D-35: M6 Supplemental Development Evidence and Draft PR Only

**Status:** Current owner-authorized development checks, scoped fixes and draft-PR publication only, 2026-10-08: "I authorize focused code/test fixes and a draft PR for this task. No deployment or live agent activation."

Work starts from `origin/master` at `f885444ac9bdd85dce9afcd012d234d56c713c69` in the isolated `feat/m6-development-evidence` worktree. Reuse D-31/D-32 and M6-E003/M6-E004; do not repeat the repository audit or accepted disposable proof without a concrete reason. Only missing synthetic correlation, audit/usage independence, cost/usage reconciliation, nonfatal failure/recovery and fake-storage checks, plus concrete telemetry defects, are authorized. Changed code may receive focused regression checks and normal unchanged PR CI. Commit and push the bounded slice and open a draft PR; do not merge.

D-31's disabled defaults, synthetic-only sampling, allowlist/redaction, worker-boundary scope, sole observability administrator and zero external telemetry spending remain controlling. No runtime instrumentation, shared-database SQL, live credentials, provider/billing access, payments, service activation, storage deployment or live agent activation is authorized. Assignment, every-refund manual approval, settlement and Paperclip controls remain unchanged. Preserve all existing worktrees and uncommitted work. D-33 remains pending; D-34 remains limited recommendation development; D-31/D-32 acceptance is not amended.

M6 remains `IN_PROGRESS`; M7 activation remains `BLOCKED`. M6-E005 is supplemental development evidence, not owner acceptance or deployed-storage/live-billing evidence. The next owner decision is to accept or reject that evidence and explicitly decide whether completion is limited to the D-31 development boundary, deferring the PRD's separate deployment and real cost-ledger reconciliation to separately approved staging, or whether those checks remain prerequisites to M6 completion. Cloud/self-hosting, deployment, credentials/live emitters, residency, retention and production sampling remain explicit owner/staging gates; no values or thresholds are selected here.

## M1 MVP Draft Decisions

All records below are **OWNER APPROVED** by Gopinathan on 2026-09-08. They define the MVP direction and do not by themselves authorize implementation, service activation, infrastructure changes, database migration, payment activation, or modification of legacy documents.

### D-11: Low-Cost MVP and One-Corridor-First Validation

| Field | Draft record |
|---|---|
| Context | The production PRD targets a broad freight platform, while current owner direction reduces phase one to a low-cost MVP. |
| Decision or proposed decision | Validate one defined operating corridor first, with a small operational workflow and measurable human review before expanding routes, features, or geography. |
| MVP justification | Limits operating cost, support load, compliance variance, and failure surface while proving repeat bookings and vendor supply. |
| Business consequences | Scope, service hours, corridor, success metrics, and expansion criteria require owner definition before launch. |
| Security/data consequences | Minimize collected data and roles; retain auditable booking, trip, payment, approval, and exception records for the pilot. |
| Deferred capabilities | Nationwide rollout, broad marketplace coverage, triangle-route optimization, advanced control tower, and advanced analytics. |
| Implementation milestone | M1 scope/contracts; M3-M4 controlled workflow validation; M8 staging E2E. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-12: One Responsive Role-Based Web Application; No Native Mobile Apps

| Field | Draft record |
|---|---|
| Context | Legacy documents prescribe separate portal, console, PWA, FlutterFlow, and native/mobile surfaces. |
| Decision or proposed decision | Phase one uses one responsive web application for phones, tablets, and computers. Native customer, vendor, and driver mobile apps are out of scope. |
| MVP justification | Delivers the required journeys with one frontend release path and lower support, build, store, and device-management cost. |
| Business consequences | The public entry page presents `Book a Vehicle` and `Register a Vehicle`; each leads to appropriate registration/authentication. Protected role-based views serve customers, vendors/drivers, and admins. |
| Security/data consequences | Browser sessions require server-side RBAC, least-privilege APIs, secure session handling, and no browser exposure of service credentials. |
| Deferred capabilities | Native mobile apps, app-store distribution, dedicated driver PWA/mobile offline features, and separate console applications. |
| Implementation milestone | M1 frontend/API contracts; implementation requires separately approved scope after M1. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-13: Customer, Vendor/Driver, and Admin Web Flows

| Field | Draft record |
|---|---|
| Context | MVP users require distinct journeys while sharing one application and backend. |
| Decision or proposed decision | Customers register once and return to book vehicles, track authorized trips, and review payment transactions. Vendors register themselves, vehicles, and applicable drivers; registration is not eligibility and requires admin approval. Admin functions remain protected server-side. |
| MVP justification | Supports recurring demand, controlled supply onboarding, and operational oversight without separate applications. |
| Business consequences | Vendor eligibility, vehicle/driver verification, and admin action reasons must be visible in authorized workflows; no automatic provider activation. |
| Security/data consequences | Enforce role and resource authorization on every server-side action; preserve audit records for approvals, rejections, and status changes. |
| Deferred capabilities | Self-service automated approval, native flows, and advanced provider marketplace tooling. |
| Implementation milestone | M1 contract design; M2 identity/RLS; M3 workflow; M4 compliance/POD. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-14: WhatsApp Group Isolation

| Field | Draft record |
|---|---|
| Context | A WhatsApp group exists outside the product, and legacy material permits an isolated messaging pilot. |
| Decision or proposed decision | The WhatsApp group remains completely isolated from the production MVP. It is not an identity provider, booking channel, workflow authority, payment source, or data synchronization path. |
| MVP justification | Avoids integration cost and prevents informal group activity from becoming an operational system of record. |
| Business consequences | Staff may use the group outside product workflows, but bookings, assignments, payment status, and approvals must use approved product channels. |
| Security/data consequences | No production credentials, personal data exports, webhooks, or group-derived authority are introduced. |
| Deferred capabilities | WhatsApp Business onboarding, notifications, and any isolated messaging pilot integration. |
| Implementation milestone | Deferred; any integration requires a new approved decision and later authorized scope. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-15: Transaction-Specific Customer/Vendor Roles and Transport-Company Participation

| Field | Draft record |
|---|---|
| Context | Legacy `users.base_role`/`active_role` fields and profile tables cannot alone express every transaction relationship. |
| Decision or proposed decision | The booking party is the customer for that transaction; the vehicle/capacity provider is the vendor. A transport company may participate as either customer or vendor by transaction, while legal identity remains singular and is not duplicated inconsistently. |
| MVP justification | Matches marketplace operations without forcing a transport company into a permanent customer-only or vendor-only classification. |
| Business consequences | Order, trip, offer, pricing, settlement, and UI contracts must identify the transaction role and authorized party. |
| Security/data consequences | A single `users.role` value must not grant cross-role access; application validation or a safer relational design must protect polymorphic `party_type`/`party_id` links. |
| Deferred capabilities | Complex multi-entity delegation and broader partner-network role models. |
| Implementation milestone | M1 contracts; M2 identity/schema/RLS; M3 workflow enforcement. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-16: Phase-One Single Operational Platform and Future Isolation

| Field | Draft record |
|---|---|
| Context | Owner direction sets phase one as one platform-wide operational tenant, while the PRD requires future multi-tenant capability. |
| Decision or proposed decision | Run phase one as a single operational platform while designing identity, company, and resource boundaries so later tenant isolation can be added without data reclassification or incompatible public contracts. |
| MVP justification | Avoids premature tenancy complexity while preserving the ability to expand safely. |
| Business consequences | Customer, transport-company, driver, and admin identities remain distinct; company participation remains transaction-specific where applicable. |
| Security/data consequences | `company_id` scoping/isolation is incomplete in the draft schema and must be explicitly designed, enforced, and tested before multi-tenant activation. |
| Deferred capabilities | Tenant self-service, tenant-specific policy administration, and multi-tenant onboarding. |
| Implementation milestone | M1 requirements; M2 tenancy/RLS design and fresh proof. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-17: Operational, Governance, and ERP Database Boundaries

| Field | Draft record |
|---|---|
| Context | The production PRD, Paperclip schema, and Odoo blueprint assign different sources of truth. |
| Decision or proposed decision | Zippy operational DB owns operational entities/events; Paperclip DB owns policies, proposals, approvals, grants, and execution attempts; Odoo DB owns accounting/ERP records. Cross-system links use immutable external IDs, idempotency keys, and events, never cross-database foreign keys. |
| MVP justification | Keeps a low-cost architecture coherent while avoiding conflicting records and unrestricted cross-service access. |
| Business consequences | Orders/trips/POD remain operational; governance determines whether consequential actions may execute; accounting remains in Odoo. |
| Security/data consequences | Separate credentials and private databases are required; Paperclip must not share the Zippy or Odoo database; direct Odoo core SQL is prohibited. |
| Deferred capabilities | Broader service decomposition and nonessential synchronization. |
| Implementation milestone | M1 contracts; M2 database isolation; M5 governance; M4 Odoo staging. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-18: Odoo Financial Authority and Zippy Operational Finance Records

| Field | Draft record |
|---|---|
| Context | Legacy Zippy payment tables coexist with an Odoo financial source-of-truth requirement. |
| Decision or proposed decision | Odoo is the financial/accounting authority. MVP integration is limited to partner synchronization, draft customer invoices, draft vendor bills, and read-only accounting/payment-status synchronization. Zippy stores operational payment status, financial requests, verified gateway evidence, POD evidence, idempotency keys, and Odoo external references; it must not become a competing accounting ledger. |
| MVP justification | Preserves a simple operational workflow while retaining one authoritative accounting system. |
| Business consequences | Customer payment, invoice, settlement, refund, and reconciliation status presented to users must distinguish operational progress from Odoo-authoritative accounting outcome. |
| Security/data consequences | Payment status comes from verified gateway/Odoo evidence, never client or agent assertions; Odoo access uses supported API/ORM and narrow capabilities. |
| Deferred capabilities | Full Odoo customization, automatic posting, settlements, reconciliation, refunds, and ledger mirroring. |
| Implementation milestone | M1 contracts; M4 sandbox/staging integration. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-19: Manual Approval for Every Refund

| Field | Draft record |
|---|---|
| Context | The approved reconciliation supersedes legacy automatic refund thresholds, and current owner direction requires manual approval for every refund. |
| Decision or proposed decision | Every refund requires recorded manual approval. No automatic refund behavior is authorized at any amount. |
| MVP justification | Limits financial risk while the MVP establishes support and finance review practices. |
| Business consequences | A refund request must include requester, approver, reason, decision time, and execution evidence; refund completion must be distinguishable from request/approval. |
| Security/data consequences | Prohibit self-approval; bind approved refund execution to the request, amount, target, idempotency key, and valid Paperclip grant where governance is implemented. |
| Deferred capabilities | Automatic refunds and any threshold-based refund automation. |
| Implementation milestone | M1 contracts; M4 financial flow; M5 governance evidence. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-20: Authorized Real-Time Trip and Payment Visibility

| Field | Draft record |
|---|---|
| Context | Both transaction participants need timely status while tracking and payment data are sensitive. |
| Decision or proposed decision | Customers and vendors/drivers may receive authorized real-time trip and payment-status updates within protected role-based views through authenticated HTTP commands plus Server-Sent Events. Admins have server-side RBAC-protected operational views. |
| MVP justification | Reduces manual status calls and supports exception handling without a separate control tower. |
| Business consequences | The event/status contract must define which stage, recipient, delay, and fallback message each view can receive. |
| Security/data consequences | Real-time location requires history plus order/trip/party authorization boundaries, not only a latest-location field; payment visibility exposes only authorized operational status and never credentials or ledger internals. |
| Deferred capabilities | Advanced control tower, unrestricted fleet tracking, and broad analytics subscriptions. |
| Implementation milestone | M1 event/API contract; M2 authorization; M3 operational events; M4 payment evidence. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-21: Browser Location Limitation and Manual Milestone Fallback

| Field | Draft record |
|---|---|
| Context | A responsive browser application cannot assume continuous, reliable background location capture on phones. |
| Decision or proposed decision | During active trips, browser geolocation may submit controlled periodic location updates. Location remains optional, consented, and best-effort; support manual trip milestones and admin-visible exceptions when location is unavailable, stale, denied, or inaccurate. |
| MVP justification | Avoids native-app cost while preserving basic trip operations. |
| Business consequences | Pickup, in-transit, arrival, delivery, POD-pending, and exception milestones require an authorized manual path and evidence policy. |
| Security/data consequences | Collect minimum location data with purpose/retention controls; authorize location visibility per trip and retain history needed for audit rather than overwriting only the latest point. |
| Deferred capabilities | Continuous background tracking, geofencing, automated route deviation, and high-frequency telematics. |
| Implementation milestone | M1 contract; M3 state/event workflow; M4 POD and exception handling. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-22: Agents as Bounded Assistants

| Field | Draft record |
|---|---|
| Context | The production PRD allows governed agents, but the MVP must not make LLMs business authorities. |
| Decision or proposed decision | No LLM is mandatory for the deterministic MVP core. Agents may provide bounded assistance only after separate activation approval, and any AI provider/model selection remains configurable and deferred. Deterministic backend services remain authoritative for pricing, order transitions, payment evidence, eligibility, and policy enforcement. Agents cannot approve their own actions. |
| MVP justification | Captures useful automation opportunities without coupling core operations to unverified models or high operating cost. |
| Business consequences | Human staff retain exception, refund, eligibility, and consequential-action control; automation begins only in shadow/recommendation modes. |
| Security/data consequences | No raw model reasoning retention; model IDs/configuration, allowlists, budgets, Paperclip grants, fail-closed behavior, and audit evidence are mandatory before activation. |
| Deferred capabilities | Full autonomous multi-agent platform, RAG, AI-directed state/pricing decisions, and unrestricted tool execution. |
| Implementation milestone | M1 policy/contracts; M5 governance; M6 observability; M7 activation. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-23: MVP Deferral Register

| Field | Draft record |
|---|---|
| Context | The low-cost MVP needs an explicit boundary against legacy platform breadth. |
| Decision or proposed decision | Defer native mobile apps; full autonomous multi-agent platform; RAG; Kafka/Redis Streams; advanced control tower; ML/dynamic pricing; triangle-route optimization; full Odoo customization; automatic settlements/refunds; advanced analytics platform; and nationwide rollout. |
| MVP justification | Concentrates budget and operational attention on a secure, role-based web workflow for one corridor. |
| Business consequences | Deferred capabilities must not be represented as current MVP commitments, acceptance criteria, or production readiness evidence. |
| Security/data consequences | Avoids unnecessary data pipelines, model exposure, message infrastructure, financial automation, and geographic compliance risk. |
| Deferred capabilities | All capabilities named in the proposed decision remain out of MVP scope until separately approved. |
| Implementation milestone | No implementation authorized; future scope requires owner-approved decision and milestone assignment. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-24: Admin Account Creation, Blocking, and Unblocking Controls

| Field | Decision record |
|---|---|
| Context | MVP operations require fast, accountable account control without changing historical operational or financial evidence. |
| Decision or proposed decision | An authorized admin may create customer and driver accounts. An authorized admin may immediately block or suspend a customer or driver for operational, safety, fraud, payment, compliance, or misuse concerns. The block takes effect for new login sessions, new bookings, new assignment acceptance, and other protected actions; existing sessions must be revoked or rejected at the next protected request. |
| MVP justification | Gives operations a direct safety and fraud-control path while avoiding a separate administration system or second-admin workflow in phase one. |
| Business consequences | Blocking does not cancel an active trip, refund payment, or release/hold settlement. Each uses its own controlled workflow. A blocked participant with an active order/trip creates an immediate admin exception for operational review. Only an authorized admin may unblock, with a recorded reason. |
| Security/data consequences | Every create, block, suspension, and unblock action must record affected account, account type, acting admin, reason code, written note where required, timestamp, previous/new status, and correlation/audit ID. Blocking preserves historical orders, trips, locations, payments, invoices, settlements, POD, disputes, and audit evidence. Agents may recommend but cannot execute, approve, or reverse account control. Permanent deletion remains governed by retention, privacy, and legal controls. |
| Deferred capabilities | Second-admin approval, automated agent blocking, and permanent deletion workflow. |
| Implementation milestone | M1 contract requirements; M2 identity/RLS; M3 protected action enforcement and exceptions. |
| Owner-approval status | OWNER APPROVED — 2026-09-08 — Gopinathan. |

### D-25: Bounded n8n Cloud Integration-Adapter Role

**Owner-approval status:** OWNER APPROVED — 2026-09-09 — Gopinathan.

This decision permits only later, separately authorized implementation. It does not authorize deploying, configuring, connecting, or activating n8n during M1.

#### Permitted Future Uses

n8n Cloud may later be used for:

- supported Odoo API/ORM integration;
- partner synchronization;
- requesting creation of draft customer invoices;
- requesting creation of draft vendor bills;
- read-only accounting and payment-status synchronization;
- notifications and failure alerts;
- scheduled reconciliation;
- consuming controlled asynchronous integration jobs from Zippy;
- reporting integration results back through authenticated FastAPI endpoints.

These are permissions for later implementation milestones, not authorization to deploy or configure n8n now.

#### Authoritative Systems

- FastAPI owns commands, validation, authorization, and deterministic business rules.
- Zippy Operational PostgreSQL remains the operational source of truth.
- Odoo remains the accounting source of truth.
- Paperclip remains the future authorization/governance boundary for consequential agents.
- File/object storage owns document binaries according to the approved ownership model.

#### Durable Queue and DLQ

- Zippy Operational PostgreSQL owns the durable outbox, inbox, retry, and dead-letter records.
- Every integration job requires an immutable event/correlation ID and idempotency key.
- n8n execution history is operational convenience, not the authoritative queue, DLQ, audit ledger, or recovery evidence.
- A failed n8n workflow cannot cause loss of the authoritative Zippy job record.
- Manual replay must be authorized and audited.

#### Prohibited n8n Authority

n8n must not independently:

- calculate or modify deterministic prices;
- accept bookings as the system of record;
- assign vehicles or drivers;
- change authoritative order or trip states;
- mark client-supplied payment data as verified;
- approve or execute refunds;
- approve or release settlements;
- post Odoo invoices, bills, payments, or reconciliations automatically;
- directly write to Odoo core tables;
- directly mutate Zippy business tables outside approved FastAPI commands;
- issue its own Paperclip authorization;
- approve an action that it executes;
- become the production SSE/location-tracking engine;
- hold the sole backup-decryption key;
- act as the backup ledger or restore controller.

#### Security Boundary

- n8n Cloud must never connect directly to PostgreSQL.
- It may access only narrowly scoped authenticated HTTPS integration endpoints.
- Later implementation must include least-privilege credentials, request authentication/signing, replay protection, idempotency, rate limits, correlation IDs, audit evidence, and credential rotation.
- Only the minimum necessary personal, location, POD, and financial metadata may enter n8n execution data.

#### Relationship to D-14

- D-14 remains controlling for WhatsApp.
- The WhatsApp group/pilot remains completely isolated and is not a production synchronization path.
- D-25 does not authorize WhatsApp integration.
- D-25 clarifies that n8n as a technology may later perform narrowly controlled non-WhatsApp integration-adapter work.
- n8n remains excluded from Zippy's authoritative production core.

#### Paperclip Timing

- Paperclip remains deferred for the deterministic MVP core.
- When consequential agents are introduced, the required order remains: action request -> Paperclip authorization/grant -> allowlisted execution -> recorded result.
- n8n cannot bypass this order.

### D-26: M4 Operations-Finance Implementation Approval and Boundaries

**Owner-approval status:** OWNER APPROVED — 2026-09-11 — Gopinathan (product owner, finance owner, and initial Odoo owner).

Verbatim approval:

> I, Gopinathan, acting as product owner, finance owner, and initial Odoo owner, approve M4-OPERATIONS-FINANCE implementation on 2026-09-11. I approve FastAPI as the Razorpay webhook ingress into the canonical Zippy PostgreSQL evidence path. Initial payment work is limited to Razorpay sandbox and synthetic tests; no live keys or live payment execution are authorized. Verified authorized, captured, and failed gateway events may update only compatible operational payment projections. A refund.processed event may reconcile evidence only for a refund that already has recorded manual approval; it may not create, approve, initiate, or automatically execute a refund. Every refund requires manual approval at every amount. Settlement release remains manual. I approve a draft-only Odoo adapter using supported API/ORM methods and fake-server tests; no live Odoo credentials, autonomous posting, payment, reconciliation, or direct database access are authorized. Production deployment, automatic refunds or settlements, unrestricted n8n/Paperclip execution, and changes to accounting authority remain prohibited.

#### Binding Boundaries

- FastAPI owns Razorpay webhook validation and canonical persistence into `webhook_receipts`, `gateway_events`, and `payment_projections`.
- Razorpay work is sandbox-only with synthetic test payloads; live keys and live payment execution remain unauthorized.
- `payment.authorized`, `payment.captured`, and `payment.failed` map only to compatible operational projections (`pending`, `evidence_verified`, `failed`); `refund.processed` reconciles evidence only for an existing refund execution backed by a recorded manual approval and never creates, approves, initiates, or executes a refund.
- Every refund requires recorded manual approval at every amount; requester self-approval is rejected; settlement release stays manual; settlement eligibility is an operational projection only.
- Odoo integration is draft-only (`res.partner` find/create, draft customer invoice, draft vendor bill, immutable external references) through supported JSON-RPC/API methods with fake-server tests; `action_post`, payment registration/reconciliation, settlement release, direct SQL, and cross-database constraints are prohibited.
- No live Odoo credentials, production deployment, automatic refunds or settlements, unrestricted n8n/Paperclip execution, or change to accounting authority is authorized.

## Owner-Approved MVP Technical Directions

These directions are **OWNER APPROVED** by Gopinathan on 2026-09-08. Implementation remains governed by the assigned milestone, validation evidence, and applicable go-live gates.

| Choice | Owner-approved low-cost direction | Owner-approval status |
|---|---|---|
| Operational database hosting | Use the existing VPS PostgreSQL for the MVP; do not add Supabase Cloud. | OWNER APPROVED — 2026-09-08 — Gopinathan |
| Minimal Paperclip timing | Defer Paperclip runtime activation until consequential runtime agents are introduced; preserve governance design and database isolation. | OWNER APPROVED — 2026-09-08 — Gopinathan |
| Real-time transport | Use ordinary authenticated HTTP commands plus Server-Sent Events; during active trips, browser geolocation may submit controlled periodic updates. | OWNER APPROVED — 2026-09-08 — Gopinathan |
| Payment gateway activation | Begin with Razorpay sandbox and/or manually recorded payment evidence. Live activation requires a separate go-live approval gate. | OWNER APPROVED — 2026-09-08 — Gopinathan |
| Odoo MVP integration depth | Limit to partner synchronization, draft customer invoice, draft vendor bill, and read-only accounting/payment-status synchronization. Do not automatically post, settle, reconcile, or refund. | OWNER APPROVED — 2026-09-08 — Gopinathan |
| AI provider/model policy | No LLM is mandatory for deterministic MVP core; defer AI provider/model selection and keep any future selection configurable. | OWNER APPROVED — 2026-09-08 — Gopinathan |
| Apache/ServerAvatar routing | Preserve ServerAvatar/Apache and use a same-origin responsive web application with an approved `/api` reverse-proxy route. Do not replace Apache or redesign infrastructure during M1. | OWNER APPROVED — 2026-09-08 — Gopinathan |

### D-27: Minimal MVP M5 Paperclip Governance Boundary

**Owner approval status:** OWNER APPROVED — 2026-09-25 — Gopinathan

> I, Gopinathan, acting as product owner and initial governance owner, approve the Minimal MVP M5-PAPERCLIP governance boundary on 2026-09-25. The unverified `/opt/paperclip` directory is preserved as reference-only and is not an authoritative or deployable source. The authoritative implementation must be tracked in the `new-logistic` repository and use an isolated Paperclip PostgreSQL database with separate roles and credentials. M5 is limited to disposable development and synthetic tests; production deployment and live external integrations are not authorized.
>
> Paperclip may evaluate proposals and issue governance grants, but it may not own or mutate orders, trips, tracking, payments, refunds, settlements, invoices, balances, accounting records, or Odoo records. Every refund, settlement release, Odoo posting or reconciliation, financial adjustment, policy change, permission change, and production-related action requires manual approval by Gopinathan. Agents and proposal creators may not approve their own actions.
>
> Each execution grant must be tenant-bound, actor-bound, action-bound, target-bound, payload-hash-bound, revocable, non-replayable, atomically consumed, and expire after five minutes. Governance must fail closed when policy or approval is missing, a grant is invalid or expired, the governance service is unavailable, a budget is exhausted, or a loop guard is triggered. During M5, external-agent spending is zero and budget behavior must use synthetic tests. Three equivalent proposals within ten minutes trigger the loop guard. Governance decisions, approvals, grants, attempts, audit events, and outbox evidence must be immutable and retained for at least 365 days.
>
> This approval authorizes documentation, isolated schema and migration implementation, least-privilege roles, RLS, governance service code, and disposable security/concurrency/rollback proofs only. It does not authorize production deployment, live credentials, live Odoo or Razorpay access, autonomous business mutations, automatic refunds or settlements, unrestricted n8n/Paperclip execution, or changes to Zippy or Odoo data ownership.

#### Derived Controls

- `/opt/paperclip` is reference-only and immutable during M5.
- Authoritative M5 source belongs in `new-logistic`.
- Paperclip PostgreSQL must be isolated from Zippy PostgreSQL and Odoo.
- Separate database roles and credentials are mandatory.
- No cross-database foreign keys or direct access to Zippy or Odoo tables.
- Grant TTL is five minutes; grant consumption is atomic and single-use.
- Three equivalent proposals within ten minutes trigger the loop guard.
- External-agent budget during M5 is zero.
- Governance evidence retention is at least 365 days.
- Gopinathan is the single Minimal MVP human approver; self-approval is prohibited.
- All approved high-risk action classes require manual approval.
- Missing, invalid, expired, unavailable, exhausted, or looped conditions fail closed.
- Only disposable development and synthetic proof execution is authorized.

### D-28: M5 Paperclip Privileged Function Boundary

**Status:** OWNER APPROVED — 2026-09-25 — Gopinathan

> I, Gopinathan, acting as product owner and initial governance owner, approve a narrowly scoped PostgreSQL `SECURITY DEFINER` boundary for M5-PAPERCLIP on 2026-09-25. This approval applies only to the isolated Paperclip governance database and only to functions implementing proposal creation, invariant recording, decision-lock acquisition and release, human approval or rejection, execution-grant issuance, atomic grant consumption, grant revocation, execution-attempt recording, heartbeat recording, token-cost and budget enforcement, and loop-guard evaluation.
>
> Every approved function must be owned by a dedicated `NOLOGIN` Paperclip function-owner role that is neither superuser nor `BYPASSRLS`. It must use a fixed safe `search_path`, schema-qualified objects, typed and validated inputs, tenant checks, least-privilege table grants, and concurrency-safe transactions. Dynamic SQL, arbitrary relation names, generic table mutation, cross-database access, and secret access are prohibited.
>
> Execute permission must be revoked from `PUBLIC` and granted only to explicitly approved Paperclip application roles. Application roles must retain no unrestricted direct mutation authority, schema creation authority, role-management authority, ownership authority, or permission to create or replace privileged functions. Paperclip and public schemas must not be writable by untrusted roles.
>
> The implementation must prove function ownership, fixed `search_path`, absence of public execution, denial of direct table writes, forced RLS, tenant isolation, resistance to temporary-object and search-path shadowing, denial of unauthorized functions and arguments, atomic single-use grant consumption, and complete governance evidence. Governance failures must remain fail-closed.
>
> This exception does not authorize production deployment, production database changes, live credentials, external integrations, business-data ownership, autonomous financial execution, unrestricted Paperclip execution, or modification of `/opt/paperclip`. It authorizes only repository-tracked migrations and disposable synthetic PostgreSQL proofs under D-27.

#### Structured Controls

- Scope: isolated Paperclip database only.
- Function owner: dedicated `NOLOGIN`, `NOSUPERUSER`, `NOBYPASSRLS` role.
- Safe fixed `search_path` and schema-qualified objects are mandatory.
- Dynamic SQL is prohibited.
- `PUBLIC` execute is prohibited.
- Direct application-role table mutation is prohibited.
- Schema creation and privileged-function replacement are prohibited.
- Tenant validation and forced RLS are mandatory.
- Least-privilege per-function execution grants are mandatory.
- Concurrency-safe transitions are mandatory.
- Search-path and temporary-object shadowing tests are mandatory.
- Production and external integration remain prohibited.

### D-29: Minimal MVP M5-B Authenticated Governance Service Boundary

**Owner approval status:** OWNER APPROVED — 2026-09-26 — Gopinathan

> I, Gopinathan, acting as product owner and initial governance owner, approve the Minimal MVP M5-B authenticated governance service boundary on 2026-09-26.
>
> The corrected canonical reference-only `/opt/paperclip` inventory digest is `dc3d4355e502d4fc678b6b3b43a4e70deb86b09109fd4c0aeccd29a055fdad44`, calculated using the documented exclusions for `.git`, `node_modules`, and `.next`. The earlier 63-character value was a transcription defect and is not a valid SHA-256 digest.
>
> M5-B must use only the twelve privileged Paperclip functions already authorized by D-28 and proven by M5-A. Read-only proposal or grant status retrieval is excluded from M5-B. No new privileged function, role, table grant, schema mutation, or direct table access is authorized.
>
> The authenticated subject, tenant, Paperclip agent UUID, policy UUID, owner-approver identity, and synthetic-executor identity must be resolved from server-controlled configuration or trusted repository logic. Clients may not select or override agent IDs, policy IDs, tenant IDs, approval identities, executor identities, roles, payload hashes, or policy checksums. JWT roles, `user_metadata`, request metadata, and other client-editable claims must not grant authority.
>
> Manual approval and rejection are authorized only when the authenticated subject exactly matches the configured Gopinathan owner subject and also holds the server-resolved admin role. Proposal creators, agents, executors, and other subjects may not approve their own proposals.
>
> M5-B may implement FastAPI models, routes, a separate Paperclip database pool, a repository that invokes only the approved functions, server-controlled synthetic identity mappings, redaction controls, and a fake executor for disposable tests. The service must fail closed on missing mappings, missing approval, invalid policy checksum, exhausted budget, loop guard, unavailable governance database, invalid or expired grant, identity mismatch, or uncertain authorization.
>
> M5-B remains limited to disposable development and synthetic tests. It must not modify `/opt/paperclip`, `docker-compose.yml`, production configuration, deployment workflows, Zippy business data, Odoo data, payment data, accounting records, or external systems. It does not authorize live credentials, live integrations, production deployment, autonomous financial execution, automatic refunds or settlements, or unrestricted Paperclip execution.

#### Enforceable Constraints

- Only the twelve existing D-28 functions may be called.
- No GET/read-status endpoint is authorized.
- No Paperclip schema, role, grant or migration change is authorized.
- Agent, policy, approver and executor identities are server-controlled.
- Client-provided identity or authority fields are prohibited.
- `user_metadata` and JWT role claims provide no authorization.
- Owner decisions require both the configured exact owner subject and server-resolved `admin`.
- The synthetic executor cannot call Zippy, Odoo, Razorpay or another external system.
- `docker-compose.yml`, deployment configuration and `/opt/paperclip` remain untouched.
- All errors and governance uncertainty fail closed.

### D-30: M5 Paperclip Completion and M6 Langfuse Discovery Handoff

**Owner acceptance status:** OWNER ACCEPTED — 2026-09-27 — Gopinathan

> I, Gopinathan, acting as product owner and initial governance owner, accept completion of M5-PAPERCLIP on 2026-09-27.
>
> I accept the isolated Paperclip governance database implemented in commit `520e8f48003e98166c029366943798e08bc042a3` and the authenticated governance service implemented in commit `e3a96d97ec9c04a88d8561e69397ae8c7b896ea7`.
>
> I accept the disposable M5-B proof with exit status `0`, proof-log SHA-256 `7a33b36dd7513011006c5176fc48df70610417a9d0d2f2fe2ec24b6b4039463f`, `46 passed, 0 skipped, 1 warning`, successful single-use concurrency enforcement, M5-A security regression, rollback, reapply, secret scanning, network and socket isolation, and complete disposable cleanup. I also accept the host validation result of `90 passed, 14 skipped, 1 warning`, with the database-dependent behavior separately covered by the disposable proof.
>
> M5 remains subject to D-27, D-28, and D-29. This acceptance does not authorize production deployment, live credentials, live integrations, autonomous financial execution, changes to Zippy or Odoo data ownership, unrestricted Paperclip execution, or modification of `/opt/paperclip`.
>
> I authorize a documentation-only milestone transition marking `M5-PAPERCLIP` complete and making `M6-LANGFUSE` the sole `IN_PROGRESS` task. This transition authorizes M6 discovery and boundary definition only. It does not authorize M6 production deployment, live telemetry export, live credentials, or implementation beyond an owner-approved M6 scope.

### D-31: Minimal MVP M6-A Langfuse Telemetry Boundary

**Owner approval status:** OWNER APPROVED — 2026-09-27 — Gopinathan

> I, Gopinathan, acting as product owner and observability owner, approve the Minimal MVP M6-A Langfuse telemetry boundary on 2026-09-27.
>
> This approval is based on the M6 discovery checkpoint committed as `f09c7993f6ce2649e85b74639d07517644fedd71`. M6-A is limited to repository-tracked telemetry contracts, redaction controls, a disabled-by-default adapter, a fake in-memory collector, and disposable synthetic tests. It does not authorize Langfuse Cloud, a self-hosted Langfuse deployment, live credentials, external telemetry transmission, production telemetry, or paid services. External spending during M6-A must remain ₹0.
>
> Telemetry must be disabled by default. Sampling must be 0% outside disposable tests and may be 100% only for synthetic test events. During M6-A, only the worker/agent execution boundary may emit telemetry. FastAPI business routes, Paperclip governance, Zippy PostgreSQL, Odoo, payment systems, and external integrations must not emit live telemetry.
>
> Permitted telemetry fields are limited to server-generated trace and correlation identifiers, pseudonymous synthetic tenant and actor identifiers, service and operation names, non-sensitive event types, model and provider aliases, timestamps, latency, input/output token counts, estimated cost, confidence where applicable, success or failure codes, policy outcome codes, and redacted exception class names.
>
> Raw prompts, model responses, system instructions, customer or driver personal data, email addresses, phone numbers, addresses, exact order/trip/vehicle identifiers, payment, refund, settlement, invoice, accounting or Odoo data, governance grants, approval payloads, payload contents, database records, stack traces, request or response bodies, JWTs, API keys, passwords, database URLs, webhook secrets, and other credentials are prohibited.
>
> Client-provided identifiers or metadata may not establish telemetry identity or authority. Tenant, actor, workflow, and correlation identifiers must be generated or resolved by trusted server logic. Any identifiers used in tests must be synthetic and pseudonymized.
>
> Telemetry delivery must fail open: Langfuse or collector unavailability must not block, change, retry, falsely succeed, or corrupt a business or governance operation. Redaction must fail closed at the telemetry boundary: if an event cannot be proven safe, that telemetry event must be dropped while the underlying business operation continues normally.
>
> The M6-A proof must use a fake local collector and synthetic inputs only. Test artifacts must be private, temporary, contain no prohibited data, and be removed during cleanup. Repository evidence may retain only test counts, markers, and cryptographic hashes—not telemetry payloads.
>
> Gopinathan is the only approved initial observability administrator. Cloud versus self-hosted Langfuse, data residency, production retention, production sampling, live emitters, production credentials, and production deployment remain deferred and require separate owner approval.
>
> Langfuse remains an observability system only. It may not become a source of truth, authorization system, governance authority, workflow engine, retry controller, business database, or financial/accounting system. It may not write to Zippy, Paperclip, or Odoo databases or alter any operational outcome.
>
> This approval authorizes M6-A implementation and disposable synthetic proof only. It does not authorize production deployment, live telemetry export, new infrastructure, changes to accounting or governance authority, autonomous financial execution, or unrestricted external-agent activity.

### D-32: Minimal MVP M6-A Langfuse Telemetry Acceptance

**Owner acceptance status:** OWNER ACCEPTED — 2026-09-27 — Gopinathan

> I, Gopinathan, acting as product owner and observability owner, accept completion of the Minimal MVP M6-A Langfuse telemetry boundary on 2026-09-27.
> I accept the repository-tracked implementation committed as `7cef6e54929a3bd5328bcb2ec8dcf0be2177e61c` with subject `feat(observability): implement M6-A telemetry boundary`.
> I accept M6-E003 and the final disposable synthetic proof recorded in `/tmp/m6a-proof.vYDFZu`, with exit status `0`, mode `0600`, SHA-256 `ba77a1f079bff8e61253bb060ce3cc89f41fd94baaa6ff515c67ec14c6003cf8`, `62 passed` focused telemetry tests, `122 passed` worker regression tests, successful cleanup, and `m6a_proof=PASS`. I accept `focused_tests count=62=PASS` as semantically equivalent to `focused_tests=PASS count=62`.
> I acknowledge the complete proof history: two environment/harness failures, one fail-closed redaction failure, and the final passing execution. These retained failures do not invalidate the corrected passing implementation or proof.
> I accept the disabled-by-default telemetry configuration, zero default sampling, strict telemetry allowlist, HMAC pseudonymization, fail-closed redaction, fail-open delivery, fake in-memory collector, synthetic-only tests, worker-boundary-only scope, absence of live Langfuse integration, and ₹0 external spending.
> This acceptance remains subject to D-31. It does not authorize Langfuse Cloud, self-hosted Langfuse, live credentials, external telemetry transmission, production telemetry, production sampling, paid services, production deployment, runtime instrumentation outside the approved worker boundary, or any change to Zippy, Paperclip, Odoo, payment, accounting, governance, or operational authority.
> I authorize a documentation-only M6-E004 acceptance record for M6-A. M6-LANGFUSE must remain `IN_PROGRESS` until I separately approve its completion or the next milestone transition. No M7 implementation or production action is authorized by this acceptance.

#### Enforceable Constraints

- M6-A implementation and proof are owner-accepted as implemented in commit `7cef6e54929a3bd5328bcb2ec8dcf0be2177e61c`.
- `M6-LANGFUSE` remains the sole `IN_PROGRESS` milestone task; no milestone transition occurred.
- `M7-AGENTS` remains `BLOCKED`; no M7 implementation is authorized.
- All D-31 prohibitions remain active: Langfuse Cloud, self-hosted Langfuse, live credentials, external telemetry transmission, production telemetry, paid services, production deployment, and runtime instrumentation outside the approved worker boundary.
- This acceptance changed only the five authorized documents; no code, tests, proof scripts, dependencies, workflows, Docker files, production configuration, or retained proof logs were modified.
- No test, proof, installation, deployment, live credential use, external telemetry transmission, or production action occurred during this acceptance.
- External spending during and after M6-A acceptance remains ₹0.
