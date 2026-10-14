# M1 Migration Inventory and MVP Reconciliation Plan

## Scope and Verdict

**Task:** `M1-MIGRATIONS`
**Baseline:** `5c7ce5281f4c85cb238fe6cc803d18d648889229`
**Method:** Static repository inspection only. No SQL, database client, container, Supabase CLI, Alembic, or credentials were used.

**Verdict:** Expanded static discovery found 37 executable or state-mutating artifacts and 12 migration-affecting configuration, startup, or ownership references. The repository now has a complete static inventory but not an executable production migration chain. `infra/supabase/migrations/` is the future repository migration home to reconcile, not an approved migration manifest. The non-numbered root `supabase/00000000000007_operational_completion.sql` is an addition/design draft and is not independently executable against the legacy initial schema. Its `orders(id)`, `drivers(id)`, and `vendors(id)` assumptions conflict with the numbered chain's `order_id`, `driver_profiles`, and absence of a `vendors` table. The Compose init mount instead targets the plain file `supabase/migrations`, not the numbered directory. No existing script is authorized to run.

## Inventory Method and Fields

Checksums are SHA-256. `Order` is filename order within its directory; it does not prove deployability. `Change` records static additive/destructive/ambiguous character. `Idempotency`, `Txn`, and `Rollback` describe only file text, not execution proof. `Authority` is the current documentation disposition. `MVP` is a planning disposition: retain, rewrite later, split, supersede, defer, or exclude. Runtime writers appear because they create or change database state and therefore constrain the eventual schema contract; ordinary database readers are excluded.

## Expanded Static Discovery Scope

The original SQL/ownership-only discovery counted 35 artifacts. The completeness correction attempted `rg --files` plus targeted content searches, but `rg` is not installed on this host and was not installed for this task. Equivalent static `find` and recursive `grep` searches examined all 152 repository files for migration frameworks, ORM schema creation, initdb/Compose initialization, seeds/fixtures, rollback/backup/restore utilities, Supabase configuration, PostgreSQL extensions, Odoo addons/manifests, Paperclip persistence, CI migration behavior, and database-writing runtime consumers.

No Alembic, Prisma, Drizzle, ORM `create_all`, automatic schema creation, migration-framework version directory, database backup/restore utility, Odoo addon manifest/model, or additional executable SQL artifact was found. The correction added four state-mutating runtime schema consumers and 12 migration-affecting references. It also establishes that `supabase/migrations` is a regular text file, while the actual numbered migration directory is `infra/supabase/migrations/`.

## Executable and State-Mutating Artifact Inventory

