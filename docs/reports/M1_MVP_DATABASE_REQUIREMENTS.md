# M1 MVP Database Requirements

## Status and Authority

**Task:** `M1-DB-REQUIREMENTS`
**Baseline:** `8334f0a0550f60e53cdf9d64a8ff7a10dd795ced`
**Mode:** Documentation-only database requirements contract. No SQL, migration, ORM model, configuration, credential, database, or runtime action is authorized.

This is the authoritative requirements contract for future MVP schema work. It preserves D-11 through D-24 and the production PRD. The existing initial schema, operational-completion draft, Paperclip schema, and Odoo blueprint are design inputs only; none is approved as an executable MVP migration chain.

## Ownership Model

| Store | Authority | Must not own |
|---|---|---|
| Zippy Operational PostgreSQL | Identities, roles, registrations, vehicles, quotes, orders, trips, assignments, locations, POD metadata/verification, operational payment evidence, financial requests, exceptions, idempotency, receipts, outbox, and audit events | Odoo ledger, posted invoice/bill truth, reconciliation truth, Paperclip approvals/grants |
| Odoo | Accounting partners, posted invoices/bills, taxes, journals, payments, reconciliation, and accounting balances | High-frequency tracking, operational event stream, governance records |
| Paperclip DB, deferred | Governance policies, proposals, approvals, grants, attempts, and governance audit when consequential runtime agents are introduced | Operational orders/trips/location and Odoo accounting truth |
| File/object storage | Vehicle document and POD binaries | Authorization, mutable business state, or financial truth; PostgreSQL holds metadata, integrity references, and access decisions |

No cross-database foreign keys are permitted. Cross-system links use immutable external IDs, correlation IDs, idempotency keys, timestamps, and versioned events. Odoo core tables are accessed only through supported API/ORM methods; direct SQL writes are forbidden.

## Mandatory Modeling Corrections

Future implementation must reject these legacy patterns:

- A single `users.role` value as the sole authorization or transaction-role model.
- Duplicated legal identities when a transport company participates as customer or vendor.
- Unvalidated polymorphic `party_type`/`party_id` references; use typed relational joins or explicitly validated participation records.
- Direct agent updates to order or payment state.
- Latest vehicle position as the sole location record.
- Automatic refund execution, client-supplied payment success, or operational tables acting as an accounting ledger.
- Hard-coded pricing, commission, tax, settlement, or refund percentages/thresholds.
- Production dependence on Supabase `auth.uid()` or `service_role`.
- Shared staging/production databases, roles, credentials, volumes, or data.
- Physical deletion of auditable business history or cross-database constraints.

## Domain Acceptance Matrix

All timestamps are UTC. Monetary values use exact numeric/decimal representation and ISO 4217 currency codes. Every state-changing command carries a correlation ID and idempotency key where applicable.

