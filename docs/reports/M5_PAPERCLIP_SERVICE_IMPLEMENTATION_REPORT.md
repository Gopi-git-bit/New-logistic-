# M5-B Paperclip Governance Service Implementation Report

**Status: ACCEPTED — COMPLETE**

## Scope

This report covers the Minimal MVP M5-B authenticated Paperclip governance service implemented in `/opt/new-logistic` under D-29 owner approval. The work is strictly limited to the authorized boundary:

- Only the twelve D-28 privileged functions are used.
- No new migrations, roles, grants, or direct Paperclip table access.
- No GET / read-status endpoints.
- Server-controlled identity mappings for agents, owner approver, executor, tenant, and policy.
- Synthetic executor for disposable tests only.
- No modification of `/opt/paperclip`, `docker-compose.yml`, deployment configuration, or external systems.

## What Was Implemented

| Component | Path | Purpose |
|---|---|---|
| Models | `api/models/paperclip.py` | Pydantic request/response schemas for all 12 operations |
| Repository | `api/repositories_paperclip.py` | Invokes only the 12 D-28 privileged functions |
| Envelope signer | `api/services/paperclip_envelope.py` | Server-signed HMAC-SHA256 grant envelopes with canonical JSON, constant-time verification, max 300s TTL |
| Synthetic executor | `api/services/synthetic_executor.py` | Fake executor that consumes a grant and records a SUCCEEDED attempt for tests |
| Service facade | `api/services/paperclip.py` | Auth, identity resolution, proposal/grant lifecycle, loop guard, budget checks |
| Routes | `api/routes_paperclip.py` | FastAPI POST routes for all 12 operations; no read-status endpoints |
| Main wiring | `api/main.py` | Registers Paperclip routes, initializes PaperclipDatabase pool, readiness checks both pools |
| Database pool | `api/database.py` | Separate `PaperclipDatabase` pool distinct from Zippy pool; no `wait=True` |
| Configuration | `api/config.py` | M5-B settings with `SecretStr` redaction and defaults |
| Environment template | `.env.example` | Documents `PAPERCLIP_*` variables |
| Unit/integration tests | `api/tests_m5/` | 46 collected; 34 passed on host, 12 integration/security/concurrency tests require the disposable proof |
| Regression tests | `api/tests/` | Existing 56 pass; 2 skipped |
| Proof script | `db/paperclip/scripts/run_m5b_service_proof.sh` | Disposable-only integration proof runner (recovery in progress) |

## Key Design Decisions

- **No direct table access.** The repository calls only the functions defined in `db/paperclip/migrations/0001_governance.up.sql`.
- **Server-controlled mappings.** `PAPERCLIP_AGENT_BINDINGS_JSON` maps external JWT subjects to Paperclip agent UUIDs; owner and executor subjects are configured separately.
- **Fail-closed service.** Missing identity, invalid envelope, exhausted budget, loop guard, policy checksum mismatch, and unavailable governance database all reject.
- **POST-only contract.** All governance operations are state mutations; status lookup is intentionally omitted.
- **Idempotency.** Every mutation path accepts an idempotency key.

## Validation Results

### Lint

Command:

```bash
ruff check api/routes_paperclip.py api/services/paperclip.py \
  api/services/paperclip_envelope.py api/services/synthetic_executor.py \
  api/repositories_paperclip.py api/models/paperclip.py api/tests_m5/ \
  api/database.py api/config.py api/main.py
```

Result: **All checks passed.**

### Host Tests

Command:

```bash
python -m pytest api/tests/ api/tests_m5/ -q
```

Result:

```
74 passed, 3 skipped, 1 warning
```

- `api/tests/`: 56 passed, 2 skipped.
  - `api/tests/test_postgres_integration.py::test_order_transition_and_worker_flow` — requires the isolated M3 PostgreSQL proof.
  - `api/tests/test_postgres_integration.py::test_task_and_outbox_terminal_failures_create_evidence` — requires the isolated M3 PostgreSQL proof.
- `api/tests_m5/`: 18 passed, 1 skipped.
  - `api/tests_m5/test_integration.py::*` — requires the private M5-B disposable PostgreSQL proof.

### Integration Proof

One fresh disposable proof was executed on 2026-09-27 and passed. The harness created a network-isolated, socket-only, SCRAM-authenticated PostgreSQL container using the same pinned image as M5-A, bootstrapped the existing Paperclip roles, applied the existing M5-A migration, loaded synthetic fixtures, ran the existing M5-A security/concurrency regression, and executed all M5-B integration/security/concurrency tests. Cleanup succeeded (`exact_cleanup=PASS`, `host_port_5432=PASS`).

