# M3 Deterministic Operational Core Report

## Scope and Result

**Task:** `M3-CORE`

**Baseline:** `a5b7048277a39336f0b7904702186736fc9f5ce9`

**Execution date:** 2026-09-10
**Result:** COMPLETE in network-isolated disposable test environments; not deployed.

M3 replaces the legacy fail-open Supabase REST path with a deterministic FastAPI/PostgreSQL command boundary. It implements typed order intake, database-resolved authorization, test-only versioned Decimal pricing, transition-RPC use, atomic idempotency, PostgreSQL tasks/outbox workers, bounded retries, stale-lease recovery, dead letters, operational exceptions, health/readiness, stable errors, exact dependency locks, and isolated integration evidence.

No production database, live credential, payment service, Odoo, Paperclip, Hermes, n8n, agent, DNS, proxy, firewall, or system service was accessed or changed. Pricing and JWT authentication are explicitly limited to test/development configuration; no production rate schedule or identity provider was invented.

## Command Boundary

- `POST /api/v1/orders` validates stops, cargo, service requirements and timezone-aware pickup commitment; returns `202`, `order_id`, `workflow_id`, correlation ID and replay state.
- A signed test JWT contributes only `sub`. Platform, active account status, roles and customer profile are resolved from PostgreSQL inside the request transaction.
- Intake atomically writes the idempotency claim/result, immutable quote evidence, pending order, two stops, customer participant, pickup commitment, durable task, operational event and outbox event.
- Identical key/payload requests return the original order/workflow and correlation; key reuse with changed input returns `409` without duplicate state.
- `POST /api/v1/orders/{order_id}/transitions` authorizes a participant or admin and calls only `zippy.transition_order()`. Direct order-status mutation is unchanged and remains database-denied.
- Errors use a stable envelope with code, message, correlation ID and retryability. Database/internal errors are sanitized.

## Deterministic Policy

Pricing uses exact `Decimal` arithmetic, explicit base/per-kilometre/per-kilogram inputs, half-up currency rounding, an immutable policy version and a SHA-256 input-evidence hash. Configuration accepts only a `test-*` policy version and test/development JWT adapter. Hazardous cargo and return-trip pricing are rejected because no approved production policy exists.

The API does not approve, dispatch, charge, settle, post to Odoo or invoke governance/agent systems. Order creation starts at `pending`; later state changes remain constrained by the database transition table and RPC.

## Reliability

Migration `0005_core_runtime` adds mandatory 24-hour idempotency expiry and safe outbox lease, attempt, completion, retry and dead-letter functions. Durable-task claims now consume attempts, including stale processing-lease recovery, so repeated worker crashes cannot loop forever. Both task and outbox failures use bounded exponential backoff; terminal failures persist dead-letter evidence and an operational exception for human handling.

All work remains in PostgreSQL transactions and queues. No Temporal, Celery, Redis, Kafka or external broker was added.

## Reproducibility

- Direct API runtime and development manifests use exact versions.
- `requirements-api.lock` and `requirements-api-dev.lock` contain exact transitive versions and SHA-256 hashes.
- Both locks installed successfully with `pip --require-hashes` in fresh disposable virtual environments.
- `Dockerfile.api` installs only the runtime lock and pins `python:3.12-slim` to `sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea`.
- The pinned image build completed successfully; no image was pushed or deployed.

## Verification

| Gate | Result |
|---|---|
| Host unit/API contract tests | PASS: 18 passed, 2 isolated-DB tests skipped as designed |
| Full restricted-login M3 proof | PASS: 19 passed |
| Order intake/replay/conflict/atomic record counts | PASS |
| Blocked and cross-customer denial; admin transition | PASS |
| Legal/illegal transition and transition replay | PASS |
| Task/outbox success, retry exhaustion, dead letters and exceptions | PASS |
| Network isolation, schema down, role teardown and cleanup | PASS |
| Ruff | PASS |
| Strict mypy | PASS: 8 production modules |
| Runtime/dev hash-locked fresh installs | PASS |
| Pinned API image build | PASS |
| Canonical M2 migration/security/concurrency regression | PASS |

The full proof used PostgreSQL `16.15 (Debian 16.15-1.pgdg13+2)` from `postgres@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94`, Docker network mode `none`, no published port, a private temporary Unix socket, a read-only repository mount, generated unrecorded credentials and synthetic `.invalid` identities. The container, volume, socket directory, schema and managed roles were removed.

## Deferred Production Decisions

M3 evidence proves the deterministic core in disposable environments only. Production remains blocked pending an approved identity provider, production pricing policy, deployment route, secrets, monitoring, backup/restore evidence and later milestone approvals. `M4-OPERATIONS-FINANCE` remains blocked and was not activated.

## Proof Status and Deployment-Prevention Correction

