# API image build-only gate

**Date:** 16 October 2026. **Decision/evidence:** D-45 / M7-E009.
**Preparation base:** merged PR #26, `f8e7cb9a548e9956a0f1f74edc6f73e8fd2a76ef`.
**Current state, 17 October 2026:** PR #27 merged; one authorized build PASSED.
Publication and runtime activation remain NOT RUN.

PR #26 is merged. Its final reviewed tree is
`61fca5826a4fdcf018d1df077d10eea4681639ab` and
[post-merge CI 38924063418](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38924063418)
passed all five jobs. This continuation implements blueprint steps 3–4 as a
manual route; it does not execute them. The parent M7-DELIVERY-DRYRUN remains
IN_PROGRESS until separately authorized build evidence has been reviewed.

## Execution closeout

[Run 38995824366](https://github.com/Gopi-git-bit/New-logistic-/actions/runs/38995824366)
passed once at source/workflow SHA `0c96e33ac887b536ef4f947b9f4c7cbb395b80f9`,
tree `10d46eea1a7e085ec3b70402e91c3b43f7bd9134`. M7-E010 and the
[review](../reports/API_BUILD_EVIDENCE_REVIEW_20261017.md) record source/download
correlation, local config ID and scoped cleanup. The
[captured report](../reports/API_BUILD_ONLY_20261017.json) remains bound to that
run; no image remains for push. [Publication criteria](API_CANDIDATE_PUBLICATION_GATE.md)
are separate proposals. Earlier preparation/execution instructions are historical
and do not authorize a repeat run.

## Admission and permissions

[api-build-only.yml](../../.github/workflows/api-build-only.yml) has only a
workflow_dispatch trigger. The canonical repository, main ref, owner login
Gopi-git-bit, actor ID 200721521, same triggering actor, first attempt and matching
input/source/workflow SHA are required before checkout. Checkout uses the full
commit `11d5960a326750d5838078e36cf38b85af677262`, resolved from the official
actions/checkout v4 Git ref on 16 October 2026, without persisted credentials.
The script repeats admission and requires a GitHub-hosted Linux/X64 runner,
the exact workflow ref, matching clean HEAD and a full 40-character source SHA.

Token permission is contents:read only. No Production environment, secrets
reference, provider key, registry login, SSH, package/deployment write permission
or external artifact upload is configured. The checkout token is not forwarded
to child commands. Read-only checkout still uses GitHub's workflow token; this
is a secret-free application build, not a claim that GitHub has no credentials.
Dispatch inputs enter the shell through environment variables, not source-code
interpolation. Reruns are denied; each execution needs a new explicit decision.

## Build and download contract

[run_api_build.py](../../scripts/run_api_build.py) uses the committed-source
exporter, now including the reviewed build-metadata helper. The context contains
33 source inputs on this preparation base, not the checkout, .git, .env, tests or
untracked files. It validates canonical settings using the synthetic fixture
and parses Compose without starting a service. Root Compose remains unchanged.

The daemon is fixed to the hosted runner's local Unix socket. Child commands
receive a fresh empty Docker configuration and HOME, a fixed PATH and no ambient
credential/proxy/remote-Docker settings. The default buildx builder must use the
local docker driver. No builder/plugin installation or remote-builder fallback
is attempted. A missing tool or unrecognized output fails the gate.

The existing Python 3.12-slim digest is retained. The report records the declared
index reference and its selected linux/amd64 child-manifest digest. Docker
resolves the digest; this is not an independent transport capture. The build uses
--load, --pull, --no-cache, --platform linux/amd64, an iidfile and a metadata file.
There is no tag, push, cache export, build secret, SSH mount or application start.
Dockerfile RUN instructions execute dependency installation and receipt emission
as ordinary build steps; no application container is started afterward.

Dockerfile.api keeps its runtime lock and final UID/GID 10001:10001. Pip now uses
isolated mode, the explicit public PyPI index, binary-only artifacts, no cache,
forced reinstall, --require-hashes and a v1 installation report. Binary-only
installation prevents implicit source-build dependency downloads. A missing
compatible locked wheel fails; do not fall back to source builds. Forced reinstall
ensures even a matching base-installed package appears in the receipt.

[emit_api_build_metadata.py](../../scripts/emit_api_build_metadata.py) emits one
allowlisted build-log record: actual image Python/pip and OS versions, installed
dpkg package versions, and selected pip names, versions, sanitized public artifact
URLs and SHA-256 hashes. Only files.pythonhosted.org HTTPS artifact locations are
accepted; userinfo, query and fragment are omitted. Arbitrary pip metadata and
environment fields are dropped. The raw pip report/helper are removed in that
same RUN instruction. The host requires exactly one BuildKit receipt and matches
every selected pip artifact against the committed runtime lock. It never prints
raw build logs, image environment/configuration or command exceptions.

The report includes source/context identities, run/actor/workflow identity,
actual Docker client/server/buildx/Compose versions, command exit statuses or
timeouts, the local image config ID and its metadata-file correlation, configured
image user/platform and cleanup result. Inspecting configured image user is not
proof of a running process UID. The local config ID is not a registry digest or
deployment artifact. The exporter report's image_build=NOT_RUN describes its own
context-export operation; the enclosing build report supplies the build result.

## Time bounds, evidence and cleanup

One job runs on ubuntu-24.04 with a 15-minute limit and no concurrent duplicate
builds. The script allows 720 seconds for operations, at most 600 for the build,
and up to 15 seconds for image cleanup. A command failure, timeout, missing or
ambiguous receipt, source/platform mismatch or cleanup failure prevents success.
Stopping the Docker CLI is not independent proof that daemon work stopped;
hosted-runner teardown is the final boundary. No automatic retry is implemented.

The exclusive report is mode 0600 in runner temporary storage. An always step
copies only the sanitized report to logs and the GitHub job summary. No image,
raw pip report or raw build log is uploaded. Ordinary GitHub run retention/access
applies; summary retention is not an independent durable artifact archive.
Raw subprocess output is captured in process memory and not emitted. Newly
allocated context/Docker-config directories are removed on script exit. Only the
specific iidfile image is removed, and only if absent from the pre-build image
inventory. No broad prune is used; base layers/build cache are left to hosted
runner teardown. Timeout/cancellation can prevent cleanup; inspect actual
job/step conclusions and do not infer a pass from an absent report.

Remaining reproducibility gaps stay explicit: mutable apt repositories, missing
apt archive origin/hash receipts and snapshot pinning; unobserved transport
redirects/mirrors and effective egress; observed rather than locked hosted tools;
and no bit-for-bit whole-image reproducibility proof. Pip's hash enforcement and
installation report are evidence from pip, not independent download capture.
No provider/network-isolation, runtime, database, production or deployment
acceptance follows from a successful build. Existing 72 database-skipped API
tests and two warnings remain separately recorded; no gap is waived here.

### PR #27 review correction

The review reproduced malformed nested receipt output escaping the CLI error
boundary as AttributeError, leaving an empty report despite scoped image cleanup.
The corrected boundary also handles AttributeError and IndexError, writes
BUILD_NOT_VERIFIED with the failed stage and cleanup result, and records only
the exception class. Messages, raw tool output and partial dependency receipts
remain excluded. The new offline regression failed before the correction and
now passes through the real build/evidence flow with fake commands. All 32
affected local cases pass, plus scoped lint/format and strict helper typing.
No actual image build or workflow dispatch is needed for this regression.

## Next execution gate

1. Review this exact feature head and its offline/CI evidence.
2. Obtain separate merge approval, merge through protected main and verify
   post-merge CI plus source/workflow identity.
3. Obtain explicit authorization for one bounded manual build, specifying that
   exact current main SHA and dependency-download scope. Dispatch main with
   source_sha equal to that SHA; main movement causes admission denial.
4. Review actual job/step results, sanitized evidence and gaps. A skipped job is
   NOT_RUN, never a build pass. Stop after this build; publication/deployment,
   real-secret dispatch, VPS changes and provider execution need separate gates.

No dispatch command is executed by preparation or PR CI. Before merge, correct
or discard only this feature branch. After merge, use a reviewed revert of this
slice. There is no VPS/production rollback action in a local build-only workflow.
Live M7 and Qwen remain disabled. D-33 stays pending; deterministic assignment,
RPC/RLS, idempotency, settlement/governance and manual refund approval persist.

Primary interface references: [GitHub variables](https://docs.github.com/en/actions/reference/workflows-and-actions/variables),
[GitHub contexts](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts),
[Docker buildx build](https://docs.docker.com/reference/cli/docker/buildx/build/),
and [pip installation report](https://pip.pypa.io/en/stable/reference/installation-report/).
