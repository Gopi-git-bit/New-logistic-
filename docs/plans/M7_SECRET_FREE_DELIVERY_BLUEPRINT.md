# M7 next development phase: secret-free delivery preparation

**Status:** API CONTEXT/LOCK/STAGING CONTRACT MERGED (D-44);
MANUAL BUILD ROUTE PREPARED FOR REVIEW (D-45); ACTUAL IMAGE BUILD NOT RUN.
**Owner:** Gopinathan. **Date:** 16 October 2026.
**Decision/evidence:** [D-42/D-43](../DECISIONS.md) / [M7-E006/M7-E007](../TEST_EVIDENCE.md).
**Tracker:** M7-DELIVERY-BLUEPRINT and M7-DELIVERY-INVENTORY COMPLETE;
M7-DELIVERY-DRYRUN IN_PROGRESS; M7-E008 records local preparation evidence.

PR #26 merged at `f8e7cb9a548e9956a0f1f74edc6f73e8fd2a76ef`; all five
[post-merge CI jobs](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38924063418)
passed. D-45's [manual build route](API_IMAGE_BUILD_ONLY.md) implements the next
review slice, with offline evidence in M7-E009. It remains unmerged/undispatched
at preparation; actual image/download evidence and acceptance remain pending.

## Starting checkpoint

Staging Secret Availability is COMPLETE for DeepSeek presence in the selected
GitHub Actions step. [Run 38903102158](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38903102158)
passed once, attempt 1, at reviewed main merge
`bc135b8b605cd96c2bacaf228953d1cbf14ba3ca`.
[Post-merge CI](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38901637850)
passed all five jobs. The owner explicitly authorized release of that run's
Production gate through the connected owner account. OpenRouter presence was
skipped. Reuse this evidence; do not dispatch again to refresh documentation.

Availability means a nonempty secret reached the intended step. It does not
prove authentication, provider-side dedication, secure VPS injection, spending
enforcement or live M7 authority. Existing VPS diagnostics are historical target
observations; this phase does not reopen VPS access.

## Objective and authorization

Prepare a separate GitHub PR that can build a local application image from
reviewed source and validate a staging configuration contract with placeholders.
A passing dry run would establish build/configuration evidence only.

D-43 records the owner's subsequent continuation approval for Docker/build
contexts, dependency locks, API configuration, staging templates and gap records.
The first [input inventory](../reports/M7_DELIVERY_INPUT_INVENTORY.md) selects the
API and records eleven gaps, including explicit input identities, declared download
operations and unverified platform/toolchain/download provenance. The subsequent D-44 slice implements the
[API context/lock/placeholder-validation contract](API_DELIVERY_PREPARATION.md)
for review. It integrates validation into existing CI, without adding the manual
image-build route or executing an image build. Continue through reviewed PRs;
keep merge approval, registry publication and target execution separate. Do not
interpret a manual event or environment approval as a provider capability grant.

## Implementation sequence

| Step | Sequenced work | Acceptance / stop condition |
|---|---|---|
| 1. Inventory — RECORDED | M7-E007 / reports/M7_DELIVERY_INPUT_INVENTORY.md at `6a6f5acd00a6aafa115f1e470821512f5434021f` | API selected as smallest build candidate; actual build not run. Missing context/locks/configuration and production contracts recorded; source behavior and accepted proofs preserved |
| 2. Build contract — STATIC INPUTS IDENTIFIED | Inventory records exact source/tree, API input blob/content hashes, declared runtime/tools/base, download operations and DELIVERY-01 through DELIVERY-11 | Actual platform/toolchain versions, downloaded artifacts/origins and full-image reproducibility remain unverified; capture them in the future bounded build, not by claiming declared selectors were observed |
| 3. Secret-free CI route | Propose a manual canonical-repository/main route with the designated owner identity, immutable reviewed source binding, finite timeout and explicit input validation | Read-only contents permission only where checkout needs it; no real-secret or Production environment binding; checkout credentials not persisted; actions pinned to verified commit SHAs |
| 4. Local image build | Build on an ephemeral GitHub-hosted runner without registry login or push; pass no credentials or production URLs into image arguments/layers | Record local image ID and build report; an unpushed image ID is not a registry manifest digest or an accepted deployment artifact |
| 5. Manifest validation — IMPLEMENTED FOR REVIEW | Strict synthetic JSON Compose/settings contract and bounded existing-CI parse step; local semantic regressions recorded in M7-E008 | Actual Compose CLI result must come from resulting-head CI; no up/run, startup, SSH, database connection, target mutation, real secret or provider request |
| 6. Offline regression — LOCAL PASS | M7-E008: 16 cases for context isolation, unsafe/missing configuration, canonical settings compatibility and output redaction | No local skips/warnings; resulting-head CI remains separately required. Existing M7/business controls and accepted proofs preserved |
| 7. Review handoff | Publish the actual diff, source identity, local image ID, versions, sanitized reports and residual gaps | Exact-head CI green and owner acceptance; no registry/package publishing or deployment follows automatically |

