# M7 GitHub CI/CD execution gate

## Accepted status — 16 October 2026 (D-42 / M7-E006)

**Staging Secret Availability: COMPLETE, DeepSeek presence-only scope.**
[Run 38903102158](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38903102158), attempt 1, succeeded at reviewed merge
`bc135b8b605cd96c2bacaf228953d1cbf14ba3ca`; [post-merge CI](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38901637850) passed all five jobs.
The owner explicitly authorized the run-specific Production approval through the
connected owner account. DeepSeek presence passed; OpenRouter was intentionally
skipped. Preserve the historical `PRESENCE_OBSERVED_REVIEW_REQUIRED` assessment;
the owner's current instruction completes its bounded documentation review.

Main's current verified policy requires a PR and **zero** approving reviews,
all five strict checks and administrator enforcement. Production's owner reviewer
is configured; self-review and administrator bypass are allowed, with no bypass
used. The owner later explicitly delegated this one approval, superseding the
earlier instruction below to leave the approval click to the owner. This supplies
no standing permission for another approval, dispatch, rerun or provider call.

The chronology below is retained as the design and earlier instruction record;
statements that PR #23 is unmerged, presence is unexecuted or main requires one
approval are historical. Use M7-E006 and D-42 for this accepted checkpoint.
The [secret-free delivery blueprint](M7_SECRET_FREE_DELIVERY_BLUEPRINT.md) is
the next phase. D-43 subsequently authorizes bounded delivery preparation;
[M7-E007's input inventory](../reports/M7_DELIVERY_INPUT_INVENTORY.md) is recorded.
Build and placeholder-manifest validation are sequenced, not executed here.
No VPS, deployment, provider-state, hard-cap or live-authority gate is completed.

Owner instruction, 16 October 2026: continue development through GitHub PRs,
pause VPS configuration, review PR #22 for staging-secret scope, least privilege
and safe triggers, update the canonical PRD, and promote the validated head to
Ready for review. This permits repository preparation and ordinary secret-free
PR CI. It does not authorize merging, a real-secret dispatch, deployment,
credential provisioning, provider calls or Qwen fallback.

## Current PR contract

`.github/workflows/validate-secrets.yml` is a presence-only workflow. Its only
trigger is `workflow_dispatch`; the job also requires the canonical repository
`Gopi-git-bit/New-logistic-`, `refs/heads/main`, and that exact event name.
PR, push, tag, fork and reusable-workflow events cannot admit this job under
the reviewed definition. Invalid provider input fails before a secret step.

The owner-authorized follow-up also requires original actor ID `200721521`,
original actor login `Gopi-git-bit`, triggering actor login `Gopi-git-bit`, and
run attempt `1`. Other actors, missing identity fields and all reruns are denied
at the job condition before runner allocation or a secret-bearing step. Account
renames require a reviewed allowlist update. A fresh manual run still requires
its own bounded authorization; the condition is not a durable one-use ledger.

GitHub may accept a dispatch request from another repository writer; YAML cannot
change who can submit that request. The job condition restricts execution and
secret access under this workflow revision. A skipped job is not a successful
presence check. Repository administrators can edit settings, and someone with
workflow write access could propose another revision; keep branch review and
environment approval controls in place. This is not protection against an
administrator deliberately removing those controls.

The workflow has `permissions: {}`: no repository writes, package publication,
deployment permissions or OIDC issuance are requested. It has one two-minute
Ubuntu-hosted job, references `Production`, performs no checkout or dependency
installation, and injects only the selected key into its own step. Input values
enter Bash through environment variables, not generated shell text. Key values,
prefixes, lengths, hashes, environments and account responses are never printed.

| Selection | Exact secret reference | Meaning of success |
|---|---|---|
| `deepseek` | `DEEPSEEK_STAGING_API_KEY` | Nonempty value available to this step |
| `openrouter` | `OPENROUTER_STAGING_API_KEY` | Nonempty value available to this step |

Success proves neither environment-exclusive origin nor key validity,
dedication, injection, budget or live authority. A same-named repository or
organization secret could resolve if the environment key were absent. Verify
secret **names and scope metadata** before dispatch; do not grant the presence
job broader API permissions to perform its own administrative audit. Generic
provider keys are never referenced by this workflow. Selecting a presence check
does not switch inference models or implement fallback.

Worker CI automatically discovers `test_staging_secret_workflow.py`. It parses
the workflow with the pinned development-only PyYAML dependency and runs only
synthetic selection/presence/redaction cases. No real key, environment approval,
provider socket or live workflow dispatch is used by those tests. These are
regressions for the reviewed workflow contract, not a general shell sandbox or
an attestation of GitHub account settings.

## Completed sequence: one authorized DeepSeek presence check (historical design)

The following sequence is a design, not an instruction to execute it in PR #22.

1. Review the exact final PR head and its checks; separately authorize its merge.
   Preserve inherited commits and require the intended change set. Ready for
   review is not approval, and a green PR run is not post-merge acceptance.
2. Verify the resulting `main` merge SHA and successful CI on that exact SHA.
   Record workflow source SHA, reviewed tree and CI run links. Do not dispatch
   a newer, unreviewed workflow revision after main moves.
3. Verify GitHub settings through authorized metadata-only access. Require
   protected main with required applicable checks and review policy, a
   `Production` branch rule admitting main only, and no allowed tags. Check
   required-reviewer, self-review and administrator-bypass settings. If the
   account plan or exposed tools cannot enforce a requested protection, record
   the precise gap and keep dispatch blocked until a separately reviewed
   enforceable alternative is accepted; do not silently remove the requirement.
   The owner has explicitly selected administrator bypass allowed for
   `Production`; retain and report that setting, and do not exercise a bypass.
   Gopinathan's verified account `Gopi-git-bit` / `200721521` is the designated
   environment reviewer. Self-review is permitted so this same human can
   dispatch and approve; this supplies owner approval, not independent review.
   The coding agent must not submit the environment approval on the owner's
   behalf. Keep main's administrator enforcement separate from environment
   bypass: main still requires one PR approval and all five strict CI checks.
4. Verify `DEEPSEEK_STAGING_API_KEY` exists in `Production`, with no same-named
   repository or applicable organization secret. Record only names, scopes,
   metadata timestamps and sanitized ownership evidence. Existing generic keys
   are outside this PR's mutation scope. Key replacement invalidates prior
   provenance evidence; presence alone does not establish dedication.
5. Obtain explicit owner authorization for **one DeepSeek presence-only run**
   against the reviewed merge SHA and environment. Dispatch `validate-secrets.yml`
   on main with `provider=deepseek`, confirm the resolved run SHA before the
   environment approval, and reject drift or an unexpected workflow/event/ref.
   An approval to review code is not authorization to expose a real secret to a
   job. An OpenRouter presence run requires its own bounded authorization.
6. Capture actor, event/ref, actual source SHA, environment, run ID/attempt,
   approval evidence, job/step conclusions and sanitized presence message.
   Unexpected skips or a missing key are failures. After an uncertain dispatch,
   inspect existing runs instead of dispatching again. Finish after this one
   run; success grants no subsequent provider, deployment or VPS authority.

The 16 October 2026 owner follow-up authorizes preparation/publication of the
actor restriction and names the environment approver. The owner's bounded
DeepSeek-only acknowledgement is recorded; no dispatch occurs during this code
change. Review and merge the corrected head through main's enforced PR controls,
verify post-merge CI and fresh settings/secret metadata, then present the one
resolved run to the owner for the actual environment approval. This does not
authorize OpenRouter, a rerun, a bypass, deployment or live inference.

Expected outcome: `PRESENCE_OBSERVED_REVIEW_REQUIRED`, an operator assessment,
not a new workflow-emitted readiness status. If any prerequisite is unverified,
the gate remains `NOT_AUTHORIZED_OR_NOT_VERIFIED` without a dispatch.

## Delivery gate: secret-free build and manifest validation

D-43 authorizes bounded preparation through separate PRs. The first inventory
records the current gaps; implement and review the build/test route before CD:

- PR CI checks applicable unit/integration/security tests and formatting without
  modifying source. Preserve accepted disposable database evidence and make
  unexecuted database cases explicit; mock success does not certify a live DB.
- Build from an exact reviewed SHA on a GitHub-hosted runner, with read-only
  checkout credentials not persisted. Use verified action SHAs and record the
  toolchain/dependency/image versions, local image ID and sanitized test reports.
  An unpushed local image ID is not a registry manifest digest.
- Validate a reviewed staging deployment manifest and configuration contract
  using placeholders. Do not infer the missing production Compose/authentication/
  pricing contract or insert secret values into image layers or build arguments.
- Publish packages/artifacts only through a separately reviewed minimum-permission
  job. Registry writes, OIDC trust or deployment credentials require their own
  explicit scope; this design adds no publishing or deployment job.
- A future manual staging deployment must consume the exact accepted artifact
  digest, obtain environment approval and prove target identity, isolated mounts,
  effective network policy, health checks and scoped rollback. Merge, build and
  secret presence must not automatically start or restart a VPS service.

The existing `deploy-hostinger.yml` job remains disabled. No `workflow_run`,
`pull_request_target`, automatic deployment, mutable-branch rollout, provider
probe or credential-copy step is introduced here. Do not reuse a presence
workflow environment approval as approval for deployment or inference.

## Remaining M7 gates and preserved boundaries

The accepted credential-free VPS diagnostic remains recorded past evidence; do
not rerun it as part of this PR. Effective synthetic egress, dedicated credential
ownership and target injection, provider claim/circuit-state isolation, enforced
monetary spending and trusted endpoint/model/source/UID/credential/limits/expiry
bound one-use authority remain separate acceptance gates. Their absence keeps
live M7 denied even after presence succeeds.

DeepSeek keeps its existing single-provider profile; no model switch or automatic
Qwen fallback is added. Qwen still needs an exact model/provider route, separate
credential, reviewed fallback behavior and aggregate budget. No new provider
smoke test, balance probe, business mutation or VPS change is needed for this
repository slice. D-33 remains pending; every refund requires manual approval.

References: [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[environment protections](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments),
and [secret scope](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).
See also [actor and triggering-actor context](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts).
