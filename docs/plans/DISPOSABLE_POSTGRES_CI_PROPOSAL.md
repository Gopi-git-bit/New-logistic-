# Disposable PostgreSQL CI proposal

**Date:** 17 October 2026. **Decision/evidence:** D-48 / M7-E012.
**Status:** DESIGN MERGED IN PR #30; D-49 IMPLEMENTATION IN REVIEW; NO PROOF EXECUTED.
See the [implementation contract](DISPOSABLE_POSTGRES_CI_IMPLEMENTATION.md) for the new manual-only route and retained execution gates. Earlier implementation-pending language below records the approved design baseline.
Baseline: `2fabdd8eaa16435d705a769d8cb15e8460a665ae`.
This is a planning baseline. A later proof must bind its current approved
main/workflow/source and post-merge CI; do not reuse this SHA as a dispatch input.
This proposal is independent of
[registry/key verification](API_REGISTRY_KEY_VERIFICATION.md).
No registry key, provider credential, VPS or production database is needed.

## Gap and acceptance target

The normal API CI passed 92 tests and skipped 72 database-dependent cases;
two deprecation warnings remain separate. Static source inventory, including
parameter expansion, accounts for all 72:

| Module | Required real cases | Current enable condition |
|---|---:|---|
| `api/tests/test_postgres_integration.py` | 2 | ZIPPY_M3_TEST_DATABASE_URL from the disposable harness |
| `api/tests_m4/test_dispatch_integration.py` | 31 | ZIPPY_M4_TEST_DATABASE_URL |
| `api/tests_m4/test_finance_integration.py` | 23 | ZIPPY_M4_TEST_DATABASE_URL |
| `api/tests_m4/test_payment_intent_privileges.py` | 4 | ZIPPY_M4_TEST_DATABASE_URL |
| `api/tests_m5/test_integration.py` | 12 | PAPERCLIP_DISPOSABLE_PROOF=YES plus the harness's private socket/login contract |
| **Total** | **72** | **60 operations + 12 governance** |

This is a source inventory, not a rerun or acceptance of those proofs. Mocks
remain useful for contracts but cannot establish PostgreSQL locking, rollback,
RLS, SQL grants or concurrent consumption.

Reuse `db/scripts/check_proof_report.py`: it rejects failures/errors/skips,
missing or duplicate test identities and missing integration groups. Required
operations groups are 2/31/23/4 and governance is 12. Additional unit cases
cannot replace a missing group. Treat these as minimum expected integration
counts; any intentional inventory change needs a reviewed report-policy update,
not a lower threshold to force success.

## Existing harnesses and implementation gaps

| Existing source | Reuse | Required implementation review |
|---|---|---|
| `db/zippy/scripts/run_m4_finance_proof.sh` | M3/M4 migrations/fixtures, separate logins, hardened Unix socket, dispatch/finance/privilege cases, rollback and cleanup | Its Python default is /tmp/zippy-m3-venv/bin/python; test process currently runs on the host. Supply a controlled test-runner mode with no external network, explicit synthetic environment and bounded execution. |
| `db/paperclip/scripts/run_m5b_service_proof.sh` | Governance migrations/roles, synthetic service execution, concurrency, rollback/reapply, private logs and report gate | It expects the repository's .venv/bin/python, M5B_PROOF_LOG and unshare support; it assumes socket UID/GID 999. Remove host-path assumptions in reviewed code while preserving every denial/role/socket guard. |
| `db/scripts/check_socket_probe.py` | Accessible/private synthetic socket controls for the unrelated UID | Runs as root orchestration with setpriv and /usr/bin/python3. Preserve the positive control and require EACCES/EPERM for denial; ENOENT/timeout/interpreter failure is not isolation proof. |
| `db/scripts/check_proof_report.py` | Zero-skip integration acceptance | Bind reports to fresh source/run/phase/resource identities and collect them before cleanup deletes their directory. |

The M5-B script already uses a fresh network namespace and a constructed child
environment. Do not claim M4 has the same test-process boundary merely because
its PostgreSQL container uses network none. No existing command is dispatched
from this proposal.

## Proposed workflow and permissions

Implement later in a separate code PR, preserving the existing five CI checks.

