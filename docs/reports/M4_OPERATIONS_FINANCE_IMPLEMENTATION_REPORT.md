# M4 Operations-Finance Implementation Report

## Scope and Result

**Task:** `M4-OPERATIONS-FINANCE`
**Baseline:** `2c5225b5edfcbac1739bb829c937e41bceee0eca`
**Execution date:** 2026-09-11 (initial implementation); 2026-09-23 (payment-contract and final-proof correction); **2026-09-23 (dispatch implementation, secret-redaction fix, and payment-intent privilege correction, this update)**
**Approval:** D-26 (owner-approved 2026-09-11, recorded verbatim in `docs/DECISIONS.md`)
**Result:** IMPLEMENTED and proven in network-isolated disposable test environments; **not marked COMPLETE** — completion requires a separate acceptance audit. Not deployed.

> **2026-09-23 correction notice (payment contract):** the 2026-09-11 M4 proof recorded in `M4-E002`
> predated both the 0006 privilege (`REVOKE EXECUTE ... FROM PUBLIC`) correction
> noted in that same record **and** the payment-contract correction described
> below (authoritative provider-reference mapping, minor-unit amount
> validation). Neither the 2026-09-11 proof nor its immediate REVOKE-only
> follow-up were used as final acceptance evidence. This update replaces the
> webhook order-linkage and amount handling described further below and
> records a new, separate final-artifact proof (`docs/TEST_EVIDENCE.md`
> `M4-E004`–`M4-E006`). `M4-OPERATIONS-FINANCE` remains **IN_PROGRESS** and is
> **not** marked `COMPLETE` by this correction.

> **2026-09-23 correction notice (dispatch / redaction / payment-intent
> privilege):** this update adds a deterministic dispatch offer/assignment
> implementation (previously schema-only, per the 2026-09-23 pre-commit audit
> finding), fixes a secret-redaction defect in `Settings`'s default `repr()`,
> and corrects `zippy.payment_intents` runtime grants to SELECT/INSERT only
> (no UPDATE/DELETE). All three are proven by a new final-artifact proof
> (`docs/TEST_EVIDENCE.md` `M4-E007`–`M4-E009`); the M4-E004–M4-E006 proof
> predates this update and is superseded by it. `M4-OPERATIONS-FINANCE`
> remains **IN_PROGRESS** and is **not** marked `COMPLETE` (dispatch is
> minimal/deterministic only; see limitations below).


M4 wires the deterministic core to sandbox payment evidence, the POD settlement gate, the manual refund workflow, a draft-only Odoo adapter, and a deterministic dispatch offer/assignment flow on the canonical schema. No live keys, live payments, live Odoo credentials, production configuration, or deployment were used or authorized.

## Implemented Behavior

### Razorpay sandbox webhook ingress (FastAPI)

- `POST /api/v1/webhooks/razorpay` operates on the exact raw request body; HMAC-SHA256 with constant-time comparison (`hmac.compare_digest`); fails closed (503) when the sandbox secret is unconfigured, (401) on missing/invalid signature, (400) on malformed body or missing provider event ID.
- Receipt persists before projection; gateway evidence, payment projection, durable task, and outbox changes commit in one transaction.
- Dedupe by `(platform_id, provider, provider_event_id)`; duplicates return a stable `duplicate=true` result with no repeated effects.
- D-26 mapping: `payment.authorized → pending`, `payment.captured → evidence_verified` (plus draft-invoice financial request and Odoo sync task), `payment.failed → failed`, `refund.processed →` reconcile-only. Unsupported types are recorded without a projection. An absent, mismatched, or cross-tenant payment mapping produces `recorded_only` plus an operational exception.
- The signature, secret, Authorization header, and raw body never enter logs or responses; only the SHA-256 payload hash and a shaped field reference persist.

### 2026-09-23 correction: authoritative provider-reference mapping and minor-unit amounts

**Problem corrected:** the original webhook resolved the Zippy order from `payload.payment.entity.notes.zippy_order_id` — a value fully controlled by whatever created the Razorpay payment/refund object. A valid webhook signature only proves the payload came from Razorpay; it does not prove the `notes` value was ever authorized by Zippy. `notes` is Razorpay-side, caller-supplied metadata, not a server-controlled mapping. The original code also converted the provider's integer minor-unit amount into a major-unit `Decimal` immediately during parsing, discarding the minor-unit representation needed for exact validation and comparison.

