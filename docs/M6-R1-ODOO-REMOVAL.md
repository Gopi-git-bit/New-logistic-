# M6-R1: Remove Mandatory Odoo Runtime Integration

Date: 2026-10-08. Branch: `feat/m6-r1-remove-mandatory-odoo`.
Baseline: `e93a7dd0c8bd465a2ca0597096301a7a697b5aa5`.
Status: separately owner-authorized, prepared for draft review; not deployed.

## Authority and Unchanged Boundaries

This change removes only mandatory Odoo integration. It does not approve the combined D-33 proposal, remove Paperclip, migrate hosting, complete M6, authorize M7, or authorize production activation. The pre-existing combined proposal and pending-decision worktree edits are deliberately excluded from this commit and preserved separately. Approved D-13 is unchanged.

Paperclip startup, governance grants, authorization/RLS, audit, order state-machine RPCs, pricing and durable retry controls remain unchanged. Deterministic vehicle delegation and driver assignment remain autonomous within their existing authorization limits; no human dispatch gate is added. Settlement eligibility/authorization rules are unchanged, with no new blanket manual approval gate. Every refund retains existing manual approval and no self-approval. POD gates remain enforced.

Signed provider webhook ingestion reconciles evidence only; it does not initiate Razorpay payments or refunds. Real provider execution remains unavailable. Missing webhook configuration still returns `503 WEBHOOK_NOT_CONFIGURED`; fake providers remain test-only and no production success is fabricated.

## Implementation and Review

- [api/repositories_finance.py](../api/repositories_finance.py) preserves payment evidence, projection, requested finance state, audit and outbox while removing automatic `odoo_draft_sync` enqueue. The historical `draft_customer_invoice` type and `odoo:draft_customer_invoice:{order_id}` key are retained for schema and replay compatibility, not as proof of an invoice.
- [api/worker_finance.py](../api/worker_finance.py) removes ERP adapter execution. Its compatibility handler always raises `OdooIntegrationUnavailable` / `ODOO_INTEGRATION_REMOVED`, with existing durable retry/dead-letter handling and no request acknowledgement or external-reference creation.
- [workers/src/zippy_workers/handlers.py](../workers/src/zippy_workers/handlers.py), [workers/src/zippy_workers/kernel.py](../workers/src/zippy_workers/kernel.py), [workers/src/zippy_workers/config.py](../workers/src/zippy_workers/config.py) and [workers/src/zippy_workers/capabilities.py](../workers/src/zippy_workers/capabilities.py) remove payment-triggered ERP enqueue, ERP client/handler registration, worker settings and ERP capabilities.
- [docker-compose.yml](../docker-compose.yml) removes API/worker Odoo environment wiring; the retained ERP service is opt-in through `legacy-odoo`, and its volume is retained. Tracked environment examples and CI no longer require Odoo credentials. Other hosting services are unchanged.
- Historical clients, adapter contract tests, immutable migrations, ERP columns/references and prior evidence remain intact. The retained generic Hermes client has no application caller; Paperclip's synthetic executor is explicitly not real ERP execution. No active API/worker path schedules or executes Odoo work.
- Final review found API CI omitted the PostgreSQL driver used during test collection. [.github/workflows/ci.yml](../.github/workflows/ci.yml) now installs canonical pinned API development requirements and runs the affected API/Paperclip and worker suites. No assertions were weakened and no skip conditions were added.

## Retired-Task Handling Plan

No live queue has been inventoried, modified, deleted or replayed. Before any separately authorized rollout, stop old ERP consumers and inventory queued, claimed, retrying and terminal work with linked requests, correlation IDs, historical external references and actual ERP evidence. Timeout-after-success remains unresolved until evidence is reconciled.

Prefer an explicitly authorized hold that preserves all evidence. No new hold status/RPC or migration is introduced. If consumed by this implementation:

- Canonical `odoo_draft_sync` tasks fail through existing retries and `dead_lettered` state, retaining DLQ and operational-exception evidence.
- Legacy `push_order_to_odoo` tasks fail with `no_handler:push_order_to_odoo`, requeue until the existing attempt limit, then become `dead`. They are never completed or charged as successful work.

Never mark retired tasks executed/succeeded, acknowledge invoices, invent ERP references, trigger refunds/settlement, discard records, or replay them through old consumers. Resolution or a future adapter transition requires separate authorization, idempotency and audit.

## Exact Local Results

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/workers/src:$PWD" .venv/bin/python -m pytest api/tests api/tests_m4 api/tests_m5 workers/tests -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 ZIPPY_M4_PYTHON="$PWD/.venv/bin/python" bash db/zippy/scripts/run_m4_finance_proof.sh
```

- Host regressions: **216 passed, 72 skipped, 2 warnings in 1.57s**. Warnings: unknown `asyncio_mode` option and Starlette/httpx deprecation.
- Fresh disposable proof: **118 passed, 1 warning in 9.03s** on PostgreSQL 16.15. Warning: Starlette/httpx deprecation. Network isolation, SCRAM authentication, negative local-user access, migration rollback, role teardown and container/volume/socket cleanup passed.
- Pinned image: `postgres@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94`. Only a fresh disposable database received synthetic mutations/migrations; no shared database was used.
- Tests cover captured-payment amount/currency/state, receipt replay without additional effects, finance-request persistence without ERP enqueue, capability denial, unregistered legacy work, unavailable canonical work, retries/DLQ, authorization, refund approval and POD/settlement gates. Full worker lint and touched-file lint passed.

The 72 host skips are database-gated, not waived failures. The disposable proof exercises API/M3/M4 SQL tests, including payment-intent privileges and dispatch, but does not exercise M5 Paperclip SQL integration. The M4 finance client reuses the existing test-only Paperclip pool stub; host Paperclip route/service/envelope regressions pass. Live Paperclip/provider connectivity, production auth, historical queue resolution and production readiness remain unverified.

## Publishing Safety

The remote default branch matches the baseline. CI runs on pull requests targeting `master`/`main`; feature-branch pushes do not match its push filter. The Hostinger workflow is manual-only and its deployment job is disabled with `if: ${{ false }}`; it is not modified or dispatched. GitHub's historical frontend CI entry has no workflow file on the current default branch. The inspected repository webhook is an Apidog push hook, not a deployment hook.

Publication is a feature-branch push and draft PR only. No merge, deployment, secret change, live-queue mutation or shared-database migration is authorized. Remote CI results belong in the draft PR handoff and must not be represented by the local results above.