A previous attempt (`M5-B-F001`) exposed a `PaperclipRepository.acquire_decision_lock` composite-result defect; that was corrected to `SELECT * FROM paperclip.acquire_decision_lock(...)`. A subsequent harness-interface attempt (`M5-B-F002`) showed that the harness requires `M5B_PROOF_LOG` as an environment variable; this pass used the exact required calling pattern.

Final proof result:

- Test: `api/tests_m5/test_integration.py::test_missing_approval_rejection_lock_invariant_and_revocation`
- Exception: `api.repositories_paperclip.GovernanceDenied: GOVERNANCE_RESULT_MISSING`
- Root cause: `PaperclipRepository.acquire_decision_lock` used `SELECT paperclip.acquire_decision_lock(...)` instead of `SELECT * FROM paperclip.acquire_decision_lock(...)`, so psycopg returned a single composite column instead of a dict row matching the expected `governance_result` shape.

Passing markers before failure:

- `network_isolation=PASS`
- `socket_scram=PASS`
- `m5a_security_regression=PASS`
- `bootstrap_and_fixture_reset=PASS`
- `m5b_concurrency=PASS successes=1 denials=1` (concurrent grant consumption produced exactly one success)
- 45 M5-B tests passed before the failing test.

After the two failure records were captured, the defects were corrected and a final proof was executed successfully. See the success record below.

## Success Record

### M5-E011: M5-B Disposable Service Proof — PASSED

| Field | Value |
|---|---|
| Proof date | 2026-09-27 |
| Harness | `db/paperclip/scripts/run_m5b_service_proof.sh` |
| Private log | `/tmp/m5b-proof.Ceyqku` |
| Log mode | `0600` |
| Log bytes | `24551` |
| Log SHA-256 | `7a33b36dd7513011006c5176fc48df70610417a9d0d2f2fe2ec24b6b4039463f` |
| Exit status | `0` |
| Disposable tests | `46 passed, 0 skipped, 1 warning` |
| Markers | `network_isolation=PASS`; `socket_scram=PASS`; `m5a_security_regression=PASS`; `bootstrap_and_fixture_reset=PASS`; `m5b_tests=PASS count=46 skipped=0`; `m5b_integration_security=PASS`; `m5b_concurrency=PASS successes=1 denials=1`; `security=PASS`; `rollback=PASS`; `reapply=PASS`; `host_port_5432=PASS`; `exact_cleanup=PASS`; `secret_scan=PASS` |
| M5-A regression | `verify.sql` PASS, `verify_security.sql` PASS, `verify_concurrency.sql` PASS |
| Concurrency | Exactly one successful consumer; one denial; one execution attempt recorded |
| Secret scan | `secret_pattern_matches=0` |
| Cleanup | Zero disposable containers, volumes, socket directories, environment files; no host port-5432 listener |

## Failure Record

### M5-B-F002: Disposable Proof Failed — Harness Requires `M5B_PROOF_LOG` Environment Variable

| Field | Value |
|---|---|
| Proof date | 2026-09-27 |
| Harness | `db/paperclip/scripts/run_m5b_service_proof.sh` |
| Private log | `/tmp/m5b-proof.nUQJfw` (mode 0600, 117 bytes, SHA-256 `547ec049e82195db1eaa939e3e7422f4e7c120dc7e52d55c5987732b4f26b1e8`) |
| Exit status | 1 |
| First failure | Harness interface: `M5B_PROOF_LOG: caller must supply the private proof log path` |
| Error | The script sources `${M5B_PROOF_LOG:?caller must supply the private proof log path}` before it can run; simple shell redirection is insufficient. |
| Corrective action required | Invoke the harness with `M5B_PROOF_LOG=/path/to/log` exported in the environment, then redirect stdout/stderr to that same path. |
| Status | M5 IN_PROGRESS; M5-E011 not created; proof not retried. |

### M5-B-F001: Disposable Proof Failed — `acquire_decision_lock` Result Shape

