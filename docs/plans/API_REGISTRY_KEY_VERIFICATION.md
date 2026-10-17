# Registry and artifact-key verification procedure

**Date:** 17 October 2026. **Decision/evidence:** D-48 / M7-E012.
**Status:** PROCEDURE FOR REVIEW; NOT EXECUTED.
Baseline: `2fabdd8eaa16435d705a769d8cb15e8460a665ae`.
This is the reviewed planning baseline, not a future dispatch SHA. Bind each
execution to its then-current approved main/workflow and green post-merge CI.
[Publisher contract](API_CANDIDATE_PUBLISHER.md).
The [database CI proposal](DISPOSABLE_POSTGRES_CI_PROPOSAL.md) is independent.

This procedure prepares verification of `ghcr.io/gopi-git-bit/zippy-api` and
the age key used to encrypt candidate artifacts. It authorizes no operational
action. No package, environment, protection rule, policy field or key is changed
by preparing or merging this document. Publication and live M7/Qwen remain denied.

## Evidence gates

| Stage | Permitted scope after its separate authorization | Success evidence |
|---|---|---|
| A — settings inspection | Read existing package, repository, environment and secret-name metadata with an already authorized owner session | Exact identity/private visibility/linkage; independent ACL review; environment protection and key-scope snapshots |
| B — key verification implementation | Separate code PR for a synthetic canary verifier; no image build or package write | Reviewed workflow/helper/tool pins, offline negative regressions, exact-head and post-merge CI |
| C — key setup, if missing | Explicitly approved generation/injection or rotation in a trusted owner context | Dedicated native age identity, approved public recipient, environment-only secret metadata and owner custody/rotation record |
| D — one canary run | One explicitly authorized synthetic decrypt check through environment approval | Same-run/source/ciphertext/hash binding, successful authenticated decryption, exact payload hash, bounded exit status and sanitized evidence |
| E — policy pin | Separate reviewed change after A/C/D evidence is accepted | Actual package ID, recipient, canonical access-review hash and expiry; no placeholder values |
| Publication | A new explicit decision after all publication prerequisites | Not authorized by any stage above; named reproducibility disposition also required |

Stages are not an instruction to execute them now. Key setup may precede the
canary only after its own scope is approved. An existing dedicated key can be
verified without generation or rotation. Never generate a key merely to make a
presence check pass.

If the package is unavailable, record UNKNOWN and stop registry acceptance.
A 403/404 does not distinguish absence from insufficient visibility. Creating
an image/package to discover its visibility is a publication/bootstrap action;
it is excluded. Crypto canary verification can proceed independently after
authorization, but cannot turn an unknown package into an accepted registry.

## Stage A: exact metadata collection

Use an already authorized owner session in a trusted review terminal or the
GitHub settings UI. No VPS/SSH session is needed. Do not introduce a PAT, expand
app scopes or print authentication tokens to work around a denied endpoint.
If the connector cannot read package/admin/secret metadata, retain UNKNOWN and
use owner-provided settings evidence through an approved route.

These are **future read-only collection commands**, not an acceptance program.
Run only after Stage A approval. Bash is required for this example. Commands
write metadata into a new private directory; they neither change GitHub settings
nor retrieve secret values. On a failed request, preserve partial evidence and
its exit status; do not interpret an empty/truncated response as absence.

