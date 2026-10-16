# API delivery preparation: context and offline staging contract

**Date:** 16 October 2026. **Decision/evidence:** D-44 / M7-E008.
**Base main:** `5ce410e954661e58cc07e1c211ebd37ed0309180`.
**State:** implementation prepared for PR review; image build/publication NOT RUN.
This slice implements the first API context/lock/configuration follow-up to the
[pinned inventory](../reports/M7_DELIVERY_INPUT_INVENTORY.md).

## Implemented contract

[prepare_api_build_context.py](../../scripts/prepare_api_build_context.py)
requires a full 40-character commit ID matching the repository HEAD. It reads
Git objects at that commit, not the working-tree contents. It exports only
Dockerfile.api, requirements-api.lock and regular tracked API Python source,
excluding the three test directories. It refuses unknown runtime file types,
symlinks, missing entrypoints, unsafe/unhashed/duplicate lock requirements,
existing destinations and destinations inside the checkout. Dirty tracked files
and unrelated/untracked files are preserved and excluded. A tracked Python file
still needs ordinary source/secret review; this is not a general secret scanner.

The new destination receives source copies only, after all inputs pass checks.
The returned report identifies source commit/tree, every file's Git blob SHA-1
and content SHA-256, and a SHA-256 of the sorted file-identity manifest. That
manifest identity is not a Docker image ID, tar/mtime digest or registry digest.
Filesystem timestamp normalization and bit-for-bit image reproducibility are
not established. It records no
dependency downloads because this helper performs none. Git commands ignore
ambient Git-directory/config/replacement-object settings and use no network.

Dockerfile.api retains its base digest, hash-locked runtime installation and
UID/GID 10001. Removing the redundant early API COPY lets dependency caching
depend on the lock instead of application source. Runtime identity and build
success remain unobserved until an actual image is built and separately tested.

[api-validation.compose.json](../../infra/staging/api-validation.compose.json)
is a parse-only fixture, not a deployable application topology. It has one
profile-gated service, unpublished local image name, /bin/false entrypoint,
network none, fixed nonroot user, read-only root, dropped capabilities and no
ports, mounts, build instructions, external environment files or dependencies.
The placeholders are deliberately public synthetic data; they grant no authority.

[validate_api_staging_config.py](../../scripts/validate_api_staging_config.py)
requires the exact allowed schema/controls and environment names. It rejects
duplicate JSON keys, provider keys, interpolation, production mode and nonzero
synthetic price inputs. Connection strings must be the fixed .invalid examples
and both signing values must be the documented non-secret placeholder. It loads
canonical api/config.py source directly, without bytecode caches, api.main or
database imports, and calls load_settings using only fixture values. It restores
its own environment/module state afterward. This is a single-process offline
CLI tool, not an API middleware or an isolation sandbox. Results never include
configuration values or raw parser/settings exceptions.

## Secret-free validation commands

Run in an isolated reviewed checkout. These commands create only a fresh
temporary context and parse configuration; they do not build or start anything.

```bash
set -euo pipefail
task_dir="$(mktemp -d)"
trap 'rm -rf -- "$task_dir"' EXIT
python3 -I scripts/prepare_api_build_context.py \
  --repo-root "$PWD" --source-sha "$(git rev-parse HEAD)" \
  --output "$task_dir/context" > "$task_dir/context-manifest.json"
cat "$task_dir/context-manifest.json"
python3 -I scripts/validate_api_staging_config.py --repo-root "$task_dir/context" \
  --manifest "$PWD/infra/staging/api-validation.compose.json"
docker compose --env-file /dev/null -f infra/staging/api-validation.compose.json \
  --profile validation-only config --quiet
```

The helper itself does not authorize a source SHA for a future manual build.
A future build route must enforce the blueprint's reviewed canonical-main/owner
admission and record actual checkout/workflow/run identity. The current PR CI
exports its actual checked-out commit, which may be GitHub's PR test merge.
It does not substitute that test merge for a later approved main source.

## CI and verification