| Path | SHA-256 | Owner | Order / purpose / principal objects | Change / idempotency / transaction / rollback | Authority, conflicts, environment assumptions, MVP disposition |
|---|---|---|---|---|---|
| `infra/supabase/migrations/00000000000000_extensions.sql` | `cd5a68eb557153f66ef5149d175d5f638b2c289caf4c03e455a6b456bb97b5a0` | Zippy Operational DB | `00`; UUID, crypto, PostGIS, vector extensions | Additive `IF NOT EXISTS`; repeatable; no explicit transaction; no rollback | Requires PostgreSQL extension availability; retain concept, rewrite later for VPS capability check |
| `infra/supabase/migrations/00000000000001_initial_schema.sql` | `8a7a9a831f2a4d2dcd83d1aabcef12f6674ec1a62b7af2da28daeb87305b0774` | Zippy Operational DB | `01`; users, profiles, transport companies, vehicles/models/telemetry, orders/events, payments/transactions, admin actions, alerts, AI, notifications, webhooks, SOP | Mostly `IF NOT EXISTS`; no explicit transaction/rollback; data-model changes are additive but schema is legacy | Missing company scope, trips/offers/stops, refund approval evidence, and robust party integrity; `base_role`/`active_role` insufficient for transaction roles; rewrite later |
| `infra/supabase/migrations/00000000000002_functions_triggers.sql` | `a3ab0b1caed7f5b0670f63f52a1a6b8b86a04ff48282ed9c4dcd65eb81c2ba37` | Zippy Operational DB | `02`; state transition, commissions, payment transaction trigger, long-halt alert, assignment helper | `CREATE OR REPLACE`; destructive trigger replacement; no transaction; rollback not supplied | Fixed rates/fees and payment behavior conflict with D-11--D-24 finance scope; direct operational payment records risk ledger duplication; split/rewrite later |
| `infra/supabase/migrations/00000000000003_views.sql` | `57f0ed9f76e70ee3cc9988cf51efa21dc3a78c4ed3bb18305c3a782e970121c8` | Zippy Operational DB | `03`; dashboard, company dual-role, driver earnings views | `CREATE OR REPLACE`; repeatable; no transaction/rollback | Uses legacy role/commission model; advanced analytics not MVP; defer |
| `infra/supabase/migrations/00000000000004_auth_stub.sql` | `e7186cee587edf6d3f2cb03c1c78cc135cc94dc6d5dd051506239f1f1c8015e4` | Zippy Operational DB | `04`; `auth.uid()` and `auth.role()` compatibility functions | `IF NOT EXISTS`/`OR REPLACE`; repeatable; no transaction/rollback | Assumes simulated Supabase settings while D-11--D-24 select VPS PostgreSQL/no Supabase Cloud; rewrite later with approved authentication contract |
| `infra/supabase/migrations/00000000000005_rls_policies.sql` | `798e2bc93f935bf723b7897535c25effa1d91c7f274872839aa21b4744a62180` | Zippy Operational DB | `05`; RLS and `is_admin()` helper across legacy tables | Policy creation is not safely rerunnable; `SECURITY DEFINER`; no transaction/rollback | Assumes auth stub/service role and has no company isolation; conflict with guardrails and D-16/D-24; rewrite later |
| `infra/supabase/migrations/00000000000006_seed_data.sql` | `576ea02f49955617242ad5f23cbd3476847b2ab4a78af8e2d0b4be9e46ab2e14` | Zippy Operational DB | `06`; sample users, profiles, company, vehicles/models, SOP | `ON CONFLICT`; partial repeatability; no transaction/rollback | Contains production-like personal, contact, tax, license, and registration data plus legacy AI/mobile assumptions; exclude from MVP production, split into sanitized dev fixtures/master data |
| `infra/supabase/migrations/00000000000007_pricing_engine.sql` | `ac629d2defd34036778e74f1710a440ed87c380c1b84a5f6fb429f5aee64de76` | Zippy Operational DB | `07`; rate/toll bands, class inference, quotes, quote events | `IF NOT EXISTS`/`OR REPLACE`; seed rows idempotent; no transaction; textual drop rollback | Fixed tax/loading/rate values must not be silently adopted; deterministic pricing remains required but policy needs finance-approved source; split/rewrite later |
| `infra/supabase/migrations/00000000000008_matching_dispatch.sql` | `8c5e71b840bb133a3fd0da3aec2f473fb11d058765093cc64e84172441c94f7b` | Zippy Operational DB | `08`; nearby-driver matching function | `OR REPLACE`; no transaction; textual drop rollback | Uses owner/driver-only candidates and latest vehicle location, no trips/offers/company isolation; rewrite later |
| `infra/supabase/migrations/00000000000009_payment_rules.sql` | `f8fe9f26829feb455b848e31f0588188490a4b32a640fdf8656f81276bb8ada7` | Zippy Operational DB | `09`; payment-plan validation and payment-hold order guard | `OR REPLACE` plus trigger replacement; no transaction; textual drop rollback | Fixed payment-mode thresholds require finance policy validation; retain payment holds concept, rewrite later |
| `infra/supabase/migrations/00000000000010_agent_control_plane.sql` | `80371ba9b3919390e1791d91b58f2784dcac38a675ba522bcd37e5028803b17f` | Zippy Operational DB | `10`; agent registry/tasks, budgets, claim/retry functions | Mostly rerunnable; no explicit transaction; textual drop rollback | Full runtime agents are deferred by D-22/D-23; Paperclip is separate; defer/exclude from MVP operational migration sequence |
| `infra/supabase/migrations/00000000000011_odoo_pipeline_webhooks.sql` | `0361029d96ddf4485e1bd023333c7920851869913527e2a1b5e5ee3d06984c98` | Zippy Operational DB | `11`; Odoo mirror columns, agent enqueue, webhook sweep/revive, stale payments | Alter `IF NOT EXISTS`; functions replaceable; no transaction; textual rollback drops columns/functions | Odoo MVP permits references and draft/read-only status only, not a mirrored ledger; split webhook/idempotency from later Odoo bridge rewrite |
| `infra/supabase/migrations/00000000000012_pod_notification.sql` | `b153dbb355df6770fd8256b7978cf01f1d8cd49b02828a79c4914c667b5a52a2` | Zippy Operational DB | `12`; POD documents, notification queue, document agent, retry functions | Explicit `BEGIN`/`COMMIT`; mixed drop/create; textual partial rollback only | POD required; notifications/agent/service-role design not MVP authority; split POD/audit rewrite, defer notification/agent sections |
| `infra/supabase/migrations/00000000000012b_upsert_document.sql` | `e06a9777f4b1e72e3d51e2686f6646937b7dd669e3138b679b5ccf3f3d557aac` | Zippy Operational DB | `12b`; repeats document upsert and grants service role | Replaceable function; no transaction/rollback | Duplicate of function in `12`; service-role assumption conflicts with approved VPS auth design; supersede |
| `infra/supabase/migrations/00000000000012c_fix_mark_failed.sql` | `cee5613f0d5255e5bee21fe7833b28250576d95b410a3c9fe612f892bb6a2635` | Zippy Operational DB | `12c`; repeats notification failure function | Replaceable; no transaction/rollback | Patch to deferred notification subsystem; defer |
| `infra/supabase/migrations/00000000000013_vehicle_models_seed.sql` | `86159132946625b9ca49736791fcdbab186708d6f6ae89282d58407c769d71dc` | Zippy Operational DB | `13`; vehicle-model columns, type constraint replacement, 123-model seed/indexes | Mixed additive/destructive constraint replacement and `DELETE` before insert; no transaction/rollback | Large nationwide master data and source URLs exceed one-corridor MVP; split small approved model catalog later; defer remainder |
| `infra/supabase/stubs/auth_stub.sql` | `b3d4f89f345ecd98193b3148246419ad410baea6c0f55ae484c5a7fa2e3e0c7c` | Zippy Operational DB | Alternate auth compatibility stub with `auth.jwt()` | Repeatable; no transaction/rollback | Duplicates `04` but adds JWT stub; incompatible/unclear with approved VPS auth approach; supersede |
| `infra/supabase/verify_m1.sql` | `9ac6c75040a3da23490ce40b7322e80dba27537fd3cbad255a58a8542da7055f` | obsolete/unclear | Verification fixture for legacy schema, commission/state/RLS | Mutates, truncates, creates a login role/password; no enclosing transaction; cleanup partial | Test fixture only; unsafe on production and assumes legacy finance/auth; supersede with isolated MVP verification |
| `infra/supabase/verify_m2.sql` | `9ffe4bd2d4e322bbaf30c734a95aa7924ac4c9a62963eccff1a791a67068ac53` | obsolete/unclear | Legacy pricing/matching/payment-hold fixture | `BEGIN`/`ROLLBACK`; mutating but isolated if successful | Tests unapproved fixed price/payment policy; defer until rewritten |
| `infra/supabase/verify_m3.sql` | `a8935eebdf7ea296490f68e9ddec765f1a4040d5fe7a29d3f46fe146acb7c543` | obsolete/unclear | Agent queue/budget fixture | `BEGIN`/`ROLLBACK`; mutating fixture | Full agent runtime deferred; exclude from MVP verification |
| `infra/supabase/verify_m4.sql` | `f723f431627d55dcffc05f4843d81a8b97cd73d1dcf17ca6015978f7289080ec` | obsolete/unclear | Odoo mirror/webhook fixture | `BEGIN`/`ROLLBACK`; mutating fixture | Expects direct order Odoo mirrors beyond minimal generic references; rewrite later |
| `infra/supabase/verify_m5.sql` | `d8115d79cc15ba2494d25fdf0ed75fec6eb1d18059af81aa68ffc280a7283790` | obsolete/unclear | POD/notification/agent fixture | `BEGIN`/`ROLLBACK`; mutating fixture | POD can return in MVP, notification/agent/service-role assumptions deferred; split/rewrite later |
| `infra/supabase/verify_m6.sql` | `8d3d090a4808f250cadd8744f14413e42a83e2b262bad93509c1a88ecf2a88d3` | obsolete/unclear | Legacy lifecycle, quote, assignment fixture | `BEGIN`/`ROLLBACK`; mutating fixture | Tests fixed payment/commission and direct `payment_settled` lifecycle; rewrite later |
| `paperclip/01_governance_schema.sql` | `e94730c47eda82f4f69f54aa8c674ecc8cec1b7b7a9beadf5b98eb706b862048` | Paperclip DB | Independent governance schema: tenants, agents, policies, tasks, proposals, locks, approvals, grants, attempts, audit/outbox | Mostly create-only, not generally rerunnable; no explicit transaction/rollback | Correctly separates DB ownership/no cross-DB FKs; runtime deferred by D-22; defer intact design, never mix into Zippy DB |
| `supabase/00000000000007_operational_completion.sql` | `4a86725937075088c6df9cb6556b1dcf802cbd241d93280d833e67491953a07f` | obsolete/unclear | Non-numbered addition draft: companies, trips, offers, exceptions, idempotency, webhook/outbox, references, financial requests, gateway/POD/events | Mostly `IF NOT EXISTS`; no transaction/rollback; comments say adapt before applying | Not independently executable: incompatible table/key names and overlaps legacy webhook schema; valuable domain blueprint; split/rewrite later |
| `supabase/seed.sql` | `1d699aba3f13bf3b4935c4f8545078cd45927463b67bc9aefbf840b19d8798ef` | obsolete/unclear | Root development seed: users/profiles/company/vehicle models/vehicles/SOP | `ON CONFLICT`; partial repeatability; no transaction/rollback | Near-duplicate but not byte-identical to `06`; production-like data and old AI/mobile/payment claims; exclude from MVP production, split sanitized fixtures |
| `supabase/test_full_integration.sql` | `58367435ee7a101a62ef9219670127e38eb0aa1d909f2c2b0a690655c6d002ee` | obsolete/unclear | Full test fixture for completion-schema tenancy/idempotency/governance/outbox | Mutates/deletes and has no enclosing transaction; assumes incompatible `id` keys, `draft` order state, and co-located Paperclip simulation | Cannot validate the numbered chain or production; excludes actual Paperclip DB boundary; supersede |
| `supabase/verify_m1.sql` | `9ac6c75040a3da23490ce40b7322e80dba27537fd3cbad255a58a8542da7055f` | obsolete/unclear | Byte-identical duplicate of `infra/supabase/verify_m1.sql` | Same mutation/transaction/rollback profile as infra copy | Duplicate path creates execution ambiguity; supersede duplicate |
| `supabase/verify_m2.sql` | `9ffe4bd2d4e322bbaf30c734a95aa7924ac4c9a62963eccff1a791a67068ac53` | obsolete/unclear | Byte-identical duplicate of `infra/supabase/verify_m2.sql` | Same mutation/transaction/rollback profile as infra copy | Duplicate path creates execution ambiguity; supersede duplicate |
| `supabase/verify_m3.sql` | `a8935eebdf7ea296490f68e9ddec765f1a4040d5fe7a29d3f46fe146acb7c543` | obsolete/unclear | Byte-identical duplicate of `infra/supabase/verify_m3.sql` | Same mutation/transaction/rollback profile as infra copy | Duplicate path creates execution ambiguity; supersede duplicate |
| `supabase/verify_m4.sql` | `f723f431627d55dcffc05f4843d81a8b97cd73d1dcf17ca6015978f7289080ec` | obsolete/unclear | Byte-identical duplicate of `infra/supabase/verify_m4.sql` | Same mutation/transaction/rollback profile as infra copy | Duplicate path creates execution ambiguity; supersede duplicate |
| `supabase/verify_m5.sql` | `d8115d79cc15ba2494d25fdf0ed75fec6eb1d18059af81aa68ffc280a7283790` | obsolete/unclear | Byte-identical duplicate of `infra/supabase/verify_m5.sql` | Same mutation/transaction/rollback profile as infra copy | Duplicate path creates execution ambiguity; supersede duplicate |
| `supabase/verify_m6.sql` | `8d3d090a4808f250cadd8744f14413e42a83e2b262bad93509c1a88ecf2a88d3` | obsolete/unclear | Byte-identical duplicate of `infra/supabase/verify_m6.sql` | Same mutation/transaction/rollback profile as infra copy | Duplicate path creates execution ambiguity; supersede duplicate |
| `api/main.py` | `5858569983b3b7ebe2656ee13a7424a870b30b1d31045580469835d919006b5a` | Zippy Operational DB | Runtime order writer; posts to Supabase REST `orders` and expects `id`/legacy fields | State-mutating runtime code; idempotency delegated to separate store; no migration transaction/rollback | Schema consumer conflicts with approved VPS PostgreSQL direction and legacy order shape; rewrite later |
| `api/idempotency.py` | `005fc4e7be440a157a0b6b2b7df0be8d5dc993cba54fb4cf7f1d5c18434f9500` | Zippy Operational DB | Runtime idempotency claim/complete/fail writer using `webhook_events` via Supabase REST | State-mutating; `INSERT ... ON CONFLICT` intent; fail-open on client error; no migration transaction/rollback | Uses completion-schema-like `id`/`status` fields incompatible with legacy webhook schema; rewrite later |
| `apps/portal/src/app/api/webhooks/razorpay/route.ts` | `d2fc4312b5bd9329a929f179e8abaf493026cf7fc1e1f7ff9408f9a52932d3a1` | Zippy Operational DB | Runtime webhook insert and agent-task RPC enqueue | State-mutating, duplicate handling by unique error; no migration transaction/rollback | Depends on legacy Supabase/service role and deferred agent queue; retain webhook concept, rewrite later |
| `workers/src/zippy_workers/kernel.py` | `2a643a5e7b50f7c92740b2ef3f8531e034aa873bd39f9ff528f1380fcf0b071d` | Zippy Operational DB | Runtime RPC/table writer for tasks, transitions, quotes, Odoo refs, POD, notifications and agent status | State-mutating runtime code; RPC idempotency varies; no migration transaction/rollback | Full runtime agent path is deferred and mixes legacy Supabase assumptions with postponed Paperclip; defer |

