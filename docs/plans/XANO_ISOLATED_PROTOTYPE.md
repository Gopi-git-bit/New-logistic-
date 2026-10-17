# Isolated Xano evaluation — implementation preparation

Date: 17 October 2026. Owner: Gopinathan / Gopi-git-bit.
Reference source: PR #31 merge `52ca43d8a2fb4f3d5d105dc6bb9f7420e5cfca26`.
Decision: D-50. Status: OFFLINE REFERENCE PREPARED; XANO RUNTIME NOT VERIFIED.

## Purpose and authority

The owner accepts an isolated prototype before considering consolidation of
backend, database and runtime agents into Xano. Prepare code, synthetic tests,
contracts and a feature PR now, then identify connection requirements. This
is an evaluation exception, not a replacement of canonical RPC/RLS, state,
governance or accounting authority. No application traffic is moved. D-33
remains pending; refunds always require manual approval. Existing PostgreSQL
proof preparation remains available and its 72 cases remain unverified.

No account/paid workspace creation, Xano installation, key provisioning,
production migration, live inference, Qwen fallback, registry publication,
workflow dispatch, VPS modification or external financial effect occurs here.
A key alone never proves platform readiness or authorizes production promotion.

## Prepared artifacts and honest limits

- `prototypes/xano/reference_model.py`: executable, stdlib-only SQLite contract
  oracle, with real local transactions, durable files and simultaneous threads.
- `prototypes/xano/tests/test_reference_model.py`: adversarial contract tests,
  including losing concurrent requests and injected transaction interruption.
- `prototypes/xano/contract.json`: machine-readable endpoint responsibilities,
  identity rules, six invariants and explicit outstanding platform gates.

This is NOT deployable XanoScript, a FastAPI replacement, an HTTP service or a
production schema. SQLite BEGIN IMMEDIATE serializes writers; passing local
races does not prove Xano record locking, isolation level or unique-index
behavior. The model has no network, provider client, token loader or credential
configuration. Principal objects are trusted test fixtures; they are not an
authentication implementation. Test clocks, grant issuance, vehicle seeding,
interruption injection and SQL introspection must never be public endpoints.
The test webhook uses a public synthetic HMAC secret and simplified event shape,
not Razorpay's production protocol. Payment amount uses integer synthetic units,
not the pricing engine or a new accounting ledger.

Eligibility is deliberately only a synthetic flag plus tenant/state availability.
Production eligibility must preserve all existing vehicle, driver, offer,
capacity, compliance, location, time and expiry rules. No ranking or dispatch
policy is invented. Assignments remain active in this bounded slice; delivery,
release, cancellation, pricing, tax, POD and settlement are not implemented.

## Xano translation blueprint

Create only namespaced prototype objects in a separately verified disposable
workspace/data source. Disable public signup, automatic CRUD, live providers,
public MCP tools, database triggers and schedules until explicitly reviewed.
Do not reuse production data through a branch that shares its database.

| Table | Required constraints and boundary |
|---|---|
| prototype_orders | Immutable tenant/customer binding; explicit state transition function; no generic status update endpoint |
| prototype_vehicles | Tenant/vendor binding and reviewed eligibility inputs; fixture-only seeding |
| prototype_active_assignments | Database-enforced unique order and unique vehicle; historical rows separate from active reservations |
| prototype_commands | Unique tenant/actor/action/key; canonical request hash and committed result |
| prototype_audit | Server-generated actor/action/resource/time/correlation; no client writes/updates/deletes; redacted payload hashes |
| prototype_outbox | Created in business transaction; stable effect key, attempts, bounded retry, lease owner/expiry and fencing token |
| prototype_webhook_events | Unique provider/account/event; verified raw-body signature and payload hash |
| prototype_payment_effects | Unique provider/account/payment identity; expected order/currency/amount mapping; no duplicate ledger mutation |
| prototype_refund_requests | Tenant/order/requester immutable; authenticated human decision bound to exact request; no payout adapter |
| prototype_agent_grants | Issued through trusted non-agent authority; exact source/tool/actor/endpoint/model/credential/expiry/max invocation binding |
| prototype_budget_reservations | Atomic reservation with unique grant/effect ID; conservative max-cost debit; no optimistic release after ambiguous call |

The JSON contract describes proposed application routes, not Xano Metadata API
paths. Actual route IDs, API group, schema syntax and import format require a
workspace export and Developer MCP validation. No generated XanoScript is
claimed valid without that validation. Do not download mutable latest CLI/MCP
packages during CI or grant an unreviewed executable a token. Inspect and pin
selected official package version/integrity, installed capabilities and plan
before authenticated use.

### Atomic assignment transaction

1. Authenticate first. Resolve tenant, account and dispatcher capability from
   the verified server identity. Reject caller-supplied authority fields.
2. Begin database transaction; check/claim tenant/actor/action/idempotency key.
   Same committed payload returns the same result; changed payload returns 409.
3. Acquire order and vehicle locks in a stable order. Re-evaluate eligibility
   inside this transaction. A preliminary eligibility check is advisory only.
4. Insert active assignment under BOTH unique constraints. Transition through
   the reviewed equivalent of transition_order, never a generic status patch.
5. Append audit and outbox rows, persist idempotent result, commit together.
   Unique conflict or injected failure rolls back ALL effects. No read-then-write
   check without database atomicity is acceptable. No external API inside this
   transaction is assumed reversible.

If Xano cannot express/verify these database guarantees for the selected plan,
stop the migration decision. An in-memory lock or single-worker demonstration
cannot substitute for concurrent multi-request database enforcement.

### Tenant/participant isolation