| Field | Value |
|---|---|
| Proof date | 2026-09-27 |
| Harness | `db/paperclip/scripts/run_m5b_service_proof.sh` |
| Private log | `/tmp/m5b-proof.log` (mode 0600, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` — empty because the original harness wrote output to stdout; the harness has since been corrected to append to the log) |
| Exit status | 1 |
| First failure | `api/tests_m5/test_integration.py::test_missing_approval_rejection_lock_invariant_and_revocation` |
| Error | `GOVERNANCE_RESULT_MISSING` in `PaperclipRepository.acquire_decision_lock` |
| Corrective action | Changed `SELECT paperclip.acquire_decision_lock(...)` to `SELECT * FROM paperclip.acquire_decision_lock(...)` in `api/repositories_paperclip.py`; corrected the proof harness to append output to the supplied private log. |
| Status | M5 IN_PROGRESS; M5-E011 not created; proof not retried. |

## Implementation Baseline

- Commit baseline for M5-B: `cd786b91e40598a9d1e66c7501669e0ec28ac0cb` (uncommitted changes recorded).
- D-29 owner approval recorded in `docs/DECISIONS.md`.
- D-28 privileged function boundary unchanged.

## Limitations

- M5-B is limited to disposable development/synthetic tests per D-29.
- Live executor integration with Zippy/Odoo/Razorpay is not authorized.
- Production deployment, live credentials, and autonomous financial execution remain prohibited.

## Evidence IDs

- M5-E009: D-29 M5-B owner boundary approval (pre-existing).
- M5-E010: M5-B Host Validation.
- M5-E011: M5-B Disposable Service Proof — PASSED.
- M5-E012: Owner Acceptance and M6 Discovery Handoff.

## Acceptance

M5-PAPERCLIP was owner-accepted on 2026-09-27 by Gopinathan under `D-30` (`docs/DECISIONS.md`).
The accepted scope includes:

- M5-A isolated governance database (`520e8f48003e98166c029366943798e08bc042a3`, evidence `M5-E008`).
- M5-B authenticated governance service (`e3a96d97ec9c04a88d8561e69397ae8c7b896ea7`, host evidence `M5-E010`, disposable proof `M5-E011`).

The disposable proof passed with `46 passed, 0 skipped, 1 warning`, proof-log SHA-256 `7a33b36dd7513011006c5176fc48df70610417a9d0d2f2fe2ec24b6b4039463f`, successful single-use concurrency enforcement, M5-A security regression, rollback, reapply, secret scanning, network/socket isolation, and exact cleanup. Host validation result: `90 passed, 14 skipped, 1 warning`.

This acceptance does not authorize production deployment, live credentials, live integrations, autonomous financial execution, unrestricted Paperclip execution, changes to Zippy or Odoo data ownership, or modification of `/opt/paperclip`. `M6-LANGFUSE` is the sole `IN_PROGRESS` task, restricted to discovery and boundary definition only.

## Operator

GitHub Copilot.

## Recovery inventory and scope reconciliation

Nothing staged; no unrelated user changes identified. All changed and untracked paths are attributable to M5-B. No dependency, lock, manifest, migration, role/grant, deployment, compose, or production file changed. M5-A protected files remain byte-identical to commit `520e8f48003e98166c029366943798e08bc042a3`.

- `api/services/paperclip_envelope.py` is necessary: it implements the versioned `m5b-v1` HMAC envelope, canonical JSON serialization, constant-time HMAC comparison, and bounded lifetime enforcement required for D-29 identity/payload binding. Retained and hardened.
- `api/tests_m5/test_service.py` is necessary: sixteen authorized unit/service tests consolidate coverage for identity resolution, owner authorization, executor authorization, envelope round-trip, secret redaction, malformed-result fail-closed behavior, database-error sanitization, and synthetic-executor denial handling. Coverage is expanded, not reduced.
- `docs/HEARTBEAT.md`: no working-tree changes; it remains at its committed state. Note: HEAD currently records M6 as complete, which is inconsistent with the recovery state that M6 has not begun; this file was left unchanged per instruction to restore only M5-B-induced edits.

Current host test collection: `api/tests/` 58 (56 pass, 2 skipped); `api/tests_m5/` 46 (34 pass on host, 12 skipped pending disposable proof). With the disposable proof active, all 46 `api/tests_m5` tests pass. Overall host result: `90 passed, 14 skipped, 1 warning`.

## M5-A Regression (Verified During M5-B Disposable Proof)

During the successful M5-E011 disposable proof, the M5-A security and concurrency regression passed:

- `verify.sql` PASS
- `verify_security.sql` PASS
- `verify_concurrency.sql` PASS (successes=1, attempts=1)

This confirms M5-B repository changes did not regress the M5-A governance database guarantees.

Skipped tests and exact reasons:

- `api/tests/test_postgres_integration.py::test_order_transition_and_worker_flow`: `requires the isolated M3 PostgreSQL proof`.
- `api/tests/test_postgres_integration.py::test_task_and_outbox_terminal_failures_create_evidence`: `requires the isolated M3 PostgreSQL proof`.
- `api/tests_m5/test_integration.py::*`: `requires the private M5-B disposable PostgreSQL proof`.