## Migration-Affecting Configuration, Startup, and Ownership References

These references are not executable migrations or state-mutating fixtures. They change how migrations could be initialized, validated, or owned, or define constraints for their future design.

| Path | Relevance | Risk | Relationship to proposed manifest | Disposition |
|---|---|---|---|---|
| `docker-compose.yml` | PostgreSQL service mounts `./supabase/migrations` at `/docker-entrypoint-initdb.d`; also configures Odoo/addon mount and service environment names | `supabase/migrations` is a UTF-8 file, not the numbered directory, so initialization source is invalid/ambiguous; published database port and legacy service credentials are not approved MVP configuration | Must be replaced by a later approved staging route and canonical migration source | supersede |
| `infra/docker/Dockerfile.db` | Builds PostGIS 16 image and installs PostgreSQL 16 pgvector package | VPS package/extension availability unverified; image does not establish migration order | Future prerequisite capability check for approved VPS PostgreSQL | rewrite later |
| `scripts/setup.sh` | Creates `.env` from template and validates a nonexistent `infra/docker/docker-compose.yml` | Path does not match root Compose; it does not apply migrations but could mislead setup | Must not be used as migration/init evidence | supersede |
| `scripts/setup.bat` | Windows analogue of setup script and same nonexistent Compose reference | Same path ambiguity and no migration controls | Must not be used as migration/init evidence | supersede |
| `.github/workflows/ci.yml` | Runs root Compose configuration validation and API/unit checks with test environment names | Does not apply migrations or create a database; test settings are not deployment evidence | Future CI should validate only the approved manifest in disposable staging | rewrite later |
| `.github/workflows/deploy-hostinger.yml` | Validates missing `docker-compose.production.yml` before a ServerAvatar deployment | Cannot currently validate or deploy a canonical database route; production workflow is outside current authorization | Staging-route design must resolve before any deployment work | defer |
| `supabase/migrations` | Plain UTF-8 migration README-like file; Compose attempts to mount it as initdb directory | Direct init mount target is not a directory and describes an outdated/inconsistent sequence | Explicitly excluded from future executable migration source | supersede |
| `infra/supabase/migrations/README.md` | Documents numbered chain and manual Docker/Supabase apply commands | Lists obsolete `07` completion placement and stale table-count guidance | Replace only after a future canonical manifest is approved | supersede |
| `.github/copilot-instructions.md` | Names SQL verification commands and legacy `supabase/migrations` location | Conflicts with actual numbered directory and approved no-execution scope | Supporting guardrail to reconcile after owner approval | rewrite later |
| `docs/PRD-database.md` | Documents legacy schema/migration ordering and verification assertions | Treats legacy schema as source of truth and relies on Supabase terminology | Historical input to future MVP database requirements, not a migration manifest | rewrite later |
| `odoo/01_ownership_relationships.md` | Defines Odoo ORM/API-only boundary and minimal external reference design | No Odoo migration exists; direct SQL is explicitly prohibited | Retain as ownership constraint for minimal Odoo API boundary | retain |
| `infra/odoo/README.md` | Placeholder for future Odoo config, addon and seed directories; addons currently contain only `.gitkeep` | No addon manifest/model/migration or seed is present | No MVP Odoo schema artifact is ready; defer until separate approval | defer |