```bash
set +x
set -euo pipefail
umask 077
review_dir=$(mktemp -d "${TMPDIR:-/tmp}/zippy-api-prepub.XXXXXXXX")
gh api --hostname github.com --method GET user --jq '{login,id}' > "$review_dir/operator.json"
gh api --hostname github.com --method GET repos/Gopi-git-bit/New-logistic-/branches/main \
  --jq '{name,sha:.commit.sha}' > "$review_dir/source-main.json"
gh api --hostname github.com --method GET repos/Gopi-git-bit/New-logistic- \
  --jq '{id,full_name,visibility,owner:{login:.owner.login,id:.owner.id,type:.owner.type}}' \
  > "$review_dir/repository.json"
gh api --hostname github.com --method GET users/Gopi-git-bit/packages/container/zippy-api \
  --jq '{id,name,package_type,visibility,owner:{login:.owner.login,id:.owner.id},repository:{id:.repository.id,full_name:.repository.full_name}}' \
  > "$review_dir/package.json"
gh api --hostname github.com --method GET repos/Gopi-git-bit/New-logistic-/environments/Candidate-Publication \
  --jq '{id,name,protection_rules,deployment_branch_policy}' \
  > "$review_dir/environment.json"
gh api --hostname github.com --method GET --paginate --slurp \
  'repos/Gopi-git-bit/New-logistic-/environments/Candidate-Publication/deployment-branch-policies?per_page=100' \
  > "$review_dir/branch-policy-pages.json"
gh api --hostname github.com --method GET --paginate --slurp \
  'repos/Gopi-git-bit/New-logistic-/environments/Candidate-Publication/secrets?per_page=100' \
  > "$review_dir/environment-secrets-pages.json"
gh api --hostname github.com --method GET --paginate --slurp \
  'repos/Gopi-git-bit/New-logistic-/actions/secrets?per_page=100' \
  > "$review_dir/repository-secrets-pages.json"
printf 'metadata_directory=%s\n' "$review_dir"
```

Capture UTC observation time, operator/session identity, request path, exit
status and response-file hash for each command in the private review ledger.
The paginated secret lists contain names/timestamps, not values. Keep these
snapshots private and extract only the target key's scope/count into the
sanitized acceptance record.
The commands do not implement that ledger or declare PASS; the future collector
must do so before automated acceptance. Failed requests and unavailable UI
settings remain explicit gaps.

| Check | Required evidence / failure condition |
|---|---|
| Owner/repository | Owner Gopi-git-bit, ID 200721521; repository Gopi-git-bit/New-logistic-, ID 1349197102; public source visibility recorded |
| Package | Actual positive package ID, name zippy-api, container type, private visibility, matching owner and repository linkage |
| Effective package ACL | Owner settings evidence for readers/writers, inheritance and repository Actions grant; reject public/anonymous read access, unexpected writers or ambiguous inheritance. The package GET alone does not prove the ACL. |
| Dedicated environment | Candidate-Publication; never infer its settings from Production. Required owner reviewer ID 200721521, branch restriction exactly main, no tags/wildcards/other branches. A protected-branches-only policy is insufficient if it admits another protected branch. |
| Solo-owner review | Propose prevent_self_review=false so the owner can approve their own explicit request. This is not permission for an agent to approve its own gate. |
| Administrator bypass | Propose bypass disabled for this dedicated environment. Verify in the owner UI if the GET response omits it; missing is UNKNOWN, not false. Changing any existing setting requires separate approval. |
| Branch policy API | Require all pages and distinguish branch rules from tag rules. If the response omits the rule type, obtain UI evidence; a name of main alone cannot prove branch-only scope. |
| Secret scope | Exactly the intended name in this environment, no repository alias. For this personal-owner repository, organization scope is N/A only after owner type is verified; a changed ownership model requires a new review. |
| Storage/cost | Owner-approved readers, candidate storage/retention and cleanup ownership. One-day Actions retention does not enforce a registry deletion date. No package deletion is granted. |

Secret metadata proves location/name/update time, not value validity or key
matching. The managed repository app may lack the permissions required to read
some settings. Do not weaken this procedure to fit that connection.

## Stages B through D: real cryptographic verification without publication

The verifier is proposed code, not an existing workflow. Do not dispatch
`.github/workflows/api-candidate.yml` as a key test: that route includes a
candidate build and push. Implement a distinct manual-only verifier first.

Proposed verifier contract:

- Canonical repository/main; exact reviewed source/workflow SHA; owner login/ID,
  same triggering actor, first attempt, green post-merge CI and a five-minute
  authorization window checked before secret use. Separate verification scope;
  do not borrow the publisher's gap-acceptance/publication authorization.
- Hosted ubuntu-24.04; contents:read and actions:read only when CI/artifact
  metadata reads require them. No packages:write, id-token, admin permission,
  provider key or Production environment reference.
  Verify github-hosted runner identity, Linux and X64 before using a secret.
- A credential-free producer creates a tiny, public synthetic canary bound to
  source/run/nonce and encrypts it to the reviewed recipient. Maximum plaintext
  4 KiB and ciphertext 16 KiB. Transfer uses an immutable artifact ID and content
  hash, never a caller-supplied URL or arbitrary uploaded archive.