| # | Domain | Purpose and relationships | Critical invariants and authorization | Audit evidence | MVP / milestone / required tests |
|---:|---|---|---|---|---|
| 1 | Platform/account identity | One account identity may link to customer, vendor, driver, transport-company, or admin roles | Server-side RBAC; status gates protected actions; no role field alone grants transaction authority | Account creation/status history, actor, UTC, correlation ID | MVP; M2; identity, duplicate identity, session tests |
| 2 | Role memberships and transaction participation | Explicit account-role memberships and order/trip participation joins | Booking party is customer; capacity party is vendor; typed joins enforce valid parties | Role grant/revoke and participation history | MVP; M2/M3; cross-role denial tests |
| 3 | Customer profiles | Reusable booking profile linked to one account/legal party | Customer may book only authorized transactions; profile verification is distinct from account status | Profile changes and verification evidence | MVP; M2; ownership/RBAC tests |
| 4 | Vendor profiles | Vendor supply profile linked to account/legal party | Registration is not eligibility; approved vendor status required before offers/assignment | Registration, approval/rejection, acting admin | MVP; M2/M3; eligibility denial tests |
| 5 | Transport-company legal identity | Singular company identity with customer/vendor participation records | Company may be either party per transaction without duplicate legal master | Legal identity, membership, role participation | MVP; M2; dual-role/identity integrity tests |
| 6 | Driver profiles and association | Driver account linked to vendor/company association with validity dates | Driver eligibility, employment/association, licence/document status are independently auditable | Association and approval history | MVP; M2/M3; unauthorized driver/expired association tests |
| 7 | Vehicles and registration approval | Vehicle owned by a vendor/company, optionally associated with driver/model | Registration/vehicle eligibility requires admin approval; prevent assignment of inactive/unapproved vehicle | Owner, registration, approval, document references | MVP; M2/M3; duplicate registration and eligibility tests |
| 8 | Vehicle-model reference data | Small first-corridor approved catalog referenced by vehicles | Model data is reference/master data, versioned and reviewable; no large nationwide catalog by default | Source/version/approver | MVP minimal; M2; reference integrity tests |
| 9 | Admin account actions | Create, block, suspend, unblock customer/driver accounts | Authorized admin only; reason and full status change required; block rejects future protected requests, preserves history, and creates exception for active work | Affected account/type, admin, reason code/note, previous/new status, UTC, correlation ID | MVP; M2/M3; session rejection, unblock, active-trip exception tests |
| 10 | Locations, addresses, and order stops | Address/location entities or owned stop records linked to orders/trips | Stop authorization and validation; do not expose location beyond participating roles | Creator, source, precision/accuracy, UTC | MVP; M2/M3; cross-party access tests |
| 11 | Deterministic quotes | Versioned quote inputs/results link to booking/order | Same approved inputs/version produce reproducible result; prices only from approved deterministic policy, never LLM | Rule/version, inputs hash, output, actor/system, UTC | MVP; M3; reproducibility and expiry tests |
| 12 | Orders and transitions | Commercial booking links customer, stops, quote, participating vendor/trip | Validated transition service commits state and operational event atomically; no direct agent write | Old/new state, reason, actor, correlation, idempotency | MVP; M3; legal/illegal/replay transition tests |
| 13 | Dispatch offers | Offer links order/trip to eligible vendor/vehicle/driver candidate | Unique offer/idempotency key, expiry, one controlled acceptance; prevent simultaneous accepted conflicts | Candidate, score/input version, sent/responded/expired UTC | MVP; M3; expiry/double-accept tests |
| 14 | Trips | Physical execution is separate from commercial order; relates assigned capacity and stops | A trip cannot silently overwrite order history; active vehicle/driver concurrency controlled | Creation, assignment, milestone links | MVP; M3; re-dispatch/assignment integrity tests |
| 15 | Trip milestones | Persist pickup, transit, arrival, delivery, POD-pending, exception milestones | Authorized actor and valid sequence; manual milestones remain available | Milestone, actor, source, reason, UTC | MVP; M3/M4; manual fallback/sequence tests |
| 16 | Authorized location history | Immutable or tamper-evident history related to active trip, vehicle, driver | Browser update only for authorized active trip; require timestamp, actor, trip, accuracy and source; do not overwrite history | Point/accuracy/time, authorization decision, correlation | MVP; M3; active-trip/access/replay/stale-location tests |
| 17 | POD metadata and verification | Metadata/integrity reference links a stored binary to order/trip | Authorized upload, verification result, manual fallback; POD is operational evidence, not automatic financial proof | Uploader, content/integrity reference, verifier, result, UTC | MVP; M4; access/verification/POD-gate tests |
| 18 | Payment-gateway event evidence | Immutable signed gateway receipt related to an order/payment attempt | Verify signature/server source before projection; duplicate provider event is safe no-op | Provider event ID, signature result, received UTC, payload hash/reference | MVP; M4; invalid signature/duplicate/retry tests |
| 19 | Operational payment projection | User-visible operational state derived from verified evidence | Never trust client/agent assertion; distinguish operational evidence from Odoo accounting/reconciliation state | Source event/reference and transition history | MVP; M4; unauthorized projection tests |
| 20 | Financial requests to Odoo | Operational request for partner/draft invoice/draft vendor bill/read-only status | Idempotent request; no automatic post, settlement, reconciliation, or refund | Request type, amount/currency, requester, status, correlation/idempotency | MVP limited; M4; duplicate and no-auto-action tests |
| 21 | Odoo external references | Immutable association from local business entity/request to Odoo object | No cross-DB FK; Odoo remains authoritative; external ID/model/version scoped | Created/updated reference, sync state, source UTC | MVP limited; M4; reference-only/no-ledger tests |
| 22 | Settlement status projection | Operational view of settlement request/outcome, not ledger | No release/hold transition outside controlled financial workflow; Odoo controls accounting outcome | Source reference, status history, authorized actor | Deferred automatic settlement; M4; projection denial tests |
| 23 | Refund request/decision/execution | Separate request, manual approval, and execution evidence | Every refund requires manual approval; requester, approver, reason, decision time, amount/target binding, idempotency, execution proof; no automatic path | All request/approval/execution fields with UTC/correlation | MVP manual only; M4/M5; self-approval/duplicate/no-auto-refund tests |
| 24 | Operational exceptions/incidents | Human review for safety, block, payment, compliance, or trip incidents | Opening/resolution cannot erase primary evidence; blocked participant with active work creates immediate exception | Code, severity, owner, reason, status history, UTC | MVP; M3/M4; active-block/closure tests |
| 25 | Idempotency records | Command outcome registry scoped to business operation and environment/company | Same key/same request returns recorded outcome; same key/different payload rejects; lease/expiry/retry is explicit | Request hash, response reference/code, lifecycle, correlation | MVP; M3/M4; replay/conflict/timeout-after-success tests |
| 26 | Webhook receipts | Inbound provider inbox distinct from business outcome | Persist and verify receipt before processing; unique provider event ID; retries do not duplicate side effects | Provider, signature result, receipt hash, attempts, UTC | MVP; M4; invalid/duplicate/outage tests |
| 27 | Transactional outbox | Persist publishable operational event in same transaction as state change | State/event/outbox atomic; consumers idempotent; retry/dead-letter evidence required | Aggregate/version, destination, attempts, published UTC | MVP; M3/M4; crash/retry/duplicate tests |
| 28 | Immutable operational/audit events | Authoritative business event history separate from observability | Append-only/tamper-evident design; no deletion/rewrite for audit avoidance | Actor, action, entity, before/after reference, correlation, UTC | MVP; M2/M3; audit completeness tests |
| 29 | Service commitments/SLA evidence | Captures promised pickup/delivery/POD and breach evidence | Policy/version and evidence reference; no invented SLA or retention period | Commitment, threshold reference, outcome, UTC | MVP minimal if corridor requires; M3/M4; breach/audit tests |
| 30 | Notification-delivery evidence | Minimal record of attempted authorized status delivery | Delivery is not business truth; no WhatsApp production integration; retries idempotent | Channel, recipient reference, template/version, outcome, UTC | MVP minimal/deferred provider integration; M3/M4; privacy/retry tests |