## Duplicate Verification Paths

The duplicate sets are exactly:

| Root path | Byte-identical infrastructure counterpart |
|---|---|
| `supabase/verify_m1.sql` | `infra/supabase/verify_m1.sql` |
| `supabase/verify_m2.sql` | `infra/supabase/verify_m2.sql` |
| `supabase/verify_m3.sql` | `infra/supabase/verify_m3.sql` |
| `supabase/verify_m4.sql` | `infra/supabase/verify_m4.sql` |
| `supabase/verify_m5.sql` | `infra/supabase/verify_m5.sql` |
| `supabase/verify_m6.sql` | `infra/supabase/verify_m6.sql` |

The root copies are not counterparts "under `supabase`"; their sole verified counterparts are under `infra/supabase/`. Both sets are legacy verification fixtures and neither is an approved MVP verification source.

## Required Conflict Analysis

1. **Initial schema versus operational completion:** the legacy initial schema is a separate `order_id`/profile-table design; completion assumes `orders(id)`, `drivers`, and `vendors`, so it is addition/design material, not migration `07` in that chain.
2. **Company isolation:** completion says add `company_id` to every tenant-owned object, but does not apply it. Initial schema and RLS cannot demonstrate future isolation.
3. **Identity and roles:** current `base_role`/`active_role`, customer profiles, drivers, and transport companies do not safely express transaction-specific customer/vendor roles or a singular transport-company legal identity. Polymorphic party links require application validation or a safer relational design.
4. **Operational workflow:** legacy orders lack first-class stops/trips/offers. Completion adds trips/offers but uses incompatible names. Latest vehicle location is not sufficient; authorized location history is required.
5. **Finance/refunds:** `payments` and `payment_transactions` risk a competing Odoo ledger. Completion's `financial_requests`, gateway evidence, and external references are the appropriate operational concepts but need rewrite. Neither family provides requester, manual approver, reason, decision time, and execution evidence for every refund.
6. **Governance/Odoo:** Paperclip is correctly separate but must never be mixed into operational tables. No cross-database foreign keys were found in the Paperclip/Odoo blueprints. Odoo blueprint forbids direct core SQL; no Odoo-core migration exists. Legacy full-integration fixture only simulates Paperclip in Zippy and is invalid as boundary evidence.
7. **Repeatability and rollback:** no migration ledger/version table exists. The numbered files rely on lexical filename order; most lack enclosing transactions and offer only comments with destructive `DROP` rollback. `13` replaces constraints and deletes seeded models. Verification M1 and full integration fixtures mutate state/roles outside a full transaction.
8. **Extensions and RLS:** PostGIS, `vector`, `uuid-ossp`, and `pgcrypto` are required by legacy files, but VPS availability is unproved. Auth stubs/service-role RLS reflect Supabase assumptions and conflict with the approved VPS PostgreSQL direction until a replacement authentication/RBAC contract is designed.
9. **MVP conflict with D-11--D-24:** fixed price/commission/tax/payment-policy SQL, active agents, AI/SOP machinery, notification integrations, broad model catalog, advanced analytics, direct Odoo mirror assumptions, automatic settlement lifecycle, and native/mobile references must not be adopted as MVP behavior. Manual refunds, admin block audit, deterministic state/pricing, isolated WhatsApp, sandbox/manual payment evidence, and no LLM core remain controlling.