Dependency/base-image retrieval during a future build is not proof of restricted
provider egress. Build failures must remain failures; do not disable runtime
authorization or fabricate authentication/pricing settings to force startup.
No existing production workflow is enabled by this design.

## Evidence contract

The future report must distinguish planned, executed, passed, failed, skipped
and unverified checks. Include repository/ref, full source/workflow SHA, actor,
event, run ID/attempt, toolchain and dependency identities, local image ID,
placeholder-only configuration result, actual job/step conclusions and cleanup.
Never include secret values, prefixes, lengths/hashes, authorization headers or
business data. Do not label mocks, a local image or a green CI badge as deployed
readiness. Accepted disposable DB proofs stay development evidence, not live DB
certification.

Main's 16 October policy is mandatory PRs, zero required approving reviews,
all five GitHub Actions checks, strict freshness and administrator enforcement.
This is the explicitly authorized solo-developer policy. Production has an owner
reviewer, self-review allowed, administrator bypass allowed and a main-only rule;
no bypass was used in the presence proof. Recheck applicable settings for future
authorized execution, not as an instruction to mutate them in this phase.

## Stop conditions and rollback

Stop on source drift, an unexpected trigger/actor, missing provenance, a secret
reference, unsafe manifest, attempted registry login/publication or SSH/provider access, unexpected
runtime activation or failed validation. Diagnose within the review scope; never
substitute another model, create credentials or remove a guard to get a pass.

Before merge, discard or correct the isolated feature branch without touching
unrelated edits. After merge, propose a reviewed revert of this delivery slice.
Ephemeral runner cleanup removes only its build workspace/local images; it must
not remove remote images, alter GitHub secrets/settings or touch VPS resources.
No production rollback is implemented by a documentation/build dry run.

## Separate gates that remain blocked

| Gate | State after this closeout | Required evidence or authorization |
|---|---|---|
| OpenRouter presence / Qwen route | NOT RUN / DISABLED | Separate bounded authorization; exact model/provider route, reviewed fallback and aggregate budget |
| Dedicated credential ownership and target injection | UNVERIFIED | Provider-account ownership/dedication metadata and reviewed secure target injection; GitHub presence is insufficient |
| Target isolation and effective synthetic egress | NOT ACCEPTED FOR LIVE EXECUTION | Fresh target-bound identity/mount/state controls and separately authorized calibrated synthetic egress evidence |
| Provider claim/circuit state | UNVERIFIED | Isolated private state ownership, concurrency/one-use behavior and fail-closed recovery |
| Hard monetary spending cap | UNVERIFIED | Provider-enforced cap or independently isolated capped balance, credits/currency and recharge evidence; token counts are usage only |
| Trusted one-use M7 authorization | DENIED | Trusted issuer and binding to endpoint/model, reviewed SHA, actual UID, credential, limits, expiry and invocation |
| Registry publication and staging deployment | NOT AUTHORIZED | Separately reviewed publishing permissions and immutable digest, target/health/rollback contract and explicit execution approval |
| Production | BLOCKED | Unresolved production authentication/pricing/configuration and all applicable readiness/financial gates |

Live M7 and Qwen remain denied. Keep the selected direct DeepSeek profile
unchanged. D-33 remains pending. Deterministic assignment, RPC/RLS boundaries,
idempotency, settlement/governance controls and manual approval for every refund
are preserved. This blueprint neither changes the architecture nor grants any
agent operational capabilities.

