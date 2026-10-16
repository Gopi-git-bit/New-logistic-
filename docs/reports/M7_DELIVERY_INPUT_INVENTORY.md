# M7 delivery inputs: inventory and gap register

**Date:** 16 October 2026. **Decision/evidence:** D-43 / M7-E007.
**Scope:** first delivery-preparation slice under the owner's continuation approval.
**Source:** [main at `6a6f5acd00a6aafa115f1e470821512f5434021f`](https://github.com/Gopi-git-bit/New-logistic-/tree/6a6f5acd00a6aafa115f1e470821512f5434021f),
tree `6d15373d8aa4b2180bc730abc33add6d22db2ef5`.

## Result and method

The API is the smallest candidate for a **build-only** follow-up: its Python
base is digest-pinned, its runtime lock contains hashes, and its Dockerfile
selects UID/GID 10001. This is a candidate selection, not a successful build.
No container image, local image ID, manifest render, startup, health check or
deployment is claimed by this inventory.

Inspected the complete pinned Git tree (315 tracked files), all five Dockerfiles,
their Compose contexts, dependency declarations/locks, API configuration,
checked-in environment examples, M7 unit templates and existing CI/deployment
definitions. Compared variable **names**, not secret values. Static lock checks
compare declared pins and hash syntax; no dependency download, resolution,
vulnerability assessment or wheel/hash verification was performed.

This PR changes records only. Dockerfiles, dependencies, configuration, templates
and workflows retain their source behavior. Existing accepted database and
presence proofs are reused without rerunning them.

## Dockerfiles and build contexts

Contexts below are the ones declared by [docker-compose.yml](../../docker-compose.yml).
No root or Dockerfile-specific `dockerignore` exists in the pinned tracked tree.

| Target / Dockerfile | Declared context and inputs | Static findings / disposition |
|---|---|---|
| API: [Dockerfile.api](../../Dockerfile.api) | Root `.`; copies `api/` and `requirements-api.lock` | `python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea`; pip `--require-hashes`; UID/GID 10001. Best candidate. Apt indexes/packages and installer provenance still float. The two API COPY operations are redundant cache work. |
| Workers: [workers/Dockerfile](../../workers/Dockerfile) | `./workers`; pyproject, then editable install, then source | Mutable Python base; unpinned apt packages; no USER; dev dependencies included. Installation precedes copying `src`: a build-order risk requiring an actual build, not a demonstrated failure. Defer until worker locking/build contract is addressed. |
| Portal: [apps/portal/Dockerfile](../../apps/portal/Dockerfile) | `./apps/portal`; package metadata, optional lock glob, app source | Mutable Node/Alpine inputs; frozen pnpm installation has no tracked lock. Workspace dependencies are outside this context. Standalone output is configured in Next, but `public/` is absent from the tracked tree and is a runtime COPY source. Runtime UID 1001. Not selected. |
| Console: [apps/console/Dockerfile](../../apps/console/Dockerfile) | `./apps/console`; package metadata, optional lock glob, app source, nginx config | Same missing lock/workspace visibility issues; mutable Node and nginx bases; no runtime USER. Its nginx config listens on 80 while Dockerfile EXPOSE and Compose target use 3000. Not selected. |
| Database: [infra/docker/Dockerfile.db](../../infra/docker/Dockerfile.db) | `./infra/docker` | Mutable PostGIS tag and apt/pgvector package resolution. This legacy application DB image is distinct from the digest-pinned disposable-proof PostgreSQL artifact. Do not start either for this inventory. |

A missing context filter does not mean every root file is copied into the API
image: its COPY statements are explicit. It does mean a reviewed secret-free
context boundary is missing. A future build must establish that boundary,
including untracked local files; the pinned Git inventory cannot attest a
developer's working directory.

Portal and console use `workspace:*` packages under root `packages/`, outside
their app-only contexts. Root `packageManager: pnpm@9.14.0` is not copied into
those contexts. The console port finding is a static configuration mismatch,
not a new network observation.

## Dependency lock coverage

| Surface | Pinned-source observation | What remains unverified |
|---|---|---|
| [API runtime input](../../requirements-api.txt) / [lock](../../requirements-api.lock) | Five exact direct pins, including PyJWT; 17 locked distributions; every locked requirement has a SHA-256 hash; all five direct versions agree | Actual package availability, downloaded bytes, resolver compatibility and image build |
| [API dev input](../../requirements-api-dev.txt) / [lock](../../requirements-api-dev.lock) | Four additional exact dev pins plus runtime include; 31 locked distributions; hash syntax present throughout; all nine direct runtime/dev versions agree | Current API and disposable DB CI install the `.txt` input rather than enforcing this lock with `--require-hashes` |
| [Workers](../../workers/pyproject.toml) | Python >=3.11; tooling targets 3.12; runtime lower bounds; unpinned Hatchling build backend; no tracked worker lock/constraints | Reproducible runtime/dev installation and compatibility with the Python 3.12 container |
| [Node workspace](../../package.json) / [workspace definition](../../pnpm-workspace.yaml) | Root pnpm 9.14.0; Node >=20; ranged dependencies; no tracked pnpm, npm, Yarn or Bun lock | Resolved workspace graph/integrities, package-manager bootstrap provenance and valid shared-package build contexts |
| OS / actions | API base digest pinned; other inspected Dockerfile bases mutable; apt/apk packages mutable; current CI uses mutable action references | Full toolchain/package provenance and security evidence; no claim of bit-for-bit reproducibility |

The lock check establishes syntax and version agreement only, including API
runtime pins inherited by the dev input. Hash presence is not proof that the
corresponding packages were downloaded or audited. No lock was regenerated.

The [M1 lock strategy](M1_DEPENDENCY_LOCK_STRATEGY.md) remains a historical report
at its own baseline. Its no-Python-lock, missing-PyJWT and mutable-API-base
findings are superseded for this snapshot; its missing Node/worker lock concerns
still apply.

## API configuration contract

[api/config.py](../../api/config.py) is authoritative for settings validation.
It admits only `APP_ENV=development|test`, `AUTH_MODE=test_jwt` and a `test-`
pricing policy. It deliberately rejects production authentication/pricing.
[api/main.py](../../api/main.py) opens both operational and Paperclip database
pools during application lifespan. Building or parsing configuration must not
start that lifespan or contact a database.

| Required name or group | Contract in current source | Root Compose API service |
|---|---|---|
| DATABASE_URL | Nonempty operational connection string | Passed through; no validity/connection claim |
| ZIPPY_PLATFORM_ID | UUID | Missing |
| APP_ENV / AUTH_MODE / AUTH_JWT_SECRET | Test/development only; test_jwt; secret at least 32 characters | APP_ENV passed/defaulted; AUTH_MODE and AUTH_JWT_SECRET missing |
| M3_PRICING_POLICY_VERSION / M3_PRICING_CURRENCY | Explicit test policy; uppercase three-letter currency | Both missing |
| M3_PRICING_BASE_AMOUNT / M3_PRICING_PER_KM / M3_PRICING_PER_KG | Finite nonnegative decimal settings | All missing |
| PAPERCLIP_DATABASE_URL | Nonempty separate governance connection string | Missing |
| PAPERCLIP_OWNER_SUBJECT / PAPERCLIP_EXECUTOR_SUBJECT | Nonempty, different subjects; neither may be a proposal agent | Both missing |
| PAPERCLIP_POLICY_ID / PAPERCLIP_AGENT_BINDINGS_JSON | UUID policy; nonempty agent map with unique UUID values | Both missing |
| PAPERCLIP_ENVELOPE_SIGNING_KEY | At least 32 characters under current validation | Missing |
| PAPERCLIP_ENVELOPE_TTL_SECONDS | Optional override; default 300, allowed range 1–300 | Omitted; default applies |

Of 15 names required to satisfy this adapter explicitly, Compose forwards only
DATABASE_URL. Its Supabase JWT, Paperclip URL and API key settings are different
names/contracts and do not substitute for the missing fields.

The checked-in [.env.example](../../.env.example) lacks eight required API names:
ZIPPY_PLATFORM_ID, AUTH_MODE, AUTH_JWT_SECRET and all five M3_PRICING names above.
[.env.production.example](../../.env.production.example) lacks the 14 required
names missing from Compose and selects a production environment that this API
adapter rejects. These are example-file findings, not inspection of live keys.
Adding names alone would not establish a production authentication or pricing
contract. RAZORPAY_WEBHOOK_SECRET has a default in Settings; that default does
not establish payment/webhook readiness.

The worker settings explicitly disable automatic `.env` loading and default
telemetry to disabled/zero sampling. They are not the M7 runner's credential
injection contract. No generic provider keys should be added to a build path.

## Staging templates and delivery route

All five [M7 unit templates](../../infra/m7-staging) use explicit source
read-only binds and are reviewed preparation artifacts. This inventory does not
verify what is installed on any VPS.

| Template | Declared role and boundary |
|---|---|
| zippy-oms-staging-probe.service.in | Credential-free observations; probe-only marker; five-second start bound; no provider key/state store |
| zippy-oms-staging-credential-probe.service.in | Separate marker and LoadCredential; metadata-only credential probe; five-second start bound |
| zippy-oms-staging.service.in | Disabled provider execution preparation; credential marker/source, private state, direct DeepSeek profile, future SHA/grant placeholders; 12-second start bound |
| zippy-oms-staging-egress-probe@.service.in | Separate marker; calibration/restricted synthetic client; 18-second start bound |
| zippy-oms-staging-synthetic-peer.service.in | Separate marker and peer namespace; bounded synthetic listener; 42-second start bound |

The [namespace firewall template](../../infra/m7-staging/egress.nft.in) declares
three drop-default chains, four empty destination sets and seven rules. Static
source inspection is not effective-egress evidence. Provider enablement and
future authorization placeholders must remain denied.

These systemd files are **not** an application staging Compose manifest.
The existing root Compose includes databases, Redis, a legacy Odoo profile,
a Honcho placeholder, workers, API and frontends on a shared bridge, published
ports and persistent volumes. It does not establish the isolated M7 boundary.

The disabled [Hostinger workflow](../../.github/workflows/deploy-hostinger.yml)
remains manual with `if: false`; it references
`docker-compose.production.yml`, which is absent from the complete pinned tree.
It is not a usable delivery route and must stay disabled.

The five-job [CI workflow](../../.github/workflows/ci.yml) parses root Compose
using the example environment; it does not build images or prove API startup.
Its worker install floats dependencies, API install does not enforce the dev
lock, Trivy uses a mutable action reference, and worker formatting runs in
mutation mode. A green historical CI result does not resolve those gaps.
The [disposable DB workflow](../../.github/workflows/disposable-db-proofs.yml)
is a separate synthetic proof path; retain its accepted evidence and scope.

## Gap register and implementation handoff

These are source gaps, not newly observed production incidents. The owner's
continuation approval starts delivery preparation; the remaining implementation
below is sequenced work, not a request to repeat that authorization. Each
resulting change still needs its own reviewed head, CI and separate merge gate.

| ID | Observed gap | Disposition / required follow-up |
|---|---|---|
| DELIVERY-01 | No reviewed API build-context filter | First implementation: establish a Dockerfile-specific allowlist or isolated staged context; reject secrets, caches, VCS metadata and unrelated work. Prove expected runtime source remains visible. |
| DELIVERY-02 | API apt/toolchain inputs still float; no image built here | Record remaining mutable inputs; build the selected API image on an ephemeral runner without registry login/push or secrets. Capture source/tool versions and local image ID; do not call it a registry digest. |
| DELIVERY-03 | API/dev hash locks exist, but current CI does not consume the dev lock | Validate lock coverage and adoption in a scoped follow-up. Do not relock or upgrade packages just to complete this inventory. |
| DELIVERY-04 | Missing worker and workspace locks; worker copy order and frontend contexts incomplete | Separate dependency/build-contract work; defer those images from the initial API build proof. Preserve application behavior and existing tests. |
| DELIVERY-05 | Current Compose/examples omit required API adapter settings | Prepare a distinct placeholder-only staging-validation contract. Exercise config validation without importing application lifespan or opening pools; reject production mode and missing fields. Do not weaken api/config.py. |
| DELIVERY-06 | Production auth/pricing contract and production Compose absent | Keep production blocked. A parseable staging test fixture is not a production contract. |
| DELIVERY-07 | No implemented bounded secret-free delivery workflow | Use the blueprint's manual canonical-main, fixed-owner, source-bound, finite-time route; pin action identities, use minimum checkout read permission with no persisted credentials, no Production environment or secret binding. No automatic deployment. |
| DELIVERY-08 | Console target port mismatch and portal public COPY source absent | Resolve separately with frontend scope and actual build evidence; do not claim either app builds successfully. |
| DELIVERY-09 | M7 live credential, egress, state, cap and authorization evidence incomplete; Qwen disabled | Independent live gates remain blocked. GitHub secret presence and a future image build cannot clear them. |

**Selected next engineering slice:** API context boundary, existing lock
consumption, placeholder-only API configuration/manifest validation and their
offline negative regressions, followed by bounded build preparation under the
[delivery blueprint](../plans/M7_SECRET_FREE_DELIVERY_BLUEPRINT.md). A future
manual build must use its exact reviewed/merged source and leave the image
unpublished. Do not start API, worker, database, synthetic peer or M7 services.

**Review acceptance for this inventory:** pinned-source paths and factual
claims reconciled; direct pins/hash syntax checked; links/decision/evidence/
tracker references validated; exact-head ordinary CI recorded on its PR.
Image build, package availability, Compose rendering and live readiness remain
NOT RUN or UNVERIFIED until supported by their own evidence.

**Rollback:** before merge, discard only this feature branch's record changes.
After merge, propose a reviewed documentation revert. There is no infrastructure
or application rollback to execute for this records-only PR. D-33 stays pending;
manual refund approval, deterministic assignment, RPC/RLS, settlement and
governance controls are unchanged.