Authentication is not authorization. Every read/write, list/filter, nested
response, realtime subscription, scheduled task and agent tool must enforce
both tenant and participant/capability restrictions. An assigned vendor sees
only permitted operational fields, not unrelated customer/vendor profiles.
Test transport companies explicitly acting as customer versus vendor. Ignore
body/query tenant, actor, role and approval flags; never forward metadata/admin
tokens to clients. Review exported CRUD endpoints and Metadata API privileges
as separate administrative surfaces. Xano authentication is not proof of
PostgreSQL RLS equivalence; this is a migration acceptance gap.

### Recovery and external effects

Persist outbox work in the same transaction as assignment. Claim with an atomic
lease plus monotonic fencing generation, bounded attempts/backoff, terminal
failure and manual recovery. Test interruption before commit, after commit
before delivery, after external success before acknowledgement, and stale
worker resumption. The local oracle covers rollback, durable restart and
lease-token replacement only; remaining external-effect/fencing cases require
Xano proof. Delivery is at least once; recipients need stable idempotency keys.
Never claim exactly-once delivery from a queue or local transaction alone.

### Refund and agent limits

A request is not approval and approval is not execution. Human approval must
come from an authenticated owner session with protected role issuance; agents
cannot submit a role flag to approve. Reject self-approval and stale/changed
request binding. The oracle records approval only, never refund execution.

Trusted grants and budgets are server-managed, inaccessible to agent writes.
Bind grant to source, actor/tool, approved endpoint/model and credential,
limits, expiry and one use. Reserve worst-case cost atomically before dispatch;
a retry or ambiguous result cannot silently release/reuse the reservation.
Local synthetic units are NOT money and NOT a provider-enforced hard cap.
Actual token pricing, provider cap, credentials, circuit breaker and revocation
remain pending. DeepSeek and Qwen are never contacted by this prototype.

## Acceptance and remaining gaps

| Owner requirement | Local reference coverage | Required Xano evidence |
|---|---|---|
| No double assignment | Two orders/one vehicle; two vehicles/one order; duplicate races | Concurrent authenticated HTTP requests, actual unique indexes/locks, exact winning rows/audit |
| Customer/vendor isolation | Cross-tenant/account/role and unassigned-vendor denials | Verified tokens, all API/list/realtime/tool surfaces, field-level responses |
| No duplicate finance effects | Signed synthetic events; event/payment/order conflicts; concurrent replay | Real adapter protocol in test mode, currency/amount/order mapping, no payout |
| Interruption recovery | Atomic rollback/retry, reopen store, expired/stale leases | Actual worker termination/restart, post-effect ambiguity, bounded retries/fencing |
| Manual refunds | Customer request; distinct human approval; agent denial | Actual human auth/role issuance, decision binding/revocation; no live refund |
| Agent/budget/audit enforcement | Wrong endpoint/model/tenant/expiry denied; one-use and cap races | Protected grant/budget storage, authentic audit, monetary cap, credentials and revocation |

The six local invariants are NOT a port of all 72 existing database tests:
core order/worker 2, dispatch 31, finance 23, payment-intent privileges 4,
governance 12. Every case needs a source identifier, invariant, Xano replacement
or explicit reviewed disposition, real execution evidence and cleanup. Preserve
the original PostgreSQL tests and CI as the reference. No gap is closed by
renaming a mocked or SQLite test. Backup/export/restore, retention/redaction,
residency, plan/compute/task limits, geographic/realtime performance, migration
rollback, stable frontend contracts and total operating cost also remain open.

## Connection handoff — next dependency

Repository-only preparation can complete without a Xano secret. To continue:

1. Supply nonsecret instance URL, disposable workspace ID/name, branch/data
   source ID and confirmation that it contains synthetic data only. Confirm
   its database is separate from any production branch/data source.
2. Connect the official Xano developer integration in the development
   environment, or securely install a dedicated expiring development/Metadata
   token outside chat/repository/logs. Use workspace-restricted permissions if
   supported; otherwise use a separate disposable account/workspace and record
   the broader scope as a blocker pending review. Do not provide an account-wide
   production administrator token. A data-plane API auth token alone may not
   permit schema/endpoint management.
3. Verify token identity/scope, exported baseline, available syntax/transaction
   capabilities and plan limits before writing. Obtain only the metadata needed;
   no whole-account exports, production rows or provider keys.
4. Prepare and platform-validate XanoScript against that export. Present the
   exact namespaced diff for review, then perform the bounded synthetic install
   and HTTP acceptance run under its own recorded scope. No production promote.
5. Retain private raw evidence and sanitized source/platform/run/test/cleanup
   hashes. Remove only ledger-owned prototype resources or revoke its dedicated
   token. Never delete a shared workspace/database or use a broad reset.

A later GitHub job, if needed, must be manual owner/main/exact-SHA/expiry bound,
with pinned verified actions, contents-read, a dedicated Xano staging environment,
no Production/provider secrets, bounded execution and sanitized private evidence.
This PR adds only offline checks to the existing five-job CI; no secret workflow.

## Verification commands

Run from repository root:

```
python3 -m unittest discover -s prototypes/xano/tests -v
python3 -m ruff check --config workers/pyproject.toml prototypes/xano
python3 -m ruff format --check --config workers/pyproject.toml prototypes/xano
```

No network, Docker, provider or external database is used by this suite.

## Official sources checked on 17 October 2026

- https://www.xano.com/developers/ — official code/sandbox/export workflow;
  platform availability and plan entitlement still need workspace verification.
- https://github.com/xano-inc/xano-developer-mcp — official tooling provenance;
  no package installation or token grant performed.
- https://www.xano.com/learn/connecting-xano-realtime-with-bubble/ — native
  WebSocket realtime exists; do not add another broker without measured need.

The uploaded assessment PDFs are proposal inputs, not proof of compatibility,
plan entitlement, performance, security controls or successful migration.