**Fix — authoritative mapping (reuses the existing canonical structures):**
- The webhook now resolves the order exclusively from `payload.payment.entity.order_id` (the Razorpay *order* reference — NOT VERIFIED against a live Razorpay account, but this is Razorpay's documented Orders-API linkage field), looked up through `zippy.external_references` (`local_entity_type='order'`, `external_system='razorpay'`, `external_model='payment_order'`, `external_id=<provider order reference>`). This table already existed (migration 0003) and already enforces tenant-scoped, provider+external-identifier uniqueness via `UNIQUE (platform_id, external_system, external_model, external_id)` — no new uniqueness schema was required.
- What the existing schema could not express — the *expected* amount/currency a webhook must be checked against — is added in 0006 as `zippy.payment_intents`, a small table 1:1 with the `external_references` row (`expected_amount_minor_units bigint`, `expected_currency_code varchar(3)`), tenant-scoped and RLS-isolated like every other operational table.
- The mapping is created **only** by `FinanceRepository.prepare_payment_intent`, representing the approved server-side payment-intent/order preparation step (called after a Razorpay order already exists) or its synthetic test fixture (`api.tests_m4.conftest.prepare_payment_intent`). The public webhook route never calls it. A pre-check rejects rebinding an order to a different provider reference, and the `ON CONFLICT` path rejects a different order claiming an already-bound reference — both raise `ConflictError` without a partial write.
- `notes.zippy_order_id` is still parsed and persisted (inside the receipt's `payload_reference`) as **untrusted evidence/diagnostic metadata only**; it never participates in order resolution, even with a valid signature.
- Absent, amount/currency-mismatched, or cross-tenant mappings (enforced by `platform_id`-scoped RLS and query filters) leave the webhook receipt recorded with an operational exception (`GATEWAY_EVENT_UNMATCHED` / `GATEWAY_EVENT_AMOUNT_MISMATCH` / `REFUND_EVENT_AMOUNT_MISMATCH`) but create **no** trusted payment projection.
- `refund.processed` reconciliation is unaffected in design (it already resolved via `external_references`/`refund_executions`, never via `notes`) but now also validates the webhook's amount/currency against the manually approved refund's own amount/currency before reconciling; a mismatch stays evidence-only.

**Fix — explicit minor-unit amount semantics (`api/gateway.py`):**
- Razorpay amounts are handled as **integer currency minor units** end-to-end during parsing and validation (100 minor units = INR 1.00). `_minor_units()` rejects booleans (a `bool` is an `int` subclass in Python), floats, strings, zero/negative values, and anything above `MAX_AMOUNT_MINOR_UNITS = 999_999_999_999` (comfortably inside PostgreSQL `bigint`, the IEEE-754/JS safe-integer bound `2**53-1`, and the existing `numeric(18,2)` storage columns).
- Currency is persisted explicitly (`currency_code`) alongside every amount; nothing is silently reinterpreted between rupees and paise.
- Conversion between minor and major units (`minor_units_to_major` / `major_units_to_minor`) uses `Decimal` exact division/multiplication only — no binary floating-point arithmetic anywhere in the amount path.
- A webhook amount/currency is compared against the authoritative mapping's (or, for refunds, the approved refund execution's) expected amount/currency **before** any projection is written; a mismatch records reconciliation evidence and exits without updating the trusted projection.
- Refund amounts were already bounded by the manually approved refund's own amount (the projection uses the refund request's amount, never the webhook's reported amount); the new mismatch check adds an explicit guard so a mismatched webhook amount doesn't silently reconcile at all.

### POD and settlement gate

- POD metadata submission (vendor participant or admin), admin-only verification decision, duplicate-safe by `object_key`.
- `evaluate_settlement` / `pod_gate_evaluate` create a projection-only `settlement_projections` row (`not_requested`) only after accepted POD evidence. No money moves; no Odoo payment; no accounting reconciliation state.
- Migration 0006 adds the database-level PAY-INV-002 gate: `validate_settlement_projection()` rejects any non-failed settlement projection without an accepted POD for the order (proven by direct INSERT denial, SQLSTATE 23514).


### Manual refund workflow

- Request (customer participant or admin) → manual admin decision → execution-evidence recording. Repository pre-checks and database triggers enforce: no self-approval, active-admin approver, execution only after an approved decision by a different account, exact amount/currency/target binding, idempotent replays and conflicts.
- A `refund.processed` webhook reconciles evidence only when a matching approved-and-executed refund already exists (gateway event + `reversed` projection + external reference marked synchronized). Otherwise it is recorded with a high-severity operational exception and creates nothing.
- No payment-provider call exists anywhere in this milestone.

### Draft-only Odoo adapter

- `OdooDraftAdapter` uses supported JSON-RPC `execute_kw` only, allowlisted to `res.partner search/create/read` and `account.move create/read`. Prohibited methods (`action_post`, payment registration, validation/confirmation, write/unlink, posting) raise before any transport call; unit tests assert the transport never receives them.
- The `odoo_draft_sync` durable task performs external calls outside the database transaction and records `external_references` idempotently (partner per order, move per financial request); conflict with a different external ID is rejected. Timeout-after-success is safe: acknowledged requests return early and references are created once.
- Transport failure enters bounded retry and dead-letters with an operational exception; no accounting mutation occurs on failure.

### Durable processing and reconciliation

`FinanceWorker` mirrors the M3 claim/lease/fail semantics with explicit M4 task types: `odoo_draft_sync`, `gateway_reconcile` (stale/unmatched receipt re-drive, idempotent), `pod_gate_evaluate`, `refund_reconcile`. Concurrent claims yield one effective execution under `FOR UPDATE SKIP LOCKED`.

### 2026-09-23 addition: deterministic dispatch offer/assignment (`api/repositories_dispatch.py`, `api/routes_dispatch.py`)

**Schema check first:** `zippy.dispatch_offers`, `zippy.trip_assignments`, `zippy.trips`, `zippy.vehicles`, `zippy.vehicle_models`, `zippy.vehicle_documents`, `zippy.driver_profiles`, `zippy.driver_associations`, `zippy.vendor_profiles`, `zippy.company_memberships`, `zippy.transaction_participants`, `zippy.order_transition_rules` (already allows `confirmed → assigned`), `zippy.transition_order`, `zippy.operational_events`, and `zippy.event_outbox` were all already present from M2/M3 and were sufficient for every requirement below **except one**, which was initially reported as a schema blocker (no trusted `zippy.orders` required-body-type field) and is resolved by the 2026-09-24 `zippy.dispatch_requirements` addition documented in its own section below.

**Design — single-candidate evaluation, no automatic matching:** offer creation names one exact vendor/vehicle/driver candidate (caller-supplied, admin-only) and evaluates it; there is no search, scoring, ranking, radius, or timeout invention anywhere (D-27 constraint). Eligibility checks, in order, using canonical data:
1. Order is platform-scoped and `status = 'confirmed'` (dispatch-eligible; `ORDER_NOT_DISPATCH_ELIGIBLE` otherwise).
2. `orders.special_handling_code`: `NULL`/empty proceeds; `hazardous`/`hazmat` (case-insensitive) fails closed with `HAZARDOUS_CARGO_NO_WORKFLOW` (no approved specialized workflow exists); any other non-null value fails closed with `AMBIGUOUS_SPECIAL_HANDLING` (ambiguous compliance information → manual fallback, never automatic assignment).
3. **ORD-INV-003 body-type compatibility** (added 2026-09-24, see the dedicated section below): the order's trusted `zippy.dispatch_requirements.required_body_type` is compared with the candidate's `zippy.vehicle_models.body_type` using exact, normalized-only (`btrim`+`lower`) equality — never request-supplied, never fuzzy.
4. Vendor/vehicle/driver exist under the caller's platform and the named vendor matches the order's committed `transaction_participants` vendor row (else `ConflictError`, a hard rejection — including cross-tenant references, which simply do not resolve under the caller's platform-scoped queries).
5. `vendor_profiles.eligibility_status`, `vehicles.status`, `driver_profiles.eligibility_status` must each be `approved`.
6. `driver_associations` must have a currently-valid (`valid_from`/`valid_until`) row linking the named driver to the named vendor.
7. `vehicle_models.capacity_kg >= orders.cargo_weight_kg`.
7. `vehicle_documents` must have a `verified`, unexpired (`valid_until IS NULL OR valid_until >= today`) row for `document_type IN ('fitness', 'insurance')` (the `'fitness'` string is the existing convention from `db/zippy/tests/verify.sql`; `'insurance'` follows the same freeform-text convention — no canonical enum exists for either).
8. Vehicle and driver must have no other active (`released_at IS NULL`) `trip_assignments` row (available/assignable check).

Any failure records a sanitized `operational_exceptions` row (`entity_type='order'`, a specific reason code, no invented values) and returns a `manual_review` outcome — **no offer row is created** for an ineligible candidate (the `dispatch_offers.status` enum has no "rejected" state, matching the existing schema).

**Offer lifecycle (`pending`/`accepted`/`declined`/`expired`/`cancelled`, exactly the existing `offer_status` enum):** creation is idempotent on a caller-supplied `Idempotency-Key`/`idempotency_key` (fingerprinted against order/vendor/vehicle/driver; a mismatched replay is a conflict). `decline`/`cancel` are real, persisted state transitions (decline: vendor/driver/admin; cancel: admin-only). Expiry is lazily persisted by a dedicated `expire_if_due` call, run in its **own** committed transaction *before* any accept attempt — a status mutation cannot safely be persisted inside the same transaction as a `ConflictError` that will roll it back.

**Atomic assignment:** `accept_dispatch_offer` locks the `orders` row (`SELECT ... FOR UPDATE`) first, serializing every concurrent accept/decline/cancel attempt for that order; it then locks the specific offer row, authorizes the actor (admin, the offer's vendor account/company-membership, or the offer's driver account — **resolved only from server-side identity, never from request-supplied role/tenant/metadata**), and rejects any offer that is not `pending` and unexpired (idempotent replay of an already-`accepted` offer by the same offer id returns the existing assignment, not an error). On success it creates/promotes the `trips` row, inserts exactly one `trip_assignments` row, calls the existing `zippy.transition_order(... 'confirmed' → 'assigned' ...)` RPC (the only path that ever changes `orders.status`), and records a dispatch-specific `operational_events`/`event_outbox` pair — all in the one transaction opened by the caller. The pre-existing `dispatch_one_accepted_offer_idx` partial unique index (`(platform_id, order_id) WHERE status = 'accepted'`) plus the `orders` row lock are the two independent guards that make "at most one assignment per order" hold under real concurrency; **no schema change was needed or made** for this guarantee.

**Manual fallback:** an ineligible candidate never creates an offer, trip, or assignment; it only records the sanitized exception above. No radius/timeout/ranking/escalation values are invented, and nothing broadcasts or contacts drivers/vendors/transport companies (no network code exists anywhere in the dispatch module — proven by a test that patches `socket.socket.connect` to raise and confirms it is never called).

**Deliberately out of scope for this minimal deterministic surface:** no HTTP-driven "search all eligible candidates" endpoint (single named candidate only, per the anti-matching-engine constraint); no automatic expiry sweep/worker (lazy, on-touch only); trip milestone/POD-linked release of a `trip_assignments` row (`released_at`) is unimplemented (no requirement asked for it here).

### 2026-09-24 addition: trusted body-type requirement (`zippy.dispatch_requirements`, ORD-INV-003)

The earlier "schema blocker" is resolved. The blocker was not that no body-type data exists anywhere — `zippy.vehicle_models.body_type` already stores a body type per model (plain `text NOT NULL`, no fixed taxonomy) — but that **no trusted, order-side requirement existed to compare it against** without trusting offer-acceptance-time input.

**Selected storage design (option B — smallest tenant-scoped canonical storage):** `zippy.orders` is immutable to the application role apart from a narrow allowlisted column set, and ORD-INV-003 forbids deriving the requirement from client metadata at assignment time, so a new tenant-scoped table `zippy.dispatch_requirements` was added in the uncommitted `0006_operations_finance` migration. It is bound to `(platform_id, order_id)` (UNIQUE + tenant-scoped FK to `orders`), stores one `required_body_type text` code in the **same free-text domain `vehicle_models.body_type` already uses** (no new taxonomy invented — none is canonically defined anywhere), plus `created_by_account_id`/`correlation_id` audit columns. RLS is enabled and forced with the canonical `platform_isolation` policy.

**No canonical enum exists for body types.** Neither the approved PRD, `DECISIONS.md`, nor the canonical schema defines a fixed body-type taxonomy — `vehicle_models.body_type` is deliberately free text. This correction therefore does **not** invent one; it treats the *set of body types actually present in a platform's own `vehicle_models`* as the recognized vocabulary at evaluation time, and fails closed to manual fallback for anything else.

**Trusted input boundary:** the requirement row is written **exactly once**, inside `CoreRepository.create_order` (the authenticated server-side order-intake path), from the already-validated `OrderCreate.service.body_type` — the same field already echoed into the pricing evidence hash. It is never accepted later. The runtime role `zippy_app` is granted only `SELECT, INSERT` (never `UPDATE`/`DELETE`), so **no application code path — including the public dispatch-offer-accept endpoint, which never references this table — can create it late or change it, before or after any `dispatch_offers`/`trip_assignments` row exists.** Client metadata, notes, agent output, and webhook payloads are never consulted; the offer-accept request body carries no body-type field at all.

**Evaluation behavior (in `DispatchRepository.create_dispatch_offer`, ordered after special-handling):** exact normalized (`btrim`+`lower`) equality only — no fuzzy/substring/AI matching:
- requirement row missing → `DISPATCH_BODY_TYPE_REQUIREMENT_MISSING` (manual fallback);
- requirement text not present among the platform's `vehicle_models.body_type` values → `DISPATCH_BODY_TYPE_UNKNOWN` (unknown/ambiguous → manual fallback);
- candidate vehicle's model body type ≠ requirement → `VEHICLE_BODY_TYPE_MISMATCH` (explicit reject, no offer created);
- exact match → proceeds to the remaining checks. Capacity is checked independently and must *also* pass.

Every rejection records a sanitized `operational_exceptions` row and creates **no** offer, trip, assignment, or order-status transition. Cross-tenant requirement/vehicle/order rows are invisible and denied by the platform-scoped joins plus forced RLS.

### 2026-09-23 addition: secret-redaction correction (`api/config.py`)

The retained failed M4 proof (`docs/TEST_EVIDENCE.md` `M4-E006`, log `2zIomoO3`) exposed the synthetic webhook/JWT test secret strings in a pytest failure traceback: `Settings` used the default dataclass `repr()`, which prints every field verbatim, and pytest's assertion-failure output implicitly calls `repr()` on local variables (including the `settings` fixture). Fixed by marking every secret-bearing field (`database_url`, `auth_jwt_secret`, `razorpay_webhook_secret`) with `dataclasses.field(repr=False)`; `repr()`/`str()` now omit them entirely while every non-secret field (platform, pricing, timing) remains visible. This is a targeted exclusion, not a blanket repr suppression, and required no change to any call site (`dataclasses.replace(...)`, used throughout the test suite to override `database_url`, is unaffected). New regression tests (`api/tests/test_config_redaction.py`) prove sentinel secret values never appear in `repr()`, `str()`, `dataclasses.replace()` output, or a simulated pytest-style assertion-failure message — reproducing the exact failure shape from the retained log. The historical failed log itself is unmodified and still contains the synthetic (non-production) secret strings; it is preserved as evidence, not rewritten.

### 2026-09-23 addition: payment-intent runtime-privilege correction (0006)

Auditing `zippy.payment_intents`'s grants found the runtime role (`zippy_app`) held `INSERT, UPDATE, DELETE` — UPDATE/DELETE were never used by any application code path (confirmed by inspection: no `UPDATE`/`DELETE` statement against this table exists anywhere in `api/`), but the grant itself violated the "runtime roles may perform only the minimum operations needed" / "must never UPDATE or DELETE" requirement. Corrected 0006 to `GRANT SELECT, INSERT ON zippy.payment_intents TO zippy_app;` only (readonly grant unchanged). This is a **grant correction only** — no table/column/constraint change — so only 0006's manifest checksum needed refreshing (0001–0005 remain byte-identical to HEAD). New tests (`api/tests_m4/test_payment_intent_privileges.py`), run through the restricted application login (`zippy_m2_app_login`, the same role the webhook uses), prove: the privilege catalog is exactly SELECT+INSERT (no UPDATE/DELETE/TRUNCATE); a direct `UPDATE`/`DELETE` against the table raises `psycopg.errors.InsufficientPrivilege` (SQLSTATE 42501), independent of row content or RLS; and the table's owner is the NOLOGIN `zippy_migrator` role, never the connected runtime login (migration/owner authority stays separate from runtime authority).

## Canonical Schema Assessment (0006)

Migrations 0001–0005 already provided every other required constraint. Exactly one demonstrated gap required 0006:

- `settlement_projections.financial_request_id NOT NULL` made pre-request settlement *eligibility* unrepresentable → dropped the NOT NULL.
- No DB-level POD gate existed on settlement projections → added trigger `settlement_projection_pod_gate`.
- Added `webhook_receipts(platform_id, processing_status, received_at)` index for reconciliation sweeps.

0006 is reversible in disposable scope (`TRUNCATE` + restore NOT NULL), creates no cross-database foreign keys, adds no Odoo ledger columns to orders, and encodes no automatic refund/settlement/posting behavior. 0001–0005 are byte-for-byte preserved; manifest checksums refreshed for 0006 only.

**2026-09-23 addendum:** 0006 also adds `zippy.payment_intents` (see the correction above) with RLS enabled/forced, an explicit `platform_isolation` policy, and explicit `zippy_app`/`zippy_readonly` grants (0004's blanket grant only covered tables that existed at that point; every table added afterward needs its own explicit grants, matching the established per-object pattern already used for 0005's functions). The down migration drops the table before any other 0006 rollback step. 0001–0005 remain byte-for-byte preserved; only 0006's checksums were refreshed.

**2026-09-23 addendum (this update):** 0006's `payment_intents` grants were narrowed to `SELECT, INSERT` only (dropping `UPDATE, DELETE`) — see the privilege correction above. No table, RLS, FK, or uniqueness definition changed; the manifest's 0006 up-file checksum was refreshed again (down-file unchanged). Dispatch required **no** 0006 (or new-migration) change at all.

## Validation (2026-09-11, historical — superseded by the 2026-09-23 run below)

| Gate | Result |
|---|---|
| Host unit suite (`api/tests` + `api/tests_m4`) | PASS: 42 passed, 14 skipped (disposable-DB guards), 2 known deferred dependency deprecation warnings (FastAPI/Starlette TestClient httpx shim; AnyIO `BlockingPortal` alias) — not suppressed, locks unchanged |
| Ruff (new/changed M4 files) | PASS |
| Strict mypy (6 new modules) | PASS |
| Manifest/checksum validation | PASS: 0006 entry matches file SHA-256; 0001–0005 unchanged |
| Isolated M4 proof (`run_m4_finance_proof.sh`) | PASS: exit 0, pytest 56 passed / 2 warnings (includes the M3 suite as regression), all harness markers PASS |
| M2 regression + 0006 up/down/reapply (`run_isolated_proof.sh`) | PASS: exit 0, all 11 markers PASS |

### Failed attempts retained (none counted as passing, 2026-09-11)

1. M4 proof run 1 (`p4vCYNhy`) failed: 4 test defects — psycopg pools cannot reopen after a TestClient lifespan closes them (tests now use one Database per client, separate worker pools); refund-execution replay was rejected on `executed` status before the idempotency check (repository fixed); a test write helper used `fetchall()` on INSERT without commit. Fixed, then rerun once.
2. M2 regression run 1 failed at `verify.sql`'s canonical-chain count (`= 5`). The assertion tracks chain length (bumped 4→5 by M3); updated to 6 for 0006.
3. M2 regression run 2 failed because the new 0006 function inherited default PUBLIC EXECUTE; added `REVOKE EXECUTE ... FROM PUBLIC` to match the canonical privilege posture, refreshed the manifest checksum, and reran.

**As already noted in `docs/TEST_EVIDENCE.md` `M4-E002`, the 2026-09-11 passing M4 proof predates the REVOKE correction above and was not itself used as final acceptance evidence; the REVOKE was folded in and covered only by the 2026-09-11 M2 regression at the time.** The 2026-09-23 correction below replaces the webhook order-linkage and amount-handling behavior entirely and is proven by its own, separate final run.

## Validation (2026-09-23 correction — final for this update)

| Gate | Result |
|---|---|
| Host unit suite (`api/tests` + `api/tests_m4`) | PASS: 52 passed, 25 skipped (disposable-DB guards), 1 known deferred dependency deprecation warning |
| Focused ruff (changed files: `api/gateway.py`, `api/repositories_finance.py`, `api/tests/test_gateway.py`, `api/tests_m4/test_finance_integration.py`, `api/tests_m4/conftest.py`) | PASS |
| Strict mypy (`api/gateway.py`, `api/repositories_finance.py`, `api/odoo.py`, `api/worker_finance.py`, `api/routes_finance.py`, `api/models/finance.py`) | PASS |
| Manifest/checksum validation | PASS: 0006 up/down SHA-256 refreshed; 0001–0005 confirmed byte-identical to HEAD |
| Final isolated M4 proof (`run_m4_finance_proof.sh`) | PASS: exit 0, pytest **77 passed, 1 warning**, all harness markers PASS (webhook ingress, idempotency, authorization, POD settlement gate, manual refund, draft-only Odoo, reconciliation, M3 regression, network isolation, cleanup, socket hardening, negative local-user probe) |
| M2 regression + 0006 up/down/reapply (`run_isolated_proof.sh`) | PASS: exit 0, all 11 markers PASS (run after the final M4 proof, per the security-catalog fix below) |

### Failed attempts retained (none counted as passing, 2026-09-23)

1. M4 proof attempt 1 (log `2zIomoO3`, exit 1, `2 failed, 75 passed`): `prepare_payment_intent` let a same-order rebind to a different provider reference fall through to a raw, uncaught `psycopg.errors.UniqueViolation` instead of a clean `ConflictError` (the `INSERT ... ON CONFLICT` only arbitrates the `(system, model, external_id)` constraint, not the `(local_entity_type, local_entity_id, system, model)` one). Fixed by adding an explicit order-scoped pre-check. The same defect also broke `test_odoo_draft_sync_success_failure_and_single_claim` because the conflict test had reused the shared `ORDER_B` fixture, permanently binding it away from its expected mapping; fixed by adding dedicated, otherwise-untouched conflict-fixture orders (`ORDER_C`, `ORDER_D`) in `setup_m4.sql`. Rerun once — passing (log `xVe8arOt`, exit 0, `77 passed`).
2. M2 regression attempt 1 (log `lyovExzs`, exit 3): `verify_security.sql`'s hardcoded table-classification catalog (48 tables, 28 `RLS REQUIRED`, one `platform_isolation`-policy count of 45) did not yet include the new `zippy.payment_intents` table, failing the "classification and catalog table membership match exactly" assertion. Fixed by adding the table to the catalog and bumping the three affected counts to 49/29/46 (matching `verify.sql`'s already-bumped 46). Rerun once — passing (log `bogmnHKC`, exit 0, all 11 markers PASS).

Both failed attempts are evidence-only; neither was counted as the passing final proof.

### Final proof evidence locations (2026-09-23, private, mode 600, not committed)

- Final M4 proof: `/tmp/zippy-m4-proof-log.xVe8arOt/proof.log` (SHA-256 `fcac88de93c69f14ff93a759beb8d2bc590b680a74eb0acb52bff1edaaf6670f`)
- Failed M4 proof attempt: `/tmp/zippy-m4-proof-log.2zIomoO3/proof.log` (SHA-256 `cbcab9ffdccc5d12d8a394a64656acac72f69b84663e6d102fc797d6c9167498`)
- Final M2 regression: `/tmp/zippy-m2-regression-log.bogmnHKC/proof.log` (SHA-256 `43b85805bdbdeb8c1c15d0462c23d789515021406cbe79bfd7f7ebe0c7c35d5f`)
- Failed M2 regression attempt: `/tmp/zippy-m2-regression-log.lyovExzs/proof.log` (SHA-256 `cc96555d315c1e5e5d3b58536b8bf9c3545457a5f4fbf2fcdec91feea28d4e51`)

Exact cleanup verified after both final proofs: zero `zippy*` Docker containers/volumes remain; no leftover private socket directories under `/tmp`; port 5432 not listening on the host.

## Validation (2026-09-23 dispatch/redaction/privilege correction — final for this update)

| Gate | Result |
|---|---|
| Focused unit tests (`api/tests/test_config_redaction.py`) | PASS: 4 passed, run repeatedly during development until stable |
| Focused PostgreSQL integration tests (`api/tests_m4/test_dispatch_integration.py`, `api/tests_m4/test_payment_intent_privileges.py`) | PASS after 3 defects found and fixed during development iteration (see below); stable before the final gated proof |
| Complete host suite (`api/tests` + `api/tests_m4`), direct unmasked exit capture | PASS: exit `0`, **56 passed, 51 skipped**, 1 known deferred dependency warning |
| Focused ruff/mypy (`api/config.py`, `api/repositories_dispatch.py`, `api/models/dispatch.py`, `api/routes_dispatch.py`, `api/main.py`) | PASS |
| Manifest/checksum validation | PASS: only 0006's up-file checksum changed (grant correction); down-file and 0001–0005 unchanged/byte-identical |
| Final isolated M4 proof (`run_m4_finance_proof.sh`) | PASS: exit `0`, pytest **107 passed, 1 warning**, all harness markers PASS |
| M2 regression (`run_isolated_proof.sh`) | Required (0006 grants changed) and run once after the final M4 proof: PASS, exit `0`, all 11 markers PASS |
| Cleanup (independent, post-proof) | PASS: zero `zippy*` containers/volumes, no leftover socket directories, port 5432 not listening |

### Development-iteration defects found and fixed (pre-final, not gated evidence)

Per the validation order (focused unit → focused integration → full host suite → final gated proof), these were found and fixed *before* reaching a stable state, using the same disposable-proof harness in a debugging loop (raw logs not individually retained — these are development iterations, not the gated final-proof attempts below):
1. **Outbox idempotency-key collision:** `accept_dispatch_offer` reused the same idempotency key for both the `transition_order` RPC call and its own `dispatch.assignment_created` outbox record; both target `event_outbox(platform_id, destination='internal', idempotency_key)`, so the second insert silently no-opped via `ON CONFLICT DO NOTHING`. Fixed by suffixing the dispatch-specific key.
2. **Test fixture cross-contamination:** several tests reused the shared baseline order/vehicle/driver fixtures for a *real, permanent* accept (which consumes them), causing every later test against the same fixtures to fail. Fixed by giving every test that performs a real accept its own freshly created order/vehicle/driver.
3. **Transactional persistence bug:** the original design tried to persist an `'expired'` status transition *inside* the same transaction as the `ConflictError` it then raised — the raised exception rolled the whole transaction back, undoing the mutation. Fixed by extracting `expire_if_due` into its own, separately committed transaction, called before the accept attempt (mirrored in both the route and the test helper).

### Failed attempts retained (none counted as passing, 2026-09-23, this update)

Gated proof runs after the fixes above were stable were **not preceded by any additional failing final-gate attempt** — the final M4 proof and M2 regression both passed on their first (and only) run after the fixes. No failed final-gate log exists for this specific update beyond the development-iteration defects already documented above.

### Final proof evidence locations (2026-09-23, this update, private, mode 600, not committed)

- Final M4 proof: `/tmp/zippy-m4-final-proof.SBBPRUZW/proof.log` (SHA-256 `aaa151afe294ea8871b65a17bf683c56f146b042de749332215d0af295641604`)
- Final M2 regression: `/tmp/zippy-m2-final-regression.3DR4xnvV/proof.log` (SHA-256 `d83595da1624eb1c8c9160e6b66091b3eba75e4c605a0a0d0a7d5ccc70f9375c`)

## Validation (2026-09-24 body-type compatibility correction — final for this update)

This update was interrupted mid-pass by a power cut and resumed by recovering from the actual filesystem state (no assumption about which steps completed). The `zippy.dispatch_requirements` schema, gate logic, and verify/grant counts were found already present and internally consistent; only the focused body-type tests and evidence documentation were unfinished.

| Gate | Result |
|---|---|
| Python compile + Ruff (`api/repositories_dispatch.py`, `api/repositories.py`, `api/tests_m4/test_dispatch_integration.py`) | PASS |
| Strict mypy (`api/repositories_dispatch.py`, `api/repositories.py`) | PASS: no issues |
| Host suite (`api/tests` + `api/tests_m4`), direct exit capture | PASS: exit `0`, **56 passed, 60 skipped** (disposable-DB guards) |
| Focused body-type tests (`api/tests_m4/test_dispatch_integration.py`, 9 new) | PASS within the final disposable proof |
| Final isolated M4 proof (`run_m4_finance_proof.sh`) | PASS: exit `0`, pytest **116 passed, 1 warning**, all harness markers PASS |
| M2 regression + 0006 up/down/reapply (`run_isolated_proof.sh`) | PASS: exit `0`, all 11 markers PASS (required: 0006 + grants + security SQL changed) |
| Manifest/checksum validation | PASS: only 0006 up/down SHA-256 refreshed; 0001–0005 confirmed byte-identical to HEAD |
| Cleanup (independent, post-proof) | PASS: zero `zippy*` containers/volumes, no leftover socket directories, port 5432 not listening |

### Failed attempt retained (not counted as passing, 2026-09-24)

One gated M4 proof attempt failed (exit `1`, `10 failed, 106 passed`) before the final passing run. Root cause was **test-fixture defects, not a production or migration defect** (classified B/C per the correction protocol):
1. `test_requirement_is_immutable_after_offer_and_assignment` performed a *real, permanent accept* against the **shared** `VEHICLE_1`/`DRIVER_PROFILE_1` fixtures, consuming them and leaving an active `trip_assignments` row — every later test creating an offer on `VEHICLE_1` then correctly received `VEHICLE_UNAVAILABLE` → `manual_review` → `dispatch_offer_id=None`, cascading into 7 downstream failures (`unauthorized_actor`, `expired_offer`, `declined_offer`, `cancelled_offer`, `rollback_on_injected_order_conflict`, `socket`, `no_secrets`). Fixed by giving that test its own freshly created vehicle/driver (the file's own documented anti-pattern).
2. `test_mismatching_body_type_rejects_eligibility` (and the override/no-assignment tests) used a requirement body type (`closed-box`) that no platform `vehicle_models` row defines; the gate's `body_type_known` check (evaluated before the candidate comparison) correctly returned `DISPATCH_BODY_TYPE_UNKNOWN`, not the expected `VEHICLE_BODY_TYPE_MISMATCH`. Fixed by cataloguing a `closed` model via a `_catalogue_closed_model()` helper so the tests exercise a genuine known-vs-known mismatch.
3. `test_cross_tenant_requirement_is_invisible` tried to INSERT a platform-2 requirement row while connected as the platform-1 app role; the table's forced-RLS `WITH CHECK` correctly rejected it (`new row violates row-level security policy`), which is the security control working as intended. Fixed to assert the RLS denial itself and verify a platform-1 order with no requirement still falls back as missing.

The failed log is retained unmodified as evidence: `/tmp/zippy-m4-proof-bodytype.log` (SHA-256 `2b35d1d6d2ee4198a0d5606e9086c1be7e1ed6ab2552515409bd824c8ad45399`, mode 600, `10 failed, 106 passed`). Fixed, then one fresh full M4 proof and one M2 regression were run — both passed.

### Final proof evidence locations (2026-09-24, this update, private, mode 600, not committed)

- Final M4 proof: `/tmp/zippy-m4-proof-bodytype-r2.log` (SHA-256 `7e241b377196f6348312948d474fcf82325bd3a427aa6b23359f7626658dd986`, `116 passed, 1 warning`)
- Final M2 regression: `/tmp/zippy-m2-regression-bodytype.log` (SHA-256 `34361b04ab0627b7d337bbaa4753a0029c5c463764cfaeec8e6aad73c9a92f4b`, all 11 markers PASS)
- Failed M4 proof attempt (retained, not counted): `/tmp/zippy-m4-proof-bodytype.log` (SHA-256 `2b35d1d6d2ee4198a0d5606e9086c1be7e1ed6ab2552515409bd824c8ad45399`)

Exact cleanup verified after both final proofs: zero `zippy*` Docker containers/volumes remain; no leftover private socket directories under `/tmp`; port 5432 not listening on the host.

## Final Acceptance (2026-09-24 — owner-authorized acceptance audit)

A full acceptance audit was run against the committed baseline `2c5225b5edfcbac1739bb829c937e41bceee0eca` with local HEAD, `origin/master`, and remote `master` all equal and nothing staged. Every worktree path was inventoried and explained by M4 scope; migrations 0001–0005, dependency lock/declaration files, `docker-compose.yml`, production configuration, `deploy-hostinger.yml`, and unrelated legacy paths were confirmed unchanged. D-26 (Gopinathan, 2026-09-11, product/finance/Odoo owner) was confirmed present exactly once and the implementation verified to remain within its boundaries (sandbox/synthetic Razorpay, authenticated webhook ingress, evidence-only `refund.processed` reconciliation, manual refund approval at every amount, manual settlement release, deterministic dispatch, POD settlement gate, draft-only Odoo fake-transport adapter).

Static gates: `git diff --check` clean; Ruff PASS (all changed/new Python); `py_compile` PASS; **strict mypy exit `0` (12 modules, run during this audit)** — the earlier success claim was re-verified by real execution, not preserved unsupported; Bash syntax PASS; workflow YAML parses; manifest full SHA-256 values match both 0006 files; focused secret scan 0 hits; prohibited-authority scan confirmed no added `SECURITY DEFINER`, `orders.status` changed only via the `transition_order` RPC, and settlement release remains manual with no release-execution path. Functional/security properties were verified from code and tests (raw-body constant-time HMAC before parsing/writes, fail-closed on missing secret/signature/event ID, authoritative server-created payment intent with integer-minor-unit amount/currency checks, refund reconcile-only with self-approval denial, POD gate fail-closed, Odoo allowlisted draft-only with prohibited methods refused before transport, secrets excluded from `repr`/`str`, dispatch with no network/notification calls). Dispatch body-type compatibility properties were all verified against the 31 dispatch tests enumerated in `M4-E010`.

Evidence logs were validated in place (all mode 600, secret-scan clean, expected totals present) and artifacts confirmed un-drifted (all executable/test/migration/harness files predate the successful logs), so the expensive full proofs were **not** rerun: retained failed body-type proof exit `1` (`10 failed, 106 passed`, SHA-256 `2b35d1d6d2ee4198a0d5606e9086c1be7e1ed6ab2552515409bd824c8ad45399`); final M4 proof exit `0` (`116 passed, 1 warning`, all markers PASS, SHA-256 `7e241b377196f6348312948d474fcf82325bd3a427aa6b23359f7626658dd986`); final M2 regression exit `0` (all 11 markers PASS, SHA-256 `34361b04ab0627b7d337bbaa4753a0029c5c463764cfaeec8e6aad73c9a92f4b`); host suite exit `0` (`56 passed, 60 skipped`).

**Result: all acceptance gates PASS. `M4-OPERATIONS-FINANCE` is COMPLETE for its authorized sandbox/synthetic, disposable-environment scope.** No deployment, live payment, live Odoo call, production database operation, workflow enablement, or M5 implementation occurred or is authorized by this acceptance.

## Isolation and Security Controls

Disposable PostgreSQL 16.15 (`postgres@sha256:f1c337…f6f94`), Docker network `none`, no published ports, hardened private Unix socket (`socket_dir_mode=2700` permission bits `rwx------`, socket file `777`), `password_encryption=scram-sha-256`, `pg_hba` local auth `scram-sha-256`, negative unrelated-user probe (`nobody`, uid 65534) PASS, read-only repository mount, generated unrecorded credentials, synthetic `.invalid` identities, exact container/volume/socket cleanup verified absent after every proof run across all three 2026-09 updates.

## NOT VERIFIED / Prohibited / Deferred

- **NOT VERIFIED (external):** live Razorpay sandbox reachability, real signature compatibility with Razorpay's production header format, the real Razorpay payment/order webhook payload shape (this correction's `entity.order_id` field mirrors Razorpay's documented Orders-API linkage but was not checked against a live account), live Odoo 18 API behavior, Odoo custom-field availability (`zippy_mirror_*` payload keys are fake-server contract only), production ingress routing, production credentials.
- **NOT VERIFIED (dispatch, external-limited):** vehicle/body-type compatibility is now implemented and proven against the trusted `zippy.dispatch_requirements` row (2026-09-24 section above) — the prior schema blocker is resolved. Still NOT VERIFIED: driver licence/vehicle document validity is checked structurally (approved/verified + unexpired) but not against any live regulatory registry; hazardous-cargo classification uses only `orders.special_handling_code` string matching, not a canonical enum.
- **Prohibited and unchanged:** live keys/payments, live Odoo credentials, autonomous posting/payment/reconciliation, direct Odoo SQL, production deployment, automatic refunds or settlements, n8n/Paperclip wiring, accounting-authority changes, AI-based matching, maps, real notifications, n8n/Paperclip/Temporal activation, external network calls. No live Razorpay order was created or paid; `FinanceRepository.prepare_payment_intent` is only ever invoked by the synthetic test fixture in this change. Dispatch never broadcasts, contacts, or notifies any driver/vendor/transport company (proven by a socket-patch test).
- **Deferred:** SSE delivery of outbox projections, real OCR/binary POD storage, production pricing policy, Paperclip grant binding for consequential actions (M5+), an automatic dispatch-offer expiry sweep/worker (expiry is lazy, on-touch only), trip-assignment release (`released_at`) on delivery/POD completion, an HTTP-driven "find all eligible candidates" search endpoint (out of scope by design — single named candidate only).

`M4-OPERATIONS-FINANCE` remains the sole IN_PROGRESS task and is **not** marked complete by this report or this correction. Dispatch is now implemented (deterministic, minimal) with passing evidence; POD was already implemented; both are proven together in the same final M4 proof above.