Owner-authorized narrow correction on 2026-09-10, retaining baseline `a5b7048277a39336f0b7904702186736fc9f5ce9` on `master` and all pre-existing M3 work. The original harness, application, migrations, locks, Dockerfile and tracker were not changed.

Invoke the existing isolated proof through:

```bash
bash db/zippy/scripts/run_m3_core_proof_logged.sh
```

The wrapper invokes Bash directly with stdout/stderr redirected to a private temporary log, immediately captures the harness status, records `harness_exit_code`, displays an allowlisted diagnostic tail of at most 60 source lines, and exits with the original status even if log display fails. It disables tracing and uses `umask 077`: log directories are mode `700`, logs mode `600`. Logs remain outside Git for restricted local diagnosis; do not publish their raw contents. No harness-to-tail/tee pipeline is used. The existing isolation and cleanup controls remain unchanged.

Before the real run, `bash db/zippy/scripts/run_m3_core_proof_logged.sh --self-test` returned the expected `37`. A second probe with an exported `tail` function returning `88` still returned `37`. Neither probe ran the harness or accessed Docker/databases.

Exactly one real proof ran from `2026-09-10T12:46:46.278618+00:00` to `2026-09-10T12:46:54.613978+00:00`. Both the captured harness status and observed wrapper status were `0`. The safe log summary was **20 passed, 2 warnings**; all nine harness PASS markers, including network isolation and cleanup, were present. Warning details were not classified in this correction. The earlier 19-test report and previous attempts above are preserved as historical records; this new observation supplies the current count, not a silent rewrite of earlier evidence.

Private log: `/tmp/zippy-m3-proof-log.O2xfnOs1/proof.log`; SHA-256: `3b7b209bd5460ef9b0e129e399e69f6b5ab1b41ee9e339eb8b133925d5fe183b`. This temporary log is not durable archival evidence.

A read-only inotify observer captured the socket creation during the run. Container and volume names were derived from that exact harness suffix and checked by exact equality against successful Docker inventories after exit; the full socket path was checked for absence:

| Resource | Exact name/path | Post-run result |
|---|---|---|
| Container | `zippy-m3-disposable-20260910124646-e9b43df5` | Absent |
| Volume | `zippy_m3_disposable_20260910124646_e9b43df5_data` | Absent |
| Socket directory | `/tmp/zippy-m3-socket-20260910124646_e9b43df5.vEe6rH` | Absent |

The sole deployment-capable job, `deploy`, in [.github/workflows/deploy-hostinger.yml](../../.github/workflows/deploy-hostinger.yml) now has unconditional job-level `if: ${{ false }}` and an authorization comment. Static YAML parsing and assertions confirmed this gate on every job. The workflow invokes inline commands and no local deployment scripts/actions. Its existing definition and missing production Compose reference were retained, not executed or replaced.

**This local workflow change does not protect the remote branch until committed and pushed.** Neither action was performed. GitHub environment protection and required reviewers remain **NOT VERIFIED**. No workflow dispatch, ServerAvatar call, environment/secret configuration, production deployment or tracker transition occurred. This correction does not resolve other review findings or authorize M4.
## M3 Hardening Correction (2026-09-10, second authorized pass)

Baseline unchanged: `a5b7048277a39336f0b7904702186736fc9f5ce9` on `master`; all prior M3 work and the deployment block preserved. No commit or push.

### Non-root API image

`Dockerfile.api` now creates fixed system identity `10001:10001` (`zippy`) and switches to it via `USER 10001:10001` before `CMD`. Package installation remains root during build; no `/app` ownership change (runtime needs no writable app paths; `PYTHONDONTWRITEBYTECODE=1`). Evidence: `docker build -f Dockerfile.api -t zippy-api:m3-hardening .` exited `0`; `docker image inspect` reports `configured_user=10001:10001`; isolated `docker run --rm --network none --entrypoint id` printed `uid=10001(zippy) gid=10001(zippy)`. This verifies the image configuration and an isolated container identity only; it is not a deployed-runtime claim.

### Disposable socket hardening

The proof harness replaces `chmod 0777` on the private socket directory with: resolve the pinned image's `postgres` UID/GID (`999:999`), `chown 999:999`, `chmod 0700`. The image entrypoint broadens the bind-mounted `/var/run/postgresql` to `3775` during startup, so the harness re-applies `0700` after readiness and asserts permission bits (this host's filesystem preserves the access-neutral setgid bit; recorded mode is `2700` = `rwx------` plus setgid). Host pytest and `docker exec` run as root and retain access.

Authentication finding: the pinned postgres image's initdb enables **`trust` for local socket connections by default**. The harness now sets `POSTGRES_INITDB_ARGS=--auth-local=scram-sha-256` (strengthened, not weakened; no network exposure added) and asserts `password_encryption=scram-sha-256` and `pg_hba_file_rules` local auth `scram-sha-256`. A targeted disposable probe of the same image/env confirmed effective rules `local all all scram-sha-256`; the initdb trust warning text is stale relative to the effective configuration. The host pytest connection string now carries the generated ephemeral password (never recorded).

