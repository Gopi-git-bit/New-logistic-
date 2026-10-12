# Disposable database proof slice

Authority: the owner accepted the mock-plus-real-PostgreSQL plan on 2026-10-12.
Base: PR #12 head `1b61b7c4a67bfb8874f7efe29886abd1ac7fcef0`.
Scope is synthetic disposable tests and feature-branch publication/CI. Production
SQL, VPS changes, live providers, deployed agents, financial actions, merge and
M7 activation remain outside this scope.

## Coverage decision

PR #12's API run reported 92 passed, 72 skipped and one test-client deprecation
warning. The 439 passing worker tests are a different layer. Existing mocks are
retained; none are added as substitutes for database acceptance.

| Required integration group | Previously skipped |
|---|---:|
| M3 order/worker transactions | 2 |
| M4 dispatch eligibility, assignment and concurrency | 31 |
| M4 finance/refunds | 23 |
| M4 restricted database permissions | 4 |
| M5 governance/grant consumption | 12 |

The existing M4 harness covers M3 regression and operations/finance in one fresh
database. M5-B separately runs governance SQL and service proofs. New CI matrix
jobs use separate ephemeral hosted runners, without shared databases, logins,
data volumes, signing keys or credentials.

## Isolation and reporting

Harnesses generate unique containers, volumes, databases and private Unix sockets
with disposable marker checks. Containers use network `none`, no published ports,
private sockets and SCRAM authentication. Tests use restricted application logins;
migration/owner authority remains separate. Root is used for CI orchestration and
namespace/socket setup, not as evidence of an unprivileged M7 provider target.

The launcher requires hosted CI, root and no pre-existing host port 5432 listener.
Each proof runs in a network namespace with a constructed environment, without
GitHub environment secrets or incoming database URLs. Dependencies and the pinned
image are obtained before test network isolation. Full diagnostics remain private
and are deleted; only fixed markers/numeric summaries are published. No private
log or credential-bearing artifact is uploaded.

JUnit validation refuses skips, failures, errors, duplicate cases and missing
integration groups. Unit/mock successes cannot satisfy integration counts.
Existing cleanup/down/role-teardown checks are retained. Migration and runtime
business rules remain unchanged, including synthetic legacy-adapter tests; this
does not restore abandoned Odoo or activate refunds/settlements.

The original PostgreSQL digest is requested. Unavailability or image-identity
mismatch fails the job; no silent substitution. Historical proof records are not
current CI evidence. Resulting-head runs and any environment corrections must be
recorded in the PR before claiming the 72 gaps are closed.

First CI run 38224409837: governance passed 46 tests, zero skips, including its
12 integration cases plus SQL security/concurrency, rollback/reapply and cleanup.
Operations stopped at the legacy equality assumption between registry digest
and Docker config ID. The correction retains the original registry digest,
verifies the image's repository digest and binds the container to its resolved
config ID; these are separately reported as non-secret artifact metadata.
Operations evidence remains pending until a resulting-head proof passes.

The second run confirms registry digest `f1c337...f6f94` resolves on hosted
Docker to config ID `80f4c7...ced8d2`; the manifest pin is unchanged. A second
early operations failure exposed the readiness loop's `/dev/null` read, which
returns EOF instead of waiting. Use a real one-second interval and safe numeric
failure-line markers, retaining the existing bounded attempts and private logs.

Later phase diagnostics narrowed failure to the interval after fixture loading
and before pytest, which also contained the non-root probe. That probe used a
project virtualenv import and conflated any interpreter exit 1 with a successful
database connection. Use system Python's standard-library Unix socket probe
instead: verify UID 65534, require permission denial, distinguish actual socket
access with exit 42, and leave other probe errors explicitly NOT VERIFIED.
This tests the private-directory boundary directly rather than accepting an
authentication failure as proof of filesystem isolation. SQLSTATE/source-only
fixture diagnostics remain available without emitting statements or values.

Evidence correction: commit d582bd5's message incorrectly stated that local
private/accessible socket controls passed. The local attempt failed at socket
creation with EPERM before either control ran; it is not counted as evidence.
Hosted CI run 38226933907 at that commit passed operations (118 tests, including
60 integration cases) and governance (46 tests, including 12 integration cases),
with zero skips, scoped cleanup and the actual non-root socket denial PASS.
The launcher now requires a separate hosted control using the same probe against
both mode-0700 and mode-0755 synthetic socket directories. A mismatch stops the
operations proof; no database is started on a failed control. Final resulting-head
control/proof outcomes are recorded in PR #13 without another local socket attempt.

The FastAPI/Starlette `httpx` deprecation remains a separate maintenance item.
M7's dedicated credentials, installed target, effective egress, budget and trusted
authorization remain unverified. D-33 remains pending; real refunds require manual
approval.