## Proposed Future MVP Manifest (Not Created and Not Executable)

This is a logical sequence for later owner-approved implementation. It does not select an existing SQL file for execution or decide destructive migration behavior.

### Zippy Operational DB

1. Prerequisite capability check: approved VPS PostgreSQL version, required extensions, migration ledger, and transaction/rollback policy.
2. Accounts and server-side RBAC: customer, vendor, driver, transport-company, and admin identities; account creation; block/suspension/unblock audit; session rejection/revocation contract.
3. Party and company model: single legal transport-company identity, transaction-specific booking/provider roles, phase-one single operational platform, and future isolation-compatible company/membership boundaries.
4. Vehicle registration: vehicle models, owner/company relationship, driver assignment, documents, and admin eligibility approval.
5. Orders and stops: idempotent booking request, pickup/delivery stops, deterministic quote reference, validated transition service, and operational audit events.
6. Trips, assignments, and dispatch offers: first-class physical execution separate from commercial order, assignment acceptance, manual exception path, and no direct status mutation.
7. Authorized location history and milestones: consented periodic browser updates for active trips, access controls for both transaction parties, manual milestones, stale/unavailable-location exceptions, and retention policy.
8. POD: document metadata, verification result, manual fallback, and no automatic financial consequence.
9. Verified payment evidence: gateway receipt/webhook inbox with signature verification, manual evidence option, payment holds, and client/agent assertions excluded as proof.
10. Financial requests and Odoo references: operational request state, idempotency, immutable external references, partner sync, drafts, and read-only status sync; never Odoo ledger mirrors, posting, settlement, reconciliation, or refunds.
11. Manual refund evidence: requester, authorized approver, reason, decision time, execution evidence, target/amount binding, and idempotency; no automatic refund path.
12. Transactional outbox, webhook receipts, operational exceptions, and audit events.