- A new manual-only disposable-proof workflow on hosted ubuntu-24.04, canonical
  repository/main, owner Gopi-git-bit / ID 200721521, same triggering actor,
  first attempt and exact reviewed source/workflow SHA. No pull_request_target,
  workflow_run chaining, arbitrary shell input, incoming DB URL or self-hosted
  runner. A skipped/rejected job is not acceptance.
  Admission also verifies github-hosted runner identity, Linux and X64.
- First version: contents:read; actions:read only if needed to verify the
  five-job post-merge CI for that source. All actions full-commit pinned, checkout
  persist-credentials=false. No packages:write, id-token, environment-secret
  reference, production deployment environment or reusable-workflow secret
  inheritance. Never reuse the publisher workflow/authorization contract.
- One concurrency group with no cancellation of an active proof. Proposed
  bounds: 30-minute job, ten minutes per operations/governance phase, 60 seconds
  per DB readiness check and five seconds per socket control. A watchdog must
  stop only its owned resources and preserve timeout as failure.
- One fresh operations phase and one fresh governance phase, sequential for the
  first implementation. Start with an empty resource ledger; no external service
  connectivity or shared database is accepted.
- Approval of this document permits neither workflow implementation nor a
  dispatch. After a separately authorized implementation PR, review/merge and
  verify normal main CI; then explicitly authorize one initial proof run.
  Later promotion to automatic PR checks/required status checks needs a separate
  trigger/protection review. Do not silently add a sixth required check.

## Concrete execution design for the implementation PR

Use a narrow orchestrator on the disposable GitHub runner. It may create/remove
only run-labelled test containers, volumes, socket directories and generated
synthetic credential files. No host firewall changes, host account creation,
persistent service, Docker prune, VPS command or live DB migration.

1. Check exact source, clean checkout, prerequisites, available disk/memory and
   no preexisting resource-name collisions. Record Docker/Compose/Python/runner
   identities without claiming they are fully pinned. Check all commands and
   expected image availability before creating resources.
   Proposed container caps: PostgreSQL one CPU/1 GiB/128 PIDs; proof runner
   two CPUs/2 GiB/256 PIDs and 256 MiB temporary writable space. Verify capacity
   before setup; an exceeded cap is failure, not an automatic retry with more
   resources. These are proposed limits, not measured performance guarantees.
2. Pull only the existing approved PostgreSQL reference
   `postgres@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94`.
   Record its repository/platform/config identity. A registry manifest digest is
   not a Docker config ID. Verify the actual container uses the resolved config;
   no mutable-tag fallback or digest substitution.
3. Prepare a local proof-runner image using the approved Python base identity
   and hash-locked API development requirements from the exact source. Record
   its config/base/context/lock/download identities; no registry push or reuse
   of the candidate publisher. Dependencies are installed before the sealed
   proof phase. This requires implementation and separate execution authority;
   no image is built by the planning PR.
4. Query the pinned PostgreSQL image's effective postgres UID/GID in a bounded
   network-none identity control. Apply that observed identity to the private
   socket directory (0700); never substitute permissive chmod or trust
   hard-coded UID 999. Record socket ownership and SCRAM local authentication.
5. Bootstrap roles/migrations/fixtures only inside the fresh PostgreSQL
   container, network none, no published ports, listen_addresses empty. Keep
   migration/superuser credentials in the orchestrator's private scope.
   Restricted application logins have no superuser/BYPASSRLS/owner authority.
6. Run tests in a separate ephemeral proof container, network none, no ports,
   fixed unprivileged UID/GID chosen for the private socket control,
   cap-drop ALL, no-new-privileges and read-only root filesystem. Bind only the
   reviewed code/fixtures read-only, the exact synthetic socket directory at
   its expected path and a private bounded output directory. Do not mount the
   Docker socket, DB data volume, host home, checkout credentials or business
   paths. Temporary writable space must be bounded and owned by the test UID.
7. Pass only generated synthetic app credentials and required public fixture
   settings in an explicit child environment. Never forward ambient
   DATABASE_URL, provider keys, GitHub token, proxy/credential-helper variables,
   Production secrets or migration credentials. Disable bytecode/cache writes
   to the read-only source. Revalidate fixtures against the current Settings
   contract using explicit synthetic auth/pricing/governance values; never
   relax configuration validation to make an old harness start.
   Governance keeps its required /tmp/paperclip-m5b.*
   socket prefix, database prefix and restricted login assertions.