## Security, Privacy, and Reliability Requirements

- Enforce server-side RBAC and database roles with least privilege; application authorization and database scope both enforce access.
- Phase one is one operational platform, but membership/company boundaries must permit future isolation without data reclassification. Staging and production always use distinct databases, roles, credentials, data, volumes, backups, and migration ledgers.
- Protect PII, document metadata, location, payment evidence, and account status. Encrypt in transit and use protected storage; separate secrets by service/environment; redact secrets, tokens, URLs, document content, and raw payment payloads from logs.
- Location collection is limited to active operational need; both parties see only their authorized trip/payment projections. SSE is a projection channel, never independent truth; commands persist before publication, reconnect uses authorized cursor/event ID, and missed events are recoverable from persisted history.
- Use UTC timestamps, exact money/currency types, correlation IDs, row locks or optimistic version boundaries where conflict risk exists, and explicit retry evidence.
- Vehicle double booking, offer expiry, quote expiry, concurrent transition, webhook replay, and duplicate external side effects must be prevented or safely detected.
- Define retention categories and legal/privacy review flags; do not invent statutory retention periods. Backups must be encrypted and protected; off-server copy, frequency, RPO/RTO, and restore-test schedule are proposed values requiring owner approval.
- Database operations must monitor connection usage, locks, storage, slow queries, health, and failed jobs without exposing sensitive details. VPS capacity, connection-pool limits, and extension availability are estimates to verify in approved staging.
- Use forward-fix as the default schema recovery strategy. Any rollback requires approved migration ledger state, a tested reversible/disposable staging procedure, and explicit owner/database approval.

## Environment and Deferred Scope

Required future environments are development, isolated staging, and production; none may share data or credentials. Future PostgreSQL version/extension compatibility, connection pooling, health checks, migration ledger, encrypted backups, off-server copy, restore testing, and proposed RPO/RTO require separate approval and evidence.

Deferred unless separately authorized: Paperclip runtime activation, full AI/RAG traces, analytics warehouse, ML pricing, triangle-route optimization, nationwide/multi-tenant scale, large vehicle catalog, automated settlement/refund, warehouse inventory, advanced fraud/OCR automation, WhatsApp production integration, and advanced notification providers.

## Future Schema/Migration Gate Checklist

Before any staging migration is authorized, the future implementation must demonstrate:

- [ ] A reviewed canonical manifest, checksum ledger, and migration-state ledger.
- [ ] Exact environment identity and proof that target is disposable staging, never production.
- [ ] Separate least-privilege roles/credentials and no cross-database foreign keys.
- [ ] All 30 domains above mapped to approved schema/API contracts with only MVP scope enabled.
- [ ] Server-side RBAC, transaction participation, account block/session rejection, and location/POD/payment authorization tests.
- [ ] Validated transition/outbox/idempotency behavior, including same-key/different-payload rejection and concurrency handling.
- [ ] Manual refund request/approval/execution evidence, with no automatic refund, settlement, Odoo posting, or reconciliation action.
- [ ] Odoo API/ORM-only boundary and reference-only accounting integration tests.
- [ ] Sanitized fixtures, backup/restore decision gates, audit redaction, and retention/legal review flags.
- [ ] Fresh migration up/down or approved forward-fix/disposable-environment evidence, health checks, rollback decision point, and owner approval.

## Completion Assessment

All 30 required domains, ownership boundaries, mandatory corrections, real-time behavior, security/privacy, reliability, operations, deferrals, and future migration gates are specified without unresolved business-model ambiguity. Implementation details such as exact schema names, indexes, retention values, backup frequency/RPO/RTO, and connection limits remain deliberately unselected for later reviewed work.