Recorded effective evidence from the passing run: `socket_dir_mode=2700`, `socket_file_mode=777`, `password_encryption=scram-sha-256`, `pg_hba_local_auth=scram-sha-256`.

### Negative local-user connection

`negative_local_user=PASS`: an unrelated non-root identity (`nobody`, uid 65534, via `setpriv`, no host account changes) could not connect through the hardened socket. Existing host identity and tooling were used; nothing was created or modified.

### Cleanup-result status handling

New `db/zippy/scripts/verify_m3_cleanup.sh` computes the combined result: a failing proof status is always preserved; a successful proof with failed exact cleanup verification exits `1`. The logged wrapper invokes it after a successful proof using the exact resource names the harness now prints. Harmless probe matrix (no real proof rerun):

| Proof | Cleanup | Expected | Actual |
|---|---|---|---|
| fails (37) | passes | 37 | 37 PASS |
| succeeds (0) | fails | 1 | 1 PASS |
| fails (37) | fails | 37 | 37 PASS |
| succeeds (0) | passes | 0 | 0 PASS |

Wrapper `--self-test` still propagates `37`, including a tail-failure variant.

### Redaction/security tests

New `api/tests/test_output_redaction.py` (host-only, 5 tests): invalid bearer token not echoed in 401; valid JWT and JWT secret absent from 503 error body; sensitive `postgresql://user:password@host` payload value absent from 422 validation details; poisoned `DATABASE_URL` and password absent from generic 500; config validation errors do not echo secret values. The M3 application defines no logging sinks; no logging was added as a test target. `api/tests/test_postgres_integration.py` additionally asserts dead-letter/exception persistence stores only exception class names (`RuntimeError`, `TypeError`) and never the sensitive message "synthetic failure details must not escape". No obsolete Supabase/Paperclip/Hermes tests restored.

### Results

- Host unit suite: **23 passed, 2 skipped** (isolated-DB guards), 2 known dependency deprecation warnings — classified deferred (FastAPI/Starlette TestClient httpx shim; AnyIO `BlockingPortal` alias). Not suppressed; locks unchanged.
- Hardened isolated proof via wrapper: `harness_exit_code=0`, `final_exit_code=0`, `cleanup-verification=PASS`, pytest **25 passed, 2 warnings**. Private log `/tmp/zippy-m3-proof-log.nMP56NHB/proof.log` (mode 600), SHA-256 `9217f3483147b40b95492d18fae604d055975b45cf7ab9469a0034140f344786`.
- Failed intermediate attempts are retained honestly: run 1 (`mwACrOfD`) failed on the trust-auth assertion (root-caused; led to `--auth-local=scram-sha-256`); run 2 (`UruMWWVE`) failed on an over-strict new dead-letter class-name assertion (`TypeError` from the deliberately mis-signed transport stub is expected); run 3 (`mdEv5lw5`) passed functionally but recorded entrypoint-broadened `socket_dir_mode=3775` and an unclassified negative probe ("no password supplied" now a classified PASS). No failure was retried blindly.
- M2 regression: **not required** — shared bootstrap/harness files (`roles.sh`, `migrate.sh`, `run_isolated_proof.sh`) and migrations 0001–0004 are untouched by this pass (verified by `git diff --name-only`); only M3-specific scripts changed. The pre-existing `manifest.tsv` modification predates this pass.
- Exact residue check after the passing run: container `zippy-m3-disposable-20260910132938-1f21aa54` absent; volume `zippy_m3_disposable_20260910132938_1f21aa54_data` absent; socket `/tmp/zippy-m3-socket-20260910132938_1f21aa54.cffp31` absent; no zippy/probe containers remain.

Production remains blocked; nothing deployed; the deployment job stays locally disabled (`if: ${{ false }}`), and this unpushed local change does not protect the remote branch. External GitHub environment protection remains NOT VERIFIED.

## Tracker Handoff

The Verification table above retains its original historical counts; the final current counts are the hardened results recorded in the correction sections: host suite **23 passed, 2 skipped**; isolated proof **25 passed, 2 warnings** (deferred dependency deprecations).

At the M3 pre-commit acceptance audit, `M4-OPERATIONS-FINANCE` was the sole task whose tracker dependency (`M3-CORE`) is complete, so it became the sole `IN_PROGRESS` tracker row following the established handoff convention. It is explicitly not begun; its authorized scope remains empty and product, finance, and Odoo owner approvals are still required before any M4 work. The audit found no post-proof drift in executable M3 code, harness, migrations, Dockerfile, or tests, so no proof rerun was required.
