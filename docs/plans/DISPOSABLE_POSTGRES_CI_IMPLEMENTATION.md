# Bounded disposable PostgreSQL CI implementation

**Date:** 17 October 2026. **Decision/evidence:** D-49 / M7-E013.
**State:** IMPLEMENTATION FOR REVIEW; FIRST PROOF DISPATCH NOT AUTHORIZED.
Baseline: `0dc43287886755a440a39a5dcc07399119da515d` (merged PR #30).
The [approved proposal](DISPOSABLE_POSTGRES_CI_PROPOSAL.md) remains the design record.
Registry/key verifier implementation is an independent, excluded scope.

## What this changes

The existing `.github/workflows/disposable-db-proofs.yml` contained a PR-triggered
matrix using host-side legacy harnesses. It is replaced by a manual-only route,
not left available alongside an automatically executable copy. Neither a feature
PR nor its ordinary CI starts PostgreSQL or builds a proof image.

The five required CI checks are preserved. The existing `api-tests` job adds
only offline verifier regressions and quality checks; the ordinary API skip
policy is unchanged. No required-status or protection setting is changed.

New `db/scripts/admit_disposable_ci.py` validates the owner/main/source/run and
current main's completed five-job push CI. It uses a read-only GitHub token only
in that admission step. `run_disposable_ci.py` receives a private metadata
receipt and a clean child environment; no token/provider secret is forwarded.
The pure contract and sealed runtime entry points are separate files.

Canonical migration/role/fixture SQL, integration assertions and legacy shell
harness defaults remain intact. The new orchestrator adapts their execution
into fresh, isolated containers rather than replacing quoted Python paths with
shell strings. The M4 Settings fixture gets public synthetic governance fields
so its test configuration is explicit without weakening validation.

## Admission and authority

- Only workflow_dispatch on canonical main, owner login Gopi-git-bit / actor ID
  200721521, repository ID 1349197102 / owner ID 200721521, same triggering
  actor, first attempt, source SHA equal to both run/workflow SHA.
- Full source SHA plus an explicit one-proof boolean (default false) and UTC
  authorization expiry no more than one hour ahead. Recheck expiry before each
  SQL phase. Queued/stale requests cannot extend themselves or replay.
- github-hosted ubuntu-24.04, Linux/X64. The receipt is generated before resource
  creation, private/single-link/regular and no more than five minutes old when
  the orchestrator begins. Source HEAD, clean checkout and each selected input's
  bytes are compared with that approved Git source before build/SQL.
- contents:read and actions:read only; no environment secret reference,
  packages:write, id-token, provider key, external DB URL or self-hosted runner.
- Workflow action pins verified against upstream commit metadata on this date:
  checkout `11d5960a326750d5838078e36cf38b85af677262` and upload-artifact
  `ea165f8d65b6e75b540449e92b4886f43607fa02`.
- Merge approval is separate from implementation approval. After merge and
  green post-merge CI, one initial proof dispatch needs explicit owner authority
  for its actual SHA/expiry. This document supplies no such authorization.

## Owned execution and limits

One concurrency group, no cancellation of an active proof; 30-minute hosted-job
bound. The orchestrator has a 27-minute command deadline, at most ten minutes
per sequential operations/governance phase, 60-second readiness deadline,
five-second socket timeout and independently bounded cleanup. Commands capture
no public argv/environment/output; the sanitized ledger records operation,
stage, UTC times and exit/timeout. Timeouts never become success.

Setup uses only the reviewed PostgreSQL digest
`postgres@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94`
and Python base
`python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea`.
The PostgreSQL repository/platform/config identities and expected data-volume
layout are checked; unsupported layouts fail, with no alternate image fallback.
A bounded unprivileged network-none control obtains the actual postgres UID/GID.
It mounts an owned directory over the image's data-volume path to avoid an
untracked anonymous volume. UID 65534 collisions are rejected for socket controls.

`db/Dockerfile.proof` installs binary-only, hash-locked development requirements
before sealing tests. Its context contains only that Dockerfile, the exact lock
and reviewed metadata emitter. It adds no apt downloads. The existing build
receipt validator checks installation/download hashes against the lock. Nothing
is pushed to a registry. Setup downloads remain external network activity and
are not proof of restricted host egress or whole-image reproducibility.

Each SQL phase owns new nonce-labelled container/volume/socket resources and
fresh synthetic passwords. PostgreSQL has no network or published ports and
an empty listen_addresses setting; SCRAM local authentication is verified.
Its startup receives only narrowly listed capabilities needed by the official
entrypoint; the final postgres process must actually have the observed non-root
UID, zero effective capabilities and NoNewPrivileges. PostgreSQL is limited to
one CPU, 1 GiB and 128 PIDs. Its default writable data area is an owned volume.
Migration/bootstrap credentials stay in root-private orchestration files.

The distinct test container uses the observed socket-owner UID, no supplementary
host grants, network none, private IPC/PID boundaries, cap-drop ALL,
NoNewPrivileges, read-only source/root filesystem, two CPUs, 2 GiB and 256 PIDs.
It receives generated application credentials plus required synthetic test
settings only. It mounts no Docker socket, server data volume, home, checkout
credentials, business path or migration credential file.

Writable test scratch is a 256 MiB tmpfs. **Output is a separate 8 MiB tmpfs**,
with individual files capped at 4 MiB. This tightens the proposal's private-output
bind: only two named, bounded, regular files are copied privately while the
owned test container is still running. Raw output is never uploaded. A fixed
590-second idle container provides the collection window; pytest itself is
bounded at 540 seconds and the phase deadline can cut it off earlier. A missing
window, unsuccessful exec or copied symlink/hardlink/stale report rejects proof.

Before pytest, a separate unrelated UID 65534 must connect to an accessible
synthetic socket and receive EACCES/EPERM on the actual private database socket.
ENOENT, refusal, timeout or interpreter failure cannot count as isolation.
The application login must authenticate and have no superuser/BYPASSRLS,
create-role/database, migration membership or schema-owner authority.
Runtime EUID/capabilities/NoNewPrivileges, namespace differences from the host,
role and network observations are correlated with Docker's actual configuration.

## Coverage and acceptance

| Integration group | Required cases |
|---|---:|
| Core order/worker | 2 |
| Dispatch | 31 |
| Finance | 23 |
| Payment-intent privileges | 4 |
| Governance | 12 |
| **Total** | **72: 60 operations + 12 governance** |

The existing report checker remains the minimum-count gate. New evidence
additionally binds phase/source/run/nonce, unique case identities, exact report
hash and restricted runtime observations. Unknown/missing/duplicate/skipped,
failed or stale evidence rejects acceptance. Existing unit tests may be present
in the same suites; they cannot replace a missing integration group.

Operations reuses canonical marker/role/migration guards, fixtures and role
teardown. Governance preserves its private socket prefix, synthetic database
prefix, restricted login, SQL security/concurrency controls and fixture reset.
Both require disposable rollback/reapply verification. Every refund remains
manually approved; no integration test authorizes a real refund.

Successful tests alone are insufficient: every ledger-owned container/volume,
image tag and socket must be absent after scoped cleanup, with port 5432 still
absent. Existing names, changed labels/IDs/inodes and daemon errors stop cleanup
rather than being treated as absence. Ambiguous creation is reconciled only by
its exact intended name and matching nonce label. No prune, shared deletion,
firewall/account change or persistent service is used.

Cleanup gets a separate bounded allowance and targets test containers before
the database. If cleanup is uncertain, bind paths remain private on the
short-lived runner and the result is NOT_VERIFIED. Hosted-job cancellation,
runner teardown and Docker build-cache deletion are not labelled verified;
setup cache remains ephemeral-runner-only and is never broadly pruned.

## Evidence, gaps and next gate

Only an allowlisted JSON summary, maximum 1 MiB, is uploaded with an immutable
artifact identity and seven-day retention. It includes source/workflow/run,
accepted CI identity, input/download/config hashes, tool versions, real case
identities/counts, runtime controls, timestamps, command exits and cleanup.
Generated-secret matching and generic credential-pattern checks reject unsafe
summaries; raw SQL/pytest output, JUnit, passwords and signed envelopes stay
private. Missing artifact/summary or an upload failure is not acceptance.
Longer raw-log retention requires its own approved private/encrypted destination.

Offline regressions validate guards and failure paths only. Docker compatibility,
actual PostgreSQL data/schema behavior, timing/cap suitability and all 72 test
assertions remain **UNVERIFIED until the separately authorized proof succeeds**.
The ordinary CI's two pytest warnings and action/dependency warnings remain
separate; this implementation does not claim to fix them. Hosted toolchain,
transport and bit-reproducibility gaps remain open. A passing disposable proof
would not establish production migration safety or M7 provider-target egress.

Next gate: review the implementation head and ordinary CI, separately approve
merge, verify exact-merge CI, then explicitly authorize one source-bound proof.
Rollback of preparation is a reviewed code/docs revert; no installed resource
exists to undo in this slice. Publication, live M7 and Qwen remain denied;
D-33 stays pending.
