# Private API candidate publisher implementation

**Date:** 17 October 2026. **Decision/evidence:** D-47 / M7-E011.
**State:** IMPLEMENTATION FOR REVIEW; PUBLICATION NOT AUTHORIZED.
This supersedes the implementation-pending portions of the
[publication design](API_CANDIDATE_PUBLICATION_GATE.md). It does not complete
the delivery milestone or any runtime/provider gate.

The owner authorizes publisher code, registry/visibility constraints, scoped
permissions, image security/provenance checks and apt/toolchain gap handling.
The implementation target is `ghcr.io/gopi-git-bit/zippy-api`, **private only**.
No registry package, access setting, environment, key or publication was created.
Effective package availability/access and publication-environment protection
remain unverified.

## Jobs and identity

| Boundary | Implemented contract |
|---|---|
| Admission | Manual dispatch only; canonical repository/main; Gopi-git-bit / actor ID 200721521; same triggering actor; attempt 1; full reviewed source SHA equals workflow SHA; clean exact checkout; current-main and green post-merge five-job CI checks |
| Authorization | Default scope is not-authorized; one private nondeployable candidate must be explicitly selected, with exact named gap acceptance and UTC expiry within one hour. Rechecked after build, on publisher admission and immediately before push. Push timeout is capped by remaining authorization time. |
| Build/scan | Hosted ubuntu-24.04, 25-minute job; contents:read and actions:read only. Existing safe Git context/settings/build path retained; no package write, provider secrets, app start or database. New image is saved before scoped cleanup. Preexisting image IDs are not exported for publication. |
| Transfer | Six exact bundle members: image.tar, build.json, scan.json, sbom.json, database.json, provenance.json. Only age ciphertext and hash/identity metadata enter Actions artifacts; one-day retention, immutable artifact ID, no overwrite. |
| Publisher | Separate hosted job, 12-minute bound, Candidate-Publication environment; contents:read, actions:read, packages:write. Daemonless crane; no build, application import, service start, Docker load, database or provider. |
| Registry | Existing private package with pinned package ID, owner ID and repository linkage required. Unknown/404/public/mismatch refuses publication. No implicit first-package bootstrap or settings changes. |
| Reference | One candidate-fullSourceSHA-runID tag. Successful tag listing must show it absent; no latest/production tag, CLI push replay or automatic deletion. Internal tool HTTP retries may occur within the bounded command; this is not a transport single-request claim. |
| Read-back | Local archive config/layers and crane manifest identity checked before push; remote immutable manifest/config digests, platform, user and layer descriptors verified afterward, with full remote layer validation. Package visibility/linkage rechecked. |
| Evidence | Public logs contain allowlisted status, identifiers, hashes and exception classes. Image, package inventory, scan, SBOM, receipts and detailed registry proof remain encrypted. Provenance is explicitly unsigned workflow evidence, not a signed attestation. |

The source repository is public. Repository read access allows downloading
Actions artifacts; plaintext image archives would not preserve a private
candidate. The age recipient is public and must be pinned by a reviewed change.
The private identity belongs only in the dedicated publication environment.
No provider or Production environment secret is referenced.

The independent, expiring access-review record must cover effective readers,
writers, repository inheritance/linkage, GitHub-token package grant, retention,
environment main-only branch policy, required owner approval and administrator
bypass policy. It must also establish that CANDIDATE_AGE_IDENTITY has no
repository/organization-scoped alias and is injected only into this environment's
publisher step. The checked-in policy holds the approved record's SHA-256 and
expiry. **A valid hash field alone is not live ACL verification:** the package
API checks current identity/visibility/linkage, while effective ACLs and secret
origin require the separate owner-reviewed settings evidence. No setting was
inspected or changed by this implementation.

## Fail-closed configuration

`infra/publication/api-candidate-policy.json` intentionally leaves package_id,
recipient, access_review_sha256 and access_review_expires_utc unset. Admission
therefore fails before downloads/build/export. This is an operational gate,
not a synthetic success or a newly provisioned credential.

Before execution, a separate reviewed change must pin the actually verified
private package ID, valid public age recipient and expiring access-review
reference. Provisioning its matching private key and configuring the protected
Candidate-Publication environment require separate authorization. If the package
does not exist, obtain an explicit bootstrap plan/approval first; this publisher
does not create a package to discover its visibility afterward.

GitHub's package visibility/access are independent of this public repository.
The implementation never automatically changes visibility, ACLs, protection,
repository permissions or a package's linkage. A new package or unknown grant
is a blocked prerequisite, not a reason to introduce a PAT or admin permission.

## Image security and provenance

The exact retained archive is validated without executing it. Config SHA-256,
linux/amd64, configured user 10001:10001 and every uncompressed layer diff ID
must match. Tar traversal, links/devices, duplicate names, unrecognized outer
members, PAX metadata and oversized payloads are refused. The accepted Docker
save representation is a single image with uncompressed layer entries; unknown
representations fail closed and require a reviewed compatibility correction.
Archive/registry compatibility has not been demonstrated by a real build in
this slice.

