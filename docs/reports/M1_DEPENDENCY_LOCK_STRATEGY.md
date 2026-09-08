# M1 Dependency Lock Strategy

## Scope and Verdict

**Task:** `M1-LOCK-STRATEGY`
**Baseline:** `0c19f4928cdd3296fa45d68310dd7d683be017ca`
**Method:** Static repository inspection and installed-runtime metadata only. No dependency installation, update, removal, lockfile generation, online vulnerability scan, or package resolution was run.

**Verdict:** Dependency ownership is sufficiently clear to define a controlled MVP locking policy, but the repository is not reproducible today. There is no Node lockfile, Python lockfile, or Python constraints file. Dockerfiles require a frozen pnpm install even though no `pnpm-lock.yaml` exists. Python manifests use broad lower-bound ranges, API CI bypasses the API manifest with an ad hoc install, Docker images use mutable tags, and GitHub Actions use mutable tags rather than immutable SHAs. No manifest or lockfile modification is authorized by this report.

## Static Inventory Method

The repository contains 19 dependency/runtime declaration artifacts. Checksums below are SHA-256 at the baseline. A missing lockfile has no checksum and is stated explicitly. Source-import comparisons are static only: a zero usage count is an apparent-unused signal, not proof of removal eligibility.

## Ecosystem Inventory

