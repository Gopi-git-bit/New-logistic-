# M2 Database Implementation Report

## Scope and Result

**Task:** `M2-DATABASES`
**Baseline:** `e2b0b5ecf0d0ee35ce3b82d896b265aca787697c`
**Execution date:** 2026-09-09
**Result:** COMPLETE in an isolated disposable PostgreSQL test environment; not deployed.

This task created one canonical Zippy operational migration chain, a checksummed manifest, a dependency-free `psql` runner, synthetic database assertions, and disposable rollback/reapply evidence. It did not modify or access a production database, deploy an application, activate payments, access Odoo, deploy Paperclip or n8n, alter DNS/firewall/Apache/system services, or expose a database port.

## Canonical Migration Chain

The sole canonical directory is `db/zippy/migrations/`. The runner applies only the explicit order in `manifest.tsv`; filename glob order is not used.

| Order | Forward migration | Down migration | Rollback class | Purpose |
|---:|---|---|---|---|
| 1 | `0001_foundation.up.sql` | `0001_foundation.down.sql` | `disposable_only` | `pgcrypto`, schema ledger, deny-by-default privileges, platform/account/RBAC/party/admin-control foundation |
| 2 | `0002_operations.up.sql` | `0002_operations.down.sql` | `disposable_only` | Vehicles/documents, quotes, orders/stops/participation, offers, trips/assignments/milestones, location history, POD metadata |
| 3 | `0003_evidence_and_reliability.up.sql` | `0003_evidence_and_reliability.down.sql` | `disposable_only` | Webhook/payment evidence, financial requests/references, manual refunds, idempotency, tasks, inbox/outbox/DLQ, audit, exceptions, SLA and notification evidence |
| 4 | `0004_controls.up.sql` | `0004_controls.down.sql` | `disposable_only` | Validated transitions, account controls, eligibility/participation guards, payment/refund guards, append-only history, row-locked claims, stale leases, RLS and grants |

The manifest records SHA-256 checksums for every up/down file. The runner rejects checksum drift, non-manifest SQL, unordered versions, protected/unsafe database names, missing disposable authorization, marker mismatch, unexpected schemas/databases, and unconfirmed down execution. `zippy.schema_migrations` records the applied version and forward checksum.

Cluster-global roles are outside the migration chain. `roles.sh bootstrap` creates the three NOLOGIN group roles and three disposable LOGIN members only after validating the exact database, server marker, container, volume and image identity. Ordinary `migrate.sh down` removes database-local objects only and preserves roles. Separate `roles.sh teardown` requires an additional exact database/container/volume confirmation, verifies the expected role set and zero dependencies, and drops only the six approved roles without `CASCADE`.

Production and staging recovery default to forward-fix or approved restore. Destructive schema down and role teardown are disposable-test operations only.

## Legacy Exclusions

All 37 executable/state-mutating artifacts and 12 migration-affecting references inventoried in M1 remain preserved and unchanged. The canonical manifest excludes:

- every file under `infra/supabase/migrations/` and `infra/supabase/stubs/`;
- both legacy `verify_m1.sql` through `verify_m6.sql` families;
- root `supabase/00000000000007_operational_completion.sql`, `seed.sql`, `test_full_integration.sql`, and the plain `supabase/migrations` file;
- `paperclip/01_governance_schema.sql` because Paperclip owns a separate deferred database;
- existing Compose initialization, legacy runtime writers, and CI/deployment workflows.

They are excluded because they contain incompatible schema families, Supabase auth/service-role assumptions, hard-coded financial policy, production-like seed data, deferred agent/notification scope, Odoo mirror risk, duplicate fixtures, incomplete rollback, or ambiguous initialization. Final legacy-path Git diff count was zero.

## Thirty-Domain Mapping

