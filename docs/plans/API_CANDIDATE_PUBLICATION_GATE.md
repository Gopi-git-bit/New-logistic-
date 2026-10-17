# Proposed API candidate publication gate

**Date:** 17 October 2026. **Decision/evidence:** D-46 / M7-E010.
**State:** DESIGN FOR REVIEW; NOT IMPLEMENTED OR AUTHORIZED.
[Evidence and gap review](../reports/API_BUILD_EVIDENCE_REVIEW_20261017.md).

The one authorized build-only run passed and removed its image. This plan defines
what must be made concrete before a future publication. It supplies no registry
permission, secret, workflow change, dispatch approval or deployment authority.

## Proposed destination and owner decisions

| Contract field | Proposal / unresolved decision |
|---|---|
| Registry | GHCR, using the existing GitHub ownership/Actions boundary; proposed, not selected or inspected |
| Package | `ghcr.io/gopi-git-bit/zippy-api`; exact namespace/name require owner approval |
| Visibility | Private candidate only; public publication excluded. Verify effective existing-package access. If absent, explicitly approve first-publication bootstrap, verify applicable creation defaults, and verify resulting visibility immediately. Unknown behavior stops publication. |
| Reference | New run-specific candidate tag containing the full source SHA and run ID; no latest/production tags or overwrite of an existing reference |
| Identity | Record immutable registry index/manifest digest, selected platform manifest, config and layers; metadata/tag alone is insufficient |
| Retention/access | Approve readers/writers, evidence/image retention, package linkage and cleanup ownership before execution; do not infer them from the public source repository |
| Residual risks | Resolve REPRO-01 through REPRO-04: implement controls or explicitly accept named risks for a private non-deployable candidate. No production waiver or bit-reproducibility claim. |
| Image security | Proposed policy: scan the exact retained candidate, retain scanner/version/database identity, SBOM and findings. Stop on unresolved HIGH/CRITICAL findings unless the owner explicitly approves a documented quarantine-only exception. No exception is approved here. |
| Provenance | Bind source/workflow/run, base/platform, material/receipt and artifact digests. Select retained provenance/attestation support; unsigned evidence must remain labelled unsigned. |
| Spending/bounds | Fix one attempt, job/command bounds, candidate count and storage/retention scope; approve any paid usage before execution |

An engineering recommendation is not an owner choice. Current GitHub package
settings, namespace availability and write permissions have not been probed.
The existing Production provider-secret environment is outside this contract.

## Admission and artifact flow required in the implementation PR

1. Preserve canonical repository/main, exact reviewed source/workflow SHA, owner
   login/ID, same triggering actor and first-attempt checks. Recheck green
   post-merge CI and intended workflow bytes before a separately authorized run.
   Deny source drift, fork/PR triggers, reruns, unexpected inputs and ambiguity.
2. Build and inspect using read-only source permission, isolated empty Docker
   configuration and no application/provider/SSH credentials. Retain the exact
   new candidate and evidence. Old run 38995824366 is historical evidence only;
   a rebuild can differ and cannot inherit its local config ID or download proof.
3. Correlate the retained artifact's manifest/config/layers with the build report,
   SBOM and image scan. If crossing jobs, define a reviewed immutable transfer
   format with content hash, source/run binding and expiry/retention. A mutable
   tag or an unverified artifact name is not a transfer boundary.
4. Limit registry authority to a separate reviewed publisher job. For approved
   GHCR use, prefer the job-scoped GITHUB_TOKEN with only necessary contents:read
   and packages:write; do not request a PAT, broad repo/admin access or production
   secrets. OIDC/attestation permissions are allowed only if that feature is
   explicitly selected and reviewed. No permission changes are made by this plan.
5. Publish only the approved candidate reference after all acceptance checks.
   Never build, import app code, open a DB or run a service in the credentialed
   publisher. A finite manual authorization boundary must cover the exact source,
   target, visibility, candidate limits and accepted gaps. The implementation PR
   must specify how that boundary is enforced before any push.
6. Resolve the pushed reference to immutable registry metadata, verify the
   index/platform/config/layer mapping against the retained artifact, verify
   visibility/access and record the final digest and evidence location.
   Do not deploy, start an application, promote a production tag or call a provider.
7. Stop and report partial/unknown outcomes. Inspect remote state before any
   retry; do not automatically replay a push or delete a possibly shared image.
   Remove only this run's local temporary files/config/images, preserving
   preexisting resources. Registry deletion, visibility change or cleanup beyond
   the approved candidate requires its own exact scope and ownership checks.

The permission split, transfer validation, duplicate-reference refusal, timeout,
partial-push handling, redaction and digest read-back need meaningful offline
regressions in the future implementation. This records-only PR creates no dummy
tests or publisher workflow. Existing build-only permissions remain unchanged.

## Reproducibility work and candidate-only deferral

For apt, propose exact archive timestamps for both Debian and security inputs,
signed repository/Release identity and package-version/archive-hash receipts,
including transitive packages. Verify the snapshot actually exists and fits the
base before implementation. Preserve repository signature verification; any
historical metadata-expiry handling needs a narrowly reviewed approach. Do not
invent a snapshot timestamp or retroactively call installed versions receipts.

For tools, identify/pin the controllable builder/action/tool binaries and record
hosted runner image/version plus remaining uncontrolled inputs. Normalize build
timestamps where supported and compare actual output identities only in a
separately authorized experiment. A fixed base digest, source SHA and pip lock
do not make mutable apt/toolchain inputs deterministic.

Candidate-only deferral must state the gap, reason, scope, owner, expiry/review
condition and remediation. The candidate must stay private and non-deployable;
deferred reproducibility must remain visible in its metadata. This plan grants
no blanket exception. Operational/runtime, database and live-provider gates stay
separate; do not force their configuration merely to make a registry step pass.

## Review and execution sequence

Current gate: review the captured build evidence, gap classification and these
proposed criteria in a new PR with exact-head CI. Its merge still needs owner
approval. After the destination/risk decisions, separately authorize publisher
implementation; review and merge the actual workflow through normal protections,
then verify post-merge CI. Only then authorize one bounded candidate publication
run on an exact current source SHA with its concrete target and limits.

No new build or publication command is included for copy-paste execution here.
A failed or skipped run is not a publication pass. A successful push establishes
image storage and identity only; staging/production deployment and live M7/Qwen
remain denied.

Rollback for these records is a reviewed documentation revert. The future
publisher must define scoped partial-publication handling, without broad package
deletion, shared-tag changes, settings bypasses or application restarts.
D-33, deterministic assignment, RPC/RLS, idempotency, settlement/governance and
manual refund approval remain unchanged.