- A separate Candidate-Publication job waits for explicit owner environment
  approval, then reads only CANDIDATE_AGE_IDENTITY for that step. The workflow's
  public recipient comes from a reviewed verification manifest bound to source;
  arbitrary dispatch overrides are rejected. After Stage C, pin the derived
  recipient in that manifest through review before Stage D. This does not fill
  the publisher policy before acceptance.
- Use the existing pinned age v1.3.2 release archive identity from
  `infra/publication/api-candidate-policy.json`. Validate the archive and selected
  regular executable. No floating install or plugin/SSH key identity; choose
  one dedicated native X25519 age identity. Tool setup must not receive the key.
- Decrypt with the approved identity in a private temporary file; check
  authenticated decrypt success and exact expected plaintext SHA-256 before
  recording key_match=true. No key, private path contents or raw tool error is
  printed. Wrong key, changed ciphertext, wrong source/run, timeout or mismatched
  hash is a failed/unknown result.
- Five-minute job bound; individual crypto command capped at ten seconds;
  one attempt, no automatic replay. Enforce payload bounds before reading/decrypt.
  If approval outlives the authorization window, deny and request a new scoped
  run rather than extending the old request.
- Remove only this run's identity/plaintext/ciphertext/temp files. Cancellation
  cleanup is a hosted-runner limitation and must not be labelled verified.
  Emit only status, source/run, recipient fingerprint, artifact/cipher/plaintext
  hashes, timestamps, exit status and cleanup outcome.

On the owner's trusted machine, the pinned age-keygen's public-recipient
derivation can corroborate a single existing identity. Verify its archive/member
identity first; the current publisher installer installs age, not age-keygen.
Do not assume a second binary is already installed or request the private key
in chat. Key generation/injection, custody, backup, expiry and rotation remain
Stage C actions; no command here provisions a secret.

## Acceptance record and policy pin

Produce one canonical UTF-8/LF JSON record with schema, owner reviewer,
observation/expiry times, reviewed source, package/owner/repository IDs, ACL and
environment snapshot hashes, complete branch-scope evidence, bypass decision,
secret-name/scope metadata hashes, public recipient/fingerprint, canary
run/artifact/content hashes and outcome, retention/cost decision and every gap.

Propose observations no older than 24 hours at acceptance and an access-review
expiry within seven days. These are proposed verifier requirements, not limits
already enforced by the current publisher. Its policy checks expiry but cannot
establish the truth of an opaque review hash.

The private record must contain no secret values. Retain it under owner-approved
private access; pin its actual SHA-256 and expiry only after review. A valid
hash-shaped placeholder is not evidence. Refresh stale/changed settings before
publication and independently recheck package identity/private visibility.

Stage E changes only the four verified policy fields via a reviewed PR; normal
protections and post-merge CI still apply. It does not authorize the publisher
dispatch, waive REPRO-01 through REPRO-04 or close database/runtime/provider
gaps. If Stage A or D fails, leave the policy unset. Stop; no package creation,
visibility mutation, automatic key replacement or repeated provider smoke test.

Record distinct settings-observation, canary-verifier and policy-pin source
identities. A policy-only pin advances main after the canary; review must prove
that the verifier workflow, tools and recipient bytes are unchanged and the
settings/key evidence remains valid. Changed verifier/key inputs require new
scoped evidence. Never relabel an older canary's SHA as the publication SHA.

Rollback of this planning PR is a reviewed documentation revert. Future
verification cleanup is exact local temporary-resource cleanup only. Shared
package deletion, key revocation/rotation and environment-policy changes each
need their own concrete scope. D-33 and manual refund approval remain unchanged.

Primary references:
- [GitHub environment metadata](https://docs.github.com/en/rest/deployments/environments#get-an-environment)
- [GitHub branch/tag policies](https://docs.github.com/en/rest/deployments/branch-policies)
- [GitHub secret metadata](https://docs.github.com/en/rest/actions/secrets#list-environment-secrets)
- [GitHub CLI API collection](https://cli.github.com/manual/gh_api)
- [age v1.3.2 manual](https://github.com/FiloSottile/age/blob/v1.3.2/doc/age.1.ronn)