| # | Approved domain | Canonical implementation |
|---:|---|---|
| 1 | Accounts/auth identities | `platforms`, `accounts`; external subjects only, no Supabase auth dependency |
| 2 | Roles/participation | `roles`, `account_role_memberships`, `transaction_participants` |
| 3 | Customer profiles | `customer_profiles` |
| 4 | Vendor profiles | `vendor_profiles` |
| 5 | Transport-company identity | `legal_entities`, `company_memberships`; reusable transaction profiles |
| 6 | Drivers/associations | `driver_profiles`, `driver_associations` |
| 7 | Vehicles/approval | `vehicles`, `vehicle_documents`; approval and eligibility checks |
| 8 | Vehicle models | `vehicle_models`; version/source/approver fields, no production catalog seed |
| 9 | Admin account actions | `admin_account_actions`, `set_account_status()`; active-trip exception |
| 10 | Addresses/order stops | `order_stops` with source, precision and ordered stop constraints |
| 11 | Deterministic quotes | append-only `quotes` with policy version/input hash; no rates in SQL |
| 12 | Orders/transitions | `orders`, `order_transition_rules`, `order_state_transitions`, `transition_order()` |
| 13 | Dispatch offers | `dispatch_offers`; idempotency, expiry and one accepted offer |
| 14 | Trips | `trips`, `trip_assignments`; active vehicle/driver uniqueness |
| 15 | Trip milestones | `trip_milestones`; ordered authorized evidence |
| 16 | Location history | append-only `trip_location_history`; active-assignment authorization guard |
| 17 | POD | `pod_documents`; object key, size, type, checksum and verification evidence |
| 18 | Gateway evidence | `webhook_receipts`, append-only `gateway_events` |
| 19 | Payment projection | `payment_projections`; verified status requires signed gateway evidence |
| 20 | Financial requests | `financial_requests`; limited request types, exact money/currency and idempotency |
| 21 | External references | `external_references`; immutable identity, no cross-database foreign key |
| 22 | Settlement projection | `settlement_projections`; external evidence required for confirmation |
| 23 | Manual refunds | `refund_requests`, `refund_decisions`, `refund_executions`; self-approval rejected |
| 24 | Operational exceptions | `operational_exceptions`, `exception_status_history` |
| 25 | Idempotency | `idempotency_records`; scope/key uniqueness and request-hash conflict detection |
| 26 | Webhook receipts | unique provider event receipts with signature/result evidence |
| 27 | Transactional outbox | `event_outbox`; aggregate-version and destination idempotency |
| 28 | Operational/audit events | append-only `operational_events`, `audit_events` |
| 29 | SLA evidence | `service_commitments`, `sla_evidence` with policy/evidence references |
| 30 | Notification evidence | `notification_attempts`; delivery state cannot mutate business truth |

## Database Controls

- 48 Zippy tables, primary/foreign keys, scoped uniqueness, checks, UTC timestamps and correlation identifiers were created.
- Exact money uses `numeric(18,2)` with ISO-style three-letter currency checks.
- Platform-scoped composite foreign keys prevent cross-platform relationships.
- 45 tenant-scoped tables have enabled and forced RLS plus a platform policy. Location history also has a restrictive participant policy.
- The original RLS assertion ran from the table-owning `zippy_m2_runner` session using `SET ROLE`; it was insufficient owner-independent evidence and is superseded.
- Corrected assertions ran as independent `zippy_m2_app_login` and `zippy_m2_readonly_login` sessions. Each LOGIN is non-superuser, non-owner, `NOBYPASSRLS`, and has exactly one NOLOGIN group membership.
- All Zippy tables are owned by `zippy_migrator`. Forced RLS was also proved against that owner role, preventing table ownership from representing runtime access.
- Application DDL, protected status-column updates, cross-platform reads/inserts/updates/deletes, and non-allowlisted functions were denied. Read-only insert/update/delete and mutating-function execution were denied.
- PUBLIC has no Zippy schema, table, sequence or function privileges. Migrator default privileges revoke PUBLIC mutation, sequence and function access.
- Order status direct updates are trigger-protected; `transition_order()` atomically writes transition, operational-event, outbox and idempotency evidence.
- Append-only triggers protect quotes, transitions, locations, gateway events, refund decisions/executions, admin actions and operational/audit events.
- `claim_durable_tasks()` uses `FOR UPDATE SKIP LOCKED`; two concurrent clients claimed two distinct tasks. Expired processing leases are reclaimable.
- Retry count, next-attempt, lease owner/expiry, max attempts and terminal dead-letter evidence are constrained and tested.