Pinned Trivy scans archive vulnerabilities and filesystem/image-configuration
secrets. Both general and separate secret-config loading are explicitly disabled
with empty paths; telemetry and version notices are disabled;
offline dependency identification avoids enrichment API calls while the explicit
security database repository remains available. HIGH/CRITICAL findings,
tool errors, missing/mismatched reports or an empty SBOM stop publication.
There is **no image-security exception input**. CycloneDX SBOM and database
metadata/content hash are retained; the database must have schema 2, be at most
24 hours old, not future-dated and not past NextUpdate at scan and publication.
Its upstream tag is intentionally refreshed security data, not a fixed package
resolution input. Database failures are not converted to passes.

Unsigned provenance binds workflow/source/run/expiry, build report/context and
pip receipts, base/platform, policy/tools/gaps, archive, scan, SBOM and database
hashes. The pinned upload action emits bare SHA-256 hex; the publisher validates
that exact representation and compares its algorithm-prefixed value to REST
artifact metadata, refusing malformed values and mismatches. The transfer binds
ciphertext, bundle and provenance hashes to producer
outputs and the same GitHub run/artifact ID/digest/source. age authenticates the
ciphertext; workflow/artifact identity supplies the selected authenticity
boundary. No OIDC/id-token or attestation permission is requested, and no signed
supply-chain or deployment acceptance is claimed. A later consumer requiring
signed attestations must add/review that contract before promotion.

## Tool identities and reproducibility disposition

New actions are full-commit pinned: checkout v4.2.2, upload-artifact v4.6.2 and
download-artifact v4.3.0. Official release metadata was read on 17 October 2026
to pin Linux/amd64 archive SHA-256 identities for age v1.3.2, crane v0.22.1 and
Trivy v0.76.0. The JSON policy is the exact version/URL/hash/member source of
truth. The installer downloads only fixed official GitHub release URLs, verifies
the archive hash and writes only the named regular executable. No release
binary was downloaded, installed or run during this implementation review.
Release-asset hashes establish the selected artifact identity; they are not
independent release-signature verification.

| Gap | Current handling | Separate remediation |
|---|---|---|
| REPRO-01 apt | Dockerfile and installed-version evidence remain unchanged; sources mutable, no .deb hash/origin or signed snapshot receipt. No snapshot timestamp is invented. | Verify compatible Debian + security snapshots and signed metadata; capture transitive archive hashes before claiming apt reproducibility. |
| REPRO-02 toolchain | New actions/binaries pinned; actual builder versions/base/platform still recorded. Hosted runner/Python/Docker/BuildKit/Compose are not fully locked. | Review a pinned builder/toolchain and any runner inputs before deterministic-build claims. |
| REPRO-03 transport | Declared origins/receipts retained; effective redirects, mirrors and egress not independently observed. | Separate transport-control evidence. |
| REPRO-04 image identity | Fresh candidate must have its own archive/manifest/config evidence. No repeat-build equality is claimed. | Separately authorize a controlled reproducibility comparison. |

The implementation **does not approve these deferrals**. A later owner dispatch
must explicitly supply all four exact IDs, the private nondeployable scope and
an expiry within one hour. Provenance retains each reason and remediation;
acceptance applies only to that run's candidate and expires with its authorization.
No production, runtime, security-scan, database or provider waiver follows.
Choosing to fix the gaps instead is valid; remove a deferral only through a
reviewed policy/code change after actual evidence exists.

## Failure, cleanup and next execution gate

Local temporary directories/config/identity files are private and removed on
normal completion/failure; only the owned new local image is removed. No broad
prune, host/VPS operation or registry deletion occurs. Cancellation/daemon
teardown remains an unverified hosted-runner limitation, not guaranteed cleanup.

A push is marked PUSH_ATTEMPTED_REMOTE_STATE_UNKNOWN before invocation. On
timeout, read-back mismatch, loss of visibility evidence or later error, retain
that status/reference/expected digest in the sanitized audit; do not replay
the push or assume nothing was stored. Stop and inspect the exact remote state
under separately approved read-only scope. Do not delete a shared package/tag
or change its visibility to force recovery. If verified publication succeeds
but evidence upload fails, inspect the publisher step's audit before retrying.

Sequence: review/merge implementation separately; verify post-merge CI; authorize
and verify the dedicated environment/key/package/access setup and pin its
evidence in a reviewed policy change; review exact current workflow/source and
named gap disposition; then explicitly authorize **one** bounded publication
dispatch. This turn performs none of those operational actions.

Offline regressions use synthetic archive bytes and fake HTTP/tools. They test
admission, tampering, tar/config/layer hashes, security/DB failure, permission
split, duplicate tags, read-back and unknown push outcomes. They do not prove
real encryption, an image scan, registry access, publication or running code.
CI remains the existing five jobs; it does not invoke this manual workflow.
M7-E011 records local validation; exact-head CI belongs to the implementation PR.

Live M7 and Qwen remain disabled. Production deployment, provider credentials,
VPS/firewall/Docker/service operations and the 72 database-test gaps remain
outside this slice. D-33 stays pending; every refund requires manual approval.

Primary interface references:
- [GitHub artifact access](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)
- [GitHub container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [age manual](https://filippo.io/age/age.1)
- [crane v0.22.1 commands](https://github.com/google/go-containerregistry/tree/v0.22.1/cmd/crane/doc)
- [Trivy image scanning](https://trivy.dev/docs/latest/target/container_image/)