### Paperclip DB — Deferred

Preserve `paperclip/01_governance_schema.sql` as the design baseline. Deploy only when consequential runtime agents are approved. Then apply its isolated tenants/policies/proposals/HITL/grants/attempts/audit model after compatibility review. Do not place Paperclip tables in Zippy PostgreSQL.

### Odoo Custom Extension/API Boundary — Minimal

Do not create Odoo core SQL migrations. Use supported API/ORM only for partner synchronization, draft customer invoice, draft vendor bill, and read-only accounting/payment-status synchronization. Any Odoo custom fields/module must be separately approved and must carry immutable external IDs/idempotency without copying the ledger.

### Seeds and Master Data

Create future sanitized, clearly non-production fixtures separately from MVP master data. Start with the small, owner-approved vehicle model catalog required for the first corridor. Do not load current contact, tax, license, vehicle-registration, or wide OEM catalog data into production.

### Verification and Rollback

Use one canonical future verification location, disposable staging databases, migration-ledger recording, transaction-aware failure tests, explicit approved rollback procedures, tenant/role denial tests, idempotency/replay tests, admin block tests, location authorization tests, manual refund tests, and Odoo boundary tests. Never execute legacy fixtures against production.

## Deferred or Excluded Schema Areas

- Paperclip runtime tables, agent registry/tasks, budgets, and Langfuse/Honcho integration: deferred.
- AI/RAG/SOP embedding vectors and model/provider records: deferred.
- Notification provider queues, WhatsApp integration, and external messaging automation: deferred.
- Fixed rate, commission, tax, toll, and payment threshold seed policies: rewrite later only after finance policy is separately ratified.
- Advanced dashboards, revenue/earnings views, nationwide 123-model catalog, dynamic pricing, route optimization, control tower, and advanced analytics: deferred.
- Root duplicate verification scripts and non-executable full integration fixture: superseded as future test sources.

## Completion Assessment

All 37 executable or state-mutating artifacts have an exact path, checksum, owner, static purpose, ordering/version, object/change profile, idempotency/transaction/rollback assessment, authority/conflict/environment note, and MVP disposition. All 12 migration-affecting configuration, startup, and ownership references are separately classified. The existing SQL is not a safe executable chain; this inventory resolves its ownership classification sufficiently to propose a non-executable MVP manifest. Any actual migration source, SQL rewrite, database creation, or migration execution remains blocked pending the later M1 requirements, owner gate, and M2 authorization.