RLS behavior is proven for the database role/context contract in this disposable database. Binding authenticated application identities to platform context remains an M3 API/auth responsibility; no production tenant-isolation claim is made.

## Table Security Classification

All 48 tables are classified exactly once. The 45 tables in the first three categories all have `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and a tested platform policy.

| Classification | Count | Tables |
|---|---:|---|
| RLS REQUIRED | 28 | `platforms`, `accounts`, `account_role_memberships`, `legal_entities`, `customer_profiles`, `vendor_profiles`, `company_memberships`, `driver_profiles`, `driver_associations`, `vehicle_models`, `vehicles`, `vehicle_documents`, `orders`, `order_stops`, `transaction_participants`, `dispatch_offers`, `trips`, `trip_assignments`, `trip_milestones`, `pod_documents`, `payment_projections`, `financial_requests`, `external_references`, `settlement_projections`, `refund_requests`, `operational_exceptions`, `service_commitments`, `sla_evidence` |
| INTERNAL WORKER | 7 | `webhook_receipts`, `idempotency_records`, `durable_tasks`, `event_outbox`, `event_inbox`, `dead_letter_records`, `notification_attempts` |
| IMMUTABLE AUDIT | 10 | `admin_account_actions`, `quotes`, `trip_location_history`, `gateway_events`, `refund_decisions`, `refund_executions`, `audit_events`, `exception_status_history`, `order_state_transitions`, `operational_events` |
| MIGRATION METADATA | 1 | `schema_migrations` |
| JUSTIFIED EXEMPT | 2 | `roles`, `order_transition_rules` |

## Isolated Test Environment

| Property | Executed evidence |
|---|---|
| Engine | PostgreSQL `16.15 (Debian 16.15-1.pgdg13+2)` |
| Immutable image | `postgres@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94`; local image ID is the same SHA-256 |
| Database identity | Unique `zippy_m2_disposable_<timestamp>_<random>` name per run |
| Container/volume | Unique generated M2 names verified against database markers; both removed after each run |
| Network | Docker `--network none`; no published port; no host PostgreSQL listener after cleanup |
| Credentials | Random ephemeral test password generated at runtime; not displayed, recorded or committed |
| Repository mount | Read-only inside the container |
| External reachability | No container network; could not reach Odoo, Paperclip or external services |
| Data | Synthetic `.invalid` identities and synthetic order/location/POD/payment references only |
| Extensions | `pgcrypto` only; PostGIS and AI/vector extensions not required by this deterministic M2 model |

## Commands and Results

The executed workflow used Docker only for the disposable PostgreSQL instance and `psql`/`pgbench` inside it:

1. Verified exact Git baseline/tracker state and no production database environment variables.
2. Started the already-local immutable image with `--network none`, no published port, unique container/volume/database names, a read-only repository mount and generated ephemeral credentials.
3. Created database-scoped server/container/volume/image markers and ran guarded cluster-role bootstrap.
4. Ran the canonical migration chain as `zippy_m2_migration_login` with only `zippy_migrator` membership.
5. Ran behavior and catalog assertions as `zippy_m2_app_login`, read-only assertions as `zippy_m2_readonly_login`, and owner-only account-control assertions as `zippy_migrator`.
6. Ran two-client `pgbench` claims as `zippy_m2_app_login` and the expanded runner rejection suite.
7. Ran confirmed ordinary schema down, proved zero database-local Zippy schema/extension objects while roles remained, reapplied, and repeated all assertions.
8. Ran separately confirmed role teardown, removed only the generated container and volume, and verified no PostgreSQL listener remained.

| Test area | Final result |
|---|---|
| Fresh canonical up and four-row ledger | PASS |
| Manifest order/checksums and unexpected SQL rejection | PASS |
| Immutable image, network `none`, no ports, read-only repository mount and exact markers | PASS |
| All 48 tables classified: 28 RLS required, 7 internal worker, 10 immutable audit, 1 migration metadata, 2 justified exempt | PASS |
| Enabled and forced RLS plus platform policy on all 45 tenant-scoped tables | PASS |
| Restricted application/read-only LOGIN identity, ownership and exact membership | PASS |
| DDL, PUBLIC, default, sequence, table, column and function privilege boundaries | PASS |
| No cross-database FK / no Odoo or Paperclip core tables | PASS |
| Account/role/platform and transaction-participation controls | PASS |
| Admin block/unblock audit and active-trip exception | PASS |
| Order transition/direct-update/replay constraints | PASS |
| Manual refund approval, self-approval denial and execution binding | PASS |
| Signed payment-evidence boundary and duplicate webhook rejection | PASS |
| Idempotency conflict, inbox/outbox uniqueness and atomic transition evidence | PASS |
| Two-client task claiming, stale lease, retry and terminal dead-letter | PASS |
| Location persistence/authorization, POD checksum and append-only audit | PASS |
| Same-platform behavior, cross-platform denial and participant-scoped location access | PASS |
| Ordinary down to zero database-local objects with roles preserved | PASS |
| Reapply and complete repeated assertions | PASS |
| Separately guarded role teardown without `CASCADE` | PASS |
| Exact disposable resource cleanup and zero PostgreSQL listeners | PASS |
| PostgreSQL 15 compatibility | NOT RUN; PostgreSQL 16.15 is within the approved 15+ target |
| Production identity-to-platform binding | NOT RUN; belongs to M3 API/auth implementation |

During implementation, executable tests exposed and led to correction of optional-null uniqueness, an ambiguous PL/pgSQL parameter, trigger/function down ordering, and stale processing-lease recovery. One `pgbench -q` invocation was invalid and performed no claims; the same unchanged concurrency test passed with valid options.

The security correction retained these additional failed attempts as evidence:

1. The original RLS check used `zippy_m2_runner`, the object-creating database owner, then `SET ROLE zippy_app`; it did not prove independent runtime identity isolation.
2. Two harness attempts failed before migration because the first probe observed the image's temporary initialization server and then because the marker-setting `docker exec` lacked stdin attachment.
3. Guards correctly stopped marker mismatch and initially rejected built-in `template1` until the inventory rule was narrowed to allow only PostgreSQL built-ins plus the exact disposable target.
4. Restricted execution exposed and corrected a fixture tuple defect, an RLS-versus-foreign-key test ordering issue, and an overloaded sequence-privilege assertion.
5. A complete run reached role teardown and exited `1` because its expected-role list omitted the disposable owner `zippy_m2_runner`.
6. The next complete run exited `1` because PostgreSQL's `pg_shdepend.deptype` internal `"char"` required an explicit `::text` cast for diagnostic concatenation.
7. The definitive rerun after these corrections exited `0` with no PostgreSQL error markers. No failed result is represented as passing evidence.

## Security and Data Impact

No production credential, production database, real personal/location/POD/payment data, database dump, public port, Odoo table/API, Paperclip table/runtime, n8n workflow, live payment, automatic refund/settlement, accounting post, host package, service, DNS, firewall or Apache configuration was accessed or changed. No hard-coded price, tax, commission, refund or settlement percentage exists in the canonical chain.

The only host-persistent runtime artifact used was the already-local immutable PostgreSQL image identified above; no image was pulled. Every disposable container and data volume was removed. Repository changes are limited to `db/zippy/` and the three authorized M2 documentation/evidence paths.

## Remaining Gaps

- Production deployment, production database creation/mutation and production readiness remain unauthorized and unverified.
- Application authentication must bind trusted platform/account context before any deployment; M2 proves the database policy behavior, not a production auth flow.
- API integration with the canonical schema, including application-facing database identities and transition calls, belongs to M3.
- PostGIS was not required or tested; future route/geospatial queries must justify and test it before introduction.
- Odoo API/ORM integration, live/sandbox payment integration, Paperclip, n8n, backup/restore, staging routing and all later milestone evidence remain outside M2.

## Tracker Handoff

`M2-DATABASES` meets its corrected fresh-database, restricted-identity RLS, role/privilege, migration, rollback/reapply, relational-invariant, concurrency, role-teardown and cleanup evidence requirements and may be marked `COMPLETE`. The dependency-correct next task is `M3-CORE`, which may become the sole `IN_PROGRESS` task but is explicitly not begun by this handoff.