| Ecosystem / path | SHA-256 | Manager / required runtime | Version and lock state | Production / dev classification | Reproducibility and security risk | MVP disposition |
|---|---|---|---|---|---|---|
| Root Node workspace: `package.json` | `55f12ffce9bce7ebf045a5e68ca8921518c4fe5be7db73786d6aefafdf42cc53` | pnpm `9.14.0`; Node `>=20`, npm `>=10` | Root dev tools use caret ranges; `pnpm-lock.yaml` missing | Build/dev orchestration | Frozen install cannot succeed without a lockfile; unbounded engine floors permit drift | retain; lock later |
| Workspace: `pnpm-workspace.yaml` | `08d75840c97ab0e72d1d9b5b84a17e47a2e06cb159a5fbec5ee0a6a56682dad7` | pnpm workspaces | Apps/packages only; no lock ownership stated | Build topology | Root workspace is the correct lock scope but has no resolved integrity state | retain |
| Turbo: `turbo.json` | `fcd7fb588111f24645b1efad34dc9c05095e004c5a886164a0fd6cd932d3d8ff` | Turbo/Node | Depends on `.env*`/infra as global cache inputs | Build/dev | Secrets/environment names may invalidate broad cache scope; no lock resolves Turbo version | rewrite later |
| Biome: `biome.json` | `39c5c1bb10a3676ea87bc0b2c8073cfa335912598ebbb718f318905952b1c687` | Biome/Node | Tool version comes from root caret range | Dev/CI formatting/lint | Version drift may rewrite files differently in CI and local environments | retain; lock later |
| Portal: `apps/portal/package.json` | `0a815971208d967ed6759d3548f48f9a5bc5c59e32e520f7a032293147125d1a` | pnpm/Node 20 | All external dependencies use caret ranges; no app or root lockfile | Frontend build/runtime plus dev test tools | Docker requires missing lockfile; Supabase/React Query/Zod appear unused in current placeholder surface; Vite plugin is not a Next build requirement | split; retain only approved responsive-web dependencies later |
| Portal image: `apps/portal/Dockerfile` | `35b8da780181359e9ec3f1f71e946d8830e03fb9786100b808975e6d05da5e50` | Node image/Corepack/pnpm | `node:20-alpine` mutable tag; `pnpm i --frozen-lockfile` with optional missing lock copy | Build/runtime | Build is currently non-reproducible and can float image/package resolution; Alpine/native module compatibility must be proven | rewrite later |
| Console: `apps/console/package.json` | `2963b98bd43d33a3b50b8dfae9f5ca6cd96a9ca616357ad02e651bbb7f460718` | pnpm/Node 20 | All external dependencies use caret ranges; no app or root lockfile | Deferred frontend build/runtime | Current console source is a placeholder; Supabase, React Query, React Router, Zustand, and test/browser tooling are apparently unused | defer/exclude from MVP until approved UI scope |
| Console image: `apps/console/Dockerfile` | `5d5dfaea72768211dec6ad204754fe9ea7591d200b5c19d4196b90f28dee7687` | Node/Nginx images | `node:20-alpine` and `nginx:alpine` mutable tags; frozen install needs missing lock | Deferred frontend build/runtime | Same lock failure plus mutable runtime image; current MVP uses one responsive app rather than separate console | defer |
| Shared types: `packages/shared-types/package.json` | `f459f6eb658114ff01cc39d8fa96efc458d032f0e844c18da5bc44318e3cdeea` | pnpm/TypeScript | TypeScript caret range; no lock | Build/dev shared package | Version drift; package has no published runtime dependency declaration | retain if used by approved MVP |
| UI package: `packages/ui/package.json` | `fe070b9ee24eae489be77d312882446a3dc4129a2b2a001659f275e3dc0aff5d` | pnpm/React/TypeScript | React peer and dev dependencies use caret ranges; no lock | Build/dev shared package | Current package is placeholder; React peer range can drift | defer until responsive app component ownership is defined |
| TS config: `packages/ts-config/package.json` | `d066f181c7f673ca0f059366870aa64f456a2ff96f23db24d01e222cd816074f` | pnpm | Metadata only; no dependency lock | Build configuration | No direct package risk, but shared config affects all builds | retain |
| API requirements: `requirements-api.txt` | `2bb72fc7522a2e7f0d02983ac6ada6d0d9b9057300a863c9d294074aeb8b2447` | pip/Python 3.12 image | Five lower-bound requirements; no constraints/lock/hashes | API runtime | Unbounded resolution; `api/auth.py` imports `jwt`, but no PyJWT package is declared; CI installs it ad hoc | rewrite later in reviewed implementation task |
| API image: `Dockerfile.api` | `268d7195c74172ca04019679afea3553fdeea31ff51ae6abf7bab05639aebf15` | Python/pip | `python:3.12-slim` mutable tag; pip resolves broad ranges | API runtime | Native `libpq-dev`/build requirements may vary by image; no hashes or wheel provenance | rewrite later |
| Workers: `workers/pyproject.toml` | `ac46f447a3b75a7c844664e13713cdaa8e5c5e540edf2048d4532f72d8305ba1` | pip/hatchling; Python `>=3.11`, tools target 3.12 | All runtime/dev packages except Ruff use lower-bound ranges; no lock/constraints/hashes | Worker runtime and dev | Runtime range allows drift; FastAPI/SQLAlchemy/Redis/RQ/Supabase/Langfuse/Sentry include deferred platform dependencies; SQLAlchemy, RQ, Sentry, pytest-asyncio, pytest-cov, mypy, and mkinit are apparently unused by current source | split production MVP from optional/deferred and dev dependencies later |
| Workers image: `workers/Dockerfile` | `22e35696e32155c03ff6f2f24a47efb0187152366878c2e4d71445d6f9acec22` | Python/pip | `python:3.12-slim` mutable tag; installs editable `.[dev]` in runtime image | Deferred worker runtime | Dev/test tools ship in runtime image; Tesseract/native dependencies must be pinned/proven; agent/OCR stack is deferred | defer/rewrite later |
| Compose: `docker-compose.yml` | `dbeea3c74a5b7f8e39d73ecd22ae79be277141be24035eedfb2506a245a86564` | Docker Compose | Floating tags: `redis:7-alpine`, `odoo:18.0`, `python:3.12-slim`, `nginx:alpine`; build contexts have unresolved package files | Development/infrastructure reference | Public ports, invalid migration mount, deferred services, and mutable images conflict with approved staging/MVP topology | supersede for future approved staging/production definition |
| Database image: `infra/docker/Dockerfile.db` | `8308cb9f80922eb7b1b55f898166acea0e9a80ab767c474628b9f3055d614408` | Docker/APT/PostgreSQL | `postgis/postgis:16-3.4` tag and unpinned APT package install | Deferred database image | APT index/package resolution floats; pgvector native package availability is unverified | defer/rewrite later |
| CI: `.github/workflows/ci.yml` | `d7ded2f2790d31a183fc1f0c2e4b216ec28066c3593869bc85360fa4533ff75f` | GitHub Actions; Python 3.12 | `actions/*@v4/v5` and Trivy `@master` are mutable tags; API deps installed ad hoc | CI/dev security | CI cannot prove reproducibility, Trivy branch is mutable, and API test environment does not come from a lock | rewrite later |
| Deploy workflow: `.github/workflows/deploy-hostinger.yml` | `7aa966b48502bd63841b3e142c2599ac3d237f49ee53701ade80ac71c34f4d01` | GitHub Actions | `actions/checkout@v4` mutable tag; references missing production Compose file | Deferred deployment | Not an approved deploy path; mutable action plus missing definition blocks trustworthy deployment | defer/rewrite later |

## Lockfile and Runtime Findings

