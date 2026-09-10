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
| D-11 | 2026-09-02 | Composio/TinyFish integration boundary | Composio is a typed MCP tool gateway; TinyFish is a bounded adapter. Neither is a system of record or database synchronization bus. | Added runtime contract, allowlisted adapter, production Compose wiring and deployment health gate | @Gopi |

## Pending Decisions

| ID | Question | Options | Recommendation |
|----|----------|---------|----------------|
| R1 | DeepSeek model IDs | `deepseek-v4-pro` / `deepseek-v4-flash` on OpenRouter | Confirm availability first |
| R4 | Razorpay live keys | Sandbox → Live KYC | Business/compliance required |
| R5 | Permit verification API | Vahan API, SERPAPI, custom | National permit scope TBD |
| R9 | Honcho deployment | Self-hosted vs managed | Self-hosted for control |

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
