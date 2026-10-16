# M7 next development phase: secret-free delivery preparation

**Status:** CONTINUATION AUTHORIZED (D-43); INPUT INVENTORY RECORDED; BUILD/VALIDATION IMPLEMENTATION SEQUENCED.
**Owner:** Gopinathan. **Date:** 16 October 2026.
**Decision/evidence:** [D-42/D-43](../DECISIONS.md) / [M7-E006/M7-E007](../TEST_EVIDENCE.md).
**Tracker:** M7-DELIVERY-BLUEPRINT and M7-DELIVERY-INVENTORY COMPLETE;
M7-DELIVERY-DRYRUN PENDING implementation and execution evidence.

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
API and records nine gaps. This records-only PR does not implement or execute
the proposed workflow/build/manifest steps below. Continue with the bounded
API context/lock/placeholder-validation slice through reviewed feature PRs;
keep merge approval, registry publication and target execution separate. Do not
interpret a manual event or environment approval as a provider capability grant.

## Implementation sequence

| Step | Sequenced work | Acceptance / stop condition |
|---|---|---|
| 1. Inventory — RECORDED | M7-E007 / reports/M7_DELIVERY_INPUT_INVENTORY.md at `6a6f5acd00a6aafa115f1e470821512f5434021f` | API selected as smallest build candidate; actual build not run. Missing context/locks/configuration and production contracts recorded; source behavior and accepted proofs preserved |
| 2. Build contract | Specify exact source, runtime/toolchain, lockfile and base-image identity; document dependency downloads | Missing lock coverage or mutable inputs must be recorded as reproducibility gaps; do not claim bit-for-bit reproducibility without evidence |
| 3. Secret-free CI route | Propose a manual canonical-repository/main route with the designated owner identity, immutable reviewed source binding, finite timeout and explicit input validation | Read-only contents permission only where checkout needs it; no real-secret or Production environment binding; checkout credentials not persisted; actions pinned to verified commit SHAs |
| 4. Local image build | Build on an ephemeral GitHub-hosted runner without registry login or push; pass no credentials or production URLs into image arguments/layers | Record local image ID and build report; an unpushed image ID is not a registry manifest digest or an accepted deployment artifact |
| 5. Manifest validation | Render/validate an explicitly staging-only manifest and environment contract using synthetic placeholders | Configuration parsing only; no compose up/run, service start, SSH, database connection, target mutation or provider request; reject missing required fields and production secret references |
| 6. Offline regression | Check the selected configuration's denial defaults, malformed/missing inputs and secret-free outputs; retain existing M7 refusal and business-invariant tests | Report actual results and skips with provenance; do not weaken checks, invent production credentials or rerun accepted VPS/provider proofs |
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