| Check | Static result | Risk / required future action |
|---|---|---|
| Node lockfiles | No `pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`, or Bun lock discovered | Root pnpm lockfile is required before any frozen install, Docker build, CI reproducibility claim, or dependency review |
| Python locks/constraints | No `poetry.lock`, `uv.lock`, `requirements.lock`, or `constraints.txt` discovered | API and workers resolve broad lower bounds differently over time; choose one Python locking mechanism per deployable environment |
| Lockfile-to-manifest match | Not verifiable because no lockfile exists | Do not claim manifest/lock integrity until generated and verified in a separate reviewed task |
| Package manager ownership | pnpm is declared at root, but API/worker pip ownership is split between `requirements-api.txt` and `workers/pyproject.toml` | Preserve one pnpm workspace lock; establish explicit API versus worker Python dependency ownership |
| Runtime declarations | Repository specifies Node 20 images, Python 3.12 images, worker Python `>=3.11`, and root Node/npm/pnpm floors | Pin an exact supported Node/Python version matrix; current floors permit unsupported future releases |
| Installed metadata | Host reports runtime metadata only; it is not build evidence | Repository declarations, not host versions, control future builds; record exact runtime versions only in future CI/staging evidence |
| Mutable images/actions | Docker tags include Alpine/slim/latest-style channels; GitHub Actions use major tags and Trivy `@master` | Pin production image digests and Action commit SHAs after compatibility review |
| Native build dependencies | API/workers install `build-essential`, `libpq-dev`; workers install Tesseract; DB image installs pgvector with APT | Pin image digest/package source and prove builds on approved Ubuntu/Hostinger staging before release |

## Import and Dependency Reconciliation

- `api/auth.py` imports `jwt`; `requirements-api.txt` omits PyJWT while CI installs `pyjwt` ad hoc. This is a source/manifest/CI mismatch and must be corrected in a reviewed implementation task.
- Current portal and console root source exports only an application name. Static search finds the portal webhook route using `@supabase/supabase-js`; current source does not establish use for portal `@supabase/ssr`, React Query, Zod, Vite plugin, JSDOM, or most console application dependencies.
- Worker source uses `httpx`, `pydantic`, `pydantic-settings`, `supabase`, `structlog`, and `typer`. It can emit Langfuse requests through `httpx`, but does not require the Langfuse SDK. Static inspection did not establish current source use for SQLAlchemy, RQ, Sentry SDK, `pytest-asyncio`, `pytest-cov`, mypy, or mkinit.
- Deferred mobile applications, mandatory LLM/RAG, Supabase Cloud, Kafka/Redis Streams, full runtime agents, advanced control-tower UI, broad Odoo customization, and advanced analytics must not justify retained MVP production dependencies.
- Existing `.env*` files were not read. No secret-bearing package configuration value was inspected or recorded.

## Proposed MVP Locking Policy

This is a recommendation only. Every manifest, lockfile, image, workflow, dependency, or runtime-version modification requires a separate reviewed implementation task and owner approval.

1. **One package manager per ecosystem:** pnpm for the JavaScript/TypeScript workspace; a single approved Python resolver/lock workflow for API and workers. Do not introduce a second Node lock format.
2. **Authoritative locks:** maintain one root `pnpm-lock.yaml` for all workspaces. Maintain one exact, hash-capable Python constraints/lock artifact per deployable API/worker environment, with clear ownership and generation command recorded in documentation.
3. **Exact runtime matrix:** select exact Node, pnpm, Python, PostgreSQL, Odoo, and base-image versions. Containers must use immutable digest references for production after staging compatibility proof.
4. **Frozen CI:** CI and image builds use frozen/offline-compatible installs only from reviewed locks. CI must never install runtime packages ad hoc outside the approved lock/constraints artifact.
5. **Action provenance:** pin every GitHub Action, including security scanners, to immutable commit SHA with a human-readable version comment; do not use branches such as `master`.
6. **Dependency separation:** keep production runtime dependencies separate from development/test/lint/typecheck tools. Keep optional/deferred services outside MVP images and manifests until their milestone is authorized.
7. **Ownership and cache rules:** root engineering owns workspace lock changes; API/worker owners own Python locks; each change must update manifests and locks atomically. Cache keys include lockfile checksum, runtime version, OS/image digest, and relevant build configuration; invalidate on any of those changes.
8. **Review cadence:** use scheduled, reviewed update windows. Review changelog, license, security advisory, native build, transitive dependency, and rollback impact before changing a lock. No automatic major-version upgrade.
9. **Provenance and rollback:** retain immutable build artifacts, image digests, source commit, lock checksum, CI run, and SBOM/license review result. Roll back by redeploying the prior approved artifact/digest with its matching lock, never by resolving packages again.
10. **MVP scope:** retain only dependencies needed for the approved responsive web application, deterministic backend, approved private PostgreSQL path, staged Razorpay/manual evidence, and limited Odoo API boundary. Defer AI/RAG, Supabase Cloud, runtime agents/Paperclip activation, extra messaging, mobile, control-tower, and advanced analytics dependencies.

## Completion Assessment

The dependency inventory and proposed locking policy are complete enough to sequence later implementation. They expose reproducibility and security risks but do not require an unresolved dependency-ownership decision: pnpm owns the Node workspace, while API and workers require separately owned, reviewed Python locks. No installation, package resolution, lockfile generation, source change, vulnerability scan, or runtime/deployment action occurred.
