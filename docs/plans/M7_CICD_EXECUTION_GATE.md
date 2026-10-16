# M7 GitHub CI/CD execution gate

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

## Next execution gate: one authorized DeepSeek presence check

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

Expected outcome: `PRESENCE_OBSERVED_REVIEW_REQUIRED`, an operator assessment,
not a new workflow-emitted readiness status. If any prerequisite is unverified,
the gate remains `NOT_AUTHORIZED_OR_NOT_VERIFIED` without a dispatch.

## Subsequent delivery gate: reproducible build and deployment dry run

Design a separate PR for a secret-free build/test route before enabling CD:

- PR CI checks applicable unit/integration/security tests and formatting without
  modifying source. Preserve accepted disposable database evidence and make
  unexecuted database cases explicit; mock success does not certify a live DB.
- Build from an exact reviewed SHA on a GitHub-hosted runner, with read-only
  checkout credentials not persisted. Use verified action SHAs and record the
  toolchain/dependency/image versions, image digest and sanitized test reports.
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
