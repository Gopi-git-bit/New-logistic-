# API build evidence and reproducibility review

**Date:** 17 October 2026. **Decision/evidence:** D-46 / M7-E010.
**Review base:** `0c96e33ac887b536ef4f947b9f4c7cbb395b80f9`.
**Engineering verdict:** bounded build result VERIFIED; registry publication NOT READY.
This review is not owner acceptance of production, a reproducibility waiver or
permission for another build. [Publication criteria](../plans/API_CANDIDATE_PUBLICATION_GATE.md).

## Evidence checked

[Run 38995824366](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38995824366)
was recaptured through GitHub's job-log API and compared with the sanitized
report in [PR #27](https://github.com/Gopi-git-bit/New-logistic-/pull/27).
The [captured JSON](API_BUILD_ONLY_20261017.json) preserves that report, not raw
checkout/build logs or an image archive. Its repository blob/content identity
will be recorded in this review PR. This capture is not a signed attestation.

| Check | Actual result / practical limit |
|---|---|
| Event and identity | workflow_dispatch; actor and triggering actor Gopi-git-bit, actor ID 200721521; attempt 1; source/workflow SHA both `0c96e33ac887b536ef4f947b9f4c7cbb395b80f9`; canonical main |
| Reviewed source | PR #27 merge; tree `10d46eea1a7e085ec3b70402e91c3b43f7bd9134`; five-check post-merge CI [38944743155](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38944743155) passed before dispatch |
| Execution | Job 117288058104; all six steps succeeded; 02:40:13–02:40:43 UTC (08:10:13–08:10:43 IST), 30 seconds; no timeout or rerun |
| Source context | 33 regular committed inputs, each Git blob ID matched to the exact source tree; manifest SHA-256 `7dd828433f4c540c5528d7c663b3443c614f9f4662a0e7a0f2faa8c57c15694b` |
| Source content | Review validation recomputes all 33 content hashes and the sorted manifest from exact-commit files; resulting proof belongs in the review PR audit |
| Base | Declared digest `sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea`; resolved linux/amd64 manifest `sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79` |
| Python retrieval | All 17 reported names/versions/SHA-256 values matched the committed runtime lock; HTTPS public artifact URLs only; pip hash enforcement/report, not independent packet or archive capture |
| Image environment | Python 3.12.14; pip 25.0.1; Debian 13; 151 installed OS package/version observations |
| Host tools | Python 3.12.3; Docker client/server 28.0.4; github.com/docker/buildx v0.38.0 0dbe87f36ed472fe36b6796c3f70b4210a731fc5; Compose 2.38.2; observed versions, not locked binaries |
| Image identity | Local config ID `sha256:fb5f63b31a208afa3be890f5418b2fb5bc7c6120dd422af0ad5a3d8e715662aa` matched the metadata config digest; no published manifest/index digest or retained image archive |
| Settings and identity | Offline canonical settings and Compose parse passed; configured image user 10001:10001; no process UID, application startup or runtime filesystem/network proof |
| Outcomes and cleanup | All 14 recorded commands exited 0; scoped new-image removal exited 0; temporary-directory cleanup is in the successful script path. Base layers/build cache were left to hosted-runner teardown; no independent cache-erasure attestation |
| Preserved denials | No application start, registry push, real-secret dispatch, VPS change or provider call in the reviewed route; live M7 and Qwen disabled. Zero provider_calls is corroborated by the route's scope, not a network-flow capture. |

The context's image_build=NOT_RUN describes only the exporter operation.
The enclosing BUILD_ONLY_PASSED report describes the actual build. Neither field
asserts runtime readiness. The OS package list is not a full SBOM or apt archive
receipt, and a metadata config digest is not a signed provenance statement.

## Gap disposition

These classifications are this review's engineering judgment. They do not
authorize remediation execution or accept residual risk for the owner.

| ID | Gap and evidence | Disposition / required closeout |
|---|---|---|
| PUB-01 | The tested local image was deliberately removed; no OCI archive was retained. Its config ID cannot identify bytes currently available for push. | Publication blocker. A separately authorized fresh build must retain the exact candidate bytes and bind the new source, run, receipts, scan and manifest/config/layer identities. Never reuse the deleted image's receipt as proof for a rebuild. |
| PUB-02 | Registry, exact namespace/name, visibility, access, retention, tagging and first-publication behavior are not approved or inspected. | Publication blocker. Review an exact target contract. Private GHCR is a proposal only; no package or permission is created here. |
| PUB-03 | Current workflow intentionally has contents:read and no publisher implementation. | Publication blocker. Separately review a narrowly scoped publisher and its admission, credential isolation, finite bound and failure/rollback behavior. Do not add push authority to the existing build-only job. |
| PUB-04 | No image vulnerability scan, full SBOM, retained provenance artifact or registry read-back exists. CI's filesystem scan is not an image scan. | Publication blocker for the proposed candidate policy. Define and implement evidence for the exact retained candidate; document authenticity and any approved exception. Never claim existing metadata is a signed attestation. |
| REPRO-01 | Mutable apt update/install; 151 installed versions, no downloaded .deb hashes/origins or repository snapshot/Release identity. | Blocks a repeatable OS-layer claim. Prefer reviewed Debian/security snapshot selection plus package/archive receipts. For a private non-deployable candidate, deferral requires explicit owner acceptance; this review grants none. |
| REPRO-02 | Ubuntu runner label and observed Python/Docker/buildx/Compose versions do not lock runner image, builder binary or serializer behavior. | Pin/identify controllable tools and record remaining hosted-runner variability. Candidate-only deferral is possible by explicit decision; reproducible-image claims remain blocked. |
| REPRO-03 | Pip-reported public URLs/hashes do not independently prove redirects, mirrors or effective egress. Apt origins were not captured. | Retain receipt limitations; implement download-origin evidence if required by the publication contract. Provider/target egress verification remains a separate gate. |
| REPRO-04 | One successful build; timestamps, OS layers and full image equality were not normalized/compared. | No bit-for-bit reproducibility claim. A future repeatability experiment needs its own bounded scope; do not rerun this proof automatically. Immutable per-artifact identity remains mandatory even if candidate repeatability is deferred. |
| DEPLOY-01 | No runtime health/startup, operational auth/pricing, production configuration or fresh target isolation proof; 72 database-skipped API tests and two warnings remain recorded. | Deployment/readiness blockers, not evidence that a private candidate cannot be stored. No DB gap is waived and no production settings are invented. |
| LIVE-01 | Dedicated injection, effective target egress, provider state isolation, hard cap and trusted endpoint/model/source/UID/credential/limit/expiry/one-use authorization remain incomplete. | Live M7 remains denied. Qwen additionally needs an exact route/model, reviewed fallback and combined budget. These are independent of image storage. |

## Recommended next development slice

Prepare a publisher contract and implementation through a new reviewed PR only
after the owner resolves target/visibility and candidate-risk choices. A private,
non-deployable GHCR candidate is the smallest proposed destination, not an
approved one. The current image is gone, so any eventual build-and-publication
execution must generate and review new evidence for the actual artifact.

Do not attempt to close every deployment or live-provider gate merely to store
a candidate. Conversely, a private registry push must not be reported as staging
or production readiness. Parent M7-DELIVERY-DRYRUN stays IN_PROGRESS pending owner
review of this handoff and gap disposition. Merge, a new build, registry access
and publication remain separate authorizations. This review changes records
only; D-33 and manual approval for every refund remain controlling.

## Primary interface references

- [Docker build metadata](https://docs.docker.com/reference/cli/docker/buildx/build/):
  config and image-manifest metadata are distinct identities.
- [Docker attestations](https://docs.docker.com/build/metadata/attestations/):
  attestation retention depends on exporter/store support; the current report
  does not prove retained or signed attestations.
- [Debian snapshots](https://snapshot.debian.org/):
  dated archive selection is a possible OS-input control, not a retroactive
  receipt for this build.
- [GitHub Container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
  and [package permissions](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages):
  package access/visibility must be checked independently; choose least authority.