The existing compose-config job has a five-minute bound, read-only checkout
without persisted credentials, private runner-temporary context, explicit
cleanup trap, helper validation and Compose parse only. The settings
validator reads api/config.py from the committed staged context, not a dirty
working-tree copy. The existing api-tests
job has a ten-minute bound and installs the unchanged
requirements-api-dev.lock with --require-hashes. It checks helper lint/format
and strict types. Workflow token permissions are contents:read. Worker CI
discovers the new offline regression module; no new manual workflow or Production
environment/secret reference is introduced. Existing disposable DB proofs are
not rerun for these paths; their install policy remains a separate follow-up.

Initial local evidence: 16 unittest cases passed on Python 3.12.14.
The PR #26 lock-name review correction now passes 17 cases, zero skips/warnings;
Ruff check/format and strict helper MyPy pass. Subcases cover all 17 missing
environment names, unsafe service controls, malformed settings and locks, CLI
redaction, environment restoration, dirty/untracked source exclusion, symlink
denial, repeatable context identity and no-overwrite behavior. The settings
positive case forbids sockets and blocks application/database imports.
The exact resulting-head CI run and its actual outcomes must be recorded in the
PR audit after they exist. Local success is not a Docker Compose parse or image
build result; no CI pass is claimed prospectively.

## PR #26 review correction

The received review identified option-shaped distribution names passing the
lock parser. The new regression reproduced nine invalid-name acceptances before
the correction. Names now require alphanumeric first and last characters, while
single-character names and internal dots/underscores/hyphens remain accepted.
Integration cases prove option-shaped entries are rejected before creating a
context; normalized duplicate-name rejection and the real runtime lock still pass.
No lock contents, pip flags, runtime capabilities or provider route changed.

Original-head CI [38920878701](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38920878701) passed at
`a17dd6b2e8c82e61bb30a95fcd0f009a350bbc70`. The review correction requires its
own exact-head checks before merge; actual corrected-head and post-merge CI
must be recorded on [PR #26](https://github.com/Gopi-git-bit/New-logistic-/pull/26).

## Gap disposition and next gate

| Inventory gap | Change in this slice / remaining evidence |
|---|---|
| DELIVERY-01 | Isolated staged context implemented and regression-tested. Root Compose's raw context is unchanged; use the staged route for the future reviewed build. |
| DELIVERY-02 / DELIVERY-10 | API cache ordering improved; base platform/patch/toolchain observations, apt snapshot/version control and actual build/local image ID still pending. |
| DELIVERY-03 | API CI adopts the existing dev hash lock. Runtime Dockerfile already uses its lock; worker and disposable-proof installs are not changed. |
| DELIVERY-04 / DELIVERY-08 | Worker/Node locks, frontend contexts/COPY/port issues remain deferred. |
| DELIVERY-05 | A separate synthetic settings/Compose-validation contract is implemented. Existing root Compose/examples and production auth/pricing are unchanged. |
| DELIVERY-06 / DELIVERY-07 | Production stays blocked; no production Compose or manual image-build/publish/deploy route is added. |
| DELIVERY-09 | No live M7/Qwen gate changes. |
| DELIVERY-11 | Context input hashes are logged; image-build download origins/receipts, actual cache outcomes and whole-image reproducibility remain unverified. A successful locked CI install is not that ledger. |

The owner now authorizes PR #26 review, scoped correction and merge after exact
final-head CI, followed by post-merge verification. This supersedes the initial
merge-pending checkpoint for this PR only. A later bounded secret-free image build must log platform, tools,
dependency retrieval, local image ID and remaining gaps under the
[blueprint](M7_SECRET_FREE_DELIVERY_BLUEPRINT.md). Do not publish images, dispatch
real secrets, start services, touch a VPS or call providers under this PR.
No existing production workflow or M7/Qwen runtime registration is enabled.

## Cleanup and rollback

The CI trap removes only its newly allocated runner-temporary directory.
The exporter never overwrites or deletes an existing destination; an I/O failure
can leave a partial new context for scoped cleanup. Never reuse a failed context
for a build. Before merge, discard/correct this feature slice only; after merge,
propose a reviewed revert. No server, database or credential rollback is involved.
D-33 remains pending; deterministic assignment, RPC/RLS, idempotency, governance,
settlement and manual approval for every refund remain controlling.