8. Add a reviewed container-runner mode/adaptation to the existing harnesses;
   a quoted Python executable path cannot simply be replaced by a string of
   docker arguments. Preserve legacy defaults and fixture/reset/rollback tests.
   No role, migration, socket, report or secret-redaction guard is removed
   merely to fit the new runner.
9. Verify an authorized positive socket connection with synthetic credentials,
   and an unrelated non-root UID's EACCES/EPERM denial. Record actual test EUID,
   capabilities, namespace/network mode, mounts, port bindings and role catalog.
   An open socket alone is neither PostgreSQL authentication nor RLS proof.
10. Exercise the existing cases, then validate each fresh JUnit report using
    the existing zero-skip checker. Execute only owned disposable rollback/
    reapply checks. Missing cases, stale report, fake-only result, skipped group,
    unexpected network behavior or cleanup failure rejects the whole proof.

Host-runner setup downloads are not a proof of restricted host egress.
PostgreSQL and test-process network-none controls establish the proposed proof
boundary. This closes no M7 provider-target egress gate. The test UID may match
the synthetic server's socket owner solely for socket access; the server data
volume and process namespace stay separate.

## Results, private data and cleanup

Raw output, credentials, environment files and JUnit initially stay private on
the disposable runner. Capture report exit codes before any pipe/tail/tee;
a formatter's success must not mask pytest or harness failure. Export a fresh,
allowlisted summary only after exact generated-secret matching and generic
credential-pattern checks. Never upload raw logs, a DB dump, environment file
or a complete private socket directory from this public repository.

The sanitized summary includes source/workflow/run/attempt, pinned/resolved
images, tool versions, phase start/end/exit codes, test identities/counts,
zero skips/failures/errors, report hashes, observed process/role/socket/network
controls, resource ledger and exact cleanup outcome. Public synthetic fixture
identifiers may be retained; no passwords, signed envelopes, live endpoints or
unredacted tracebacks. Proposed sanitized artifact retention: seven days,
immutable ID, fail if missing. Require the sanitized summary to stay below
1 MiB; reject a larger result instead of silently truncating it. Raw-log
retention beyond runner lifetime requires
a separate approved private/encrypted destination; it does not depend on the
publisher key or block the credential-free design.

Cleanup must run on success/failure with a separate bounded budget, targeting
only ledger-owned resources after identity/label checks. Record that container,
volume and socket paths are absent and host port 5432 is not newly listening.
Preserve unrelated resources. A failed test remains failure even if cleanup
succeeds; successful tests cannot pass with failed/unknown cleanup. Hosted-runner
cancellation cleanup remains UNKNOWN unless verified; runner teardown is not
an application-level cleanup assertion.

## Acceptance and remaining limits

Accept only one source/run-correlated proof with both 60 operations and 12
governance cases actually passing, no skips/errors/failures, restricted role
and namespace/socket controls verified, rollback/reapply successful and exact
cleanup verified. Record the observed total, not an assumed 72-case PASS.
The report may include additional unit cases; they do not replace the 72.

Before implementation execution, add meaningful offline regressions for
wrong image/config identity, existing-resource conflicts, unexpected socket
success/error, root or overprivileged test identity, unsafe mounts, inherited
credentials, pytest/pipe exit propagation, missing/stale/duplicate/skipped
reports, secret-bearing output, timeout and failed cleanup. Do not add dummy
tests that merely restate this document.

A real disposable proof can close the corresponding CI database gap for that
source and fixture environment. It does not prove production migration safety,
production data compatibility, live financial reconciliation, live provider
readiness, image reproducibility or registry publication. The normal API job's
skip policy changes only in a separately reviewed coverage design.

D-33 stays pending. Deterministic assignment, RPC/RLS, idempotency, settlement/
governance boundaries and manual approval of every refund remain unchanged.
Historical accepted proofs are reused as references; no blind rerun or weakening
of their negative controls is authorized here.

Rollback of this proposal is a reviewed docs revert. Future implementation/
dispatch/required-check changes each remain explicit gates.
