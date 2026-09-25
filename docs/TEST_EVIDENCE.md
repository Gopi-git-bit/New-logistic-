# Zippy Test and Discovery Evidence

## Evidence Policy

- Current verdict: **BLOCKED FOR PRODUCTION — M3 DETERMINISTIC CORE COMPLETE IN DISPOSABLE TEST ENVIRONMENTS**.
- This file distinguishes read-only discovery evidence from executable test evidence.
- Historical repository counts are not current results.
- No application, SQL, integration, build, lint, security, container, or database test was executed during M0 discovery.
- No container or database is marked operational.
- Secret values, credentials, authorization headers, private keys, database URLs, and sensitive SSH endpoint details must never be recorded here.

## Production PRD Precedence

`docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md` was imported after M0 discovery and is the owner-approved production execution source of truth established at commit `cee3307861fc4d19c5a85c7bbce3ca1367c9a6a2`. It was not present during discovery and is not discovery-time evidence. Conflicting legacy documents are historical until reconciled. Their business rules must not be silently rewritten or discarded. Architecture deviations require a proposed `docs/DECISIONS.md` entry and owner approval. No legacy document was edited during this correction task.

## Evidence Record Template

Use this template only for separately authorized future evidence collection:

| Field | Required value |
|---|---|
| Evidence ID | Unique immutable identifier |
| Command | Exact redacted command |
| Timestamp | UTC ISO-8601 |
| Commit | Full Git SHA |
| Environment | Host/environment identity without secrets |
| Preconditions | Git state, dependencies, service state, and authorization |
| Exit code | Integer |
| Result | PASS, FAIL, BLOCKED, or NOT RUN |
| Evidence location | Repository path or approved immutable external location |
| Redactions | Values intentionally omitted |
| Operator/automation | Human or workflow identity |
| Notes | Scope, limitations, and interpretation |

## M0 Read-Only Discovery Evidence

### M0-E001: Git and Connection Baseline

| Field | Value |
|---|---|
| Command | `pwd`; `hostname`; SSH presence check; `git rev-parse --show-toplevel`; `git remote -v`; `git branch --show-current`; `git rev-parse HEAD`; `git status --short` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `a6aee5294145eb9c12ffd93a1b63431ca6631bd4` |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH; endpoint details redacted |
| Exit code | 0 |
| Result | PASS: expected repository, branch, commit, and clean tree verified |
| Evidence location | `docs/reports/M0_DISCOVERY_REPORT.md` |

### M0-E002: Host Capacity and Runtime Versions

| Field | Value |
|---|---|
| Command | `lsb_release -a`; `uname -a`; selected `lscpu`; `free -h`; `df -h`; `docker --version`; `docker compose version` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `a6aee5294145eb9c12ffd93a1b63431ca6631bd4` |
| Environment | `srv1943844` |
| Exit code | 0 |
| Result | PASS: inventory captured; not an application test |
| Evidence location | `docs/reports/M0_DISCOVERY_REPORT.md` |

### M0-E003: Service, Container, Network, and Volume Inventory

| Field | Value |
|---|---|
| Command | Read-only `systemctl`, `docker ps -a`, `docker images`, `docker volume ls`, `docker network ls`, `ss -tulpn`, process, supervisor, and unit-file inspection |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `a6aee5294145eb9c12ffd93a1b63431ca6631bd4` |
| Environment | `srv1943844` |
| Exit code | 0 for reported command groups |
| Result | PASS: inventory captured; production runtime not provisioned or verified |
| Evidence location | `docs/reports/M0_DISCOVERY_REPORT.md` |

### M0-E004: Apache, TLS, Firewall, and Scheduling Inventory

| Field | Value |
|---|---|
| Command | Read-only Apache site/config metadata, `certbot certificates`, `ufw status verbose`, systemd timer, cron metadata, and socket inspection |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `a6aee5294145eb9c12ffd93a1b63431ca6631bd4` |
| Environment | `srv1943844` |
| Exit code | 0 for reported command groups |
| Result | PASS: inventory captured; no configuration changed |
| Evidence location | `docs/reports/M0_DISCOVERY_REPORT.md` |

### M0-E005: Filesystem, Deployment, and Backup Inventory

| Field | Value |
|---|---|
| Command | Read-only directory metadata for `/opt`, selected `/home` application paths, backup paths, duplicate checkout, and required repository files |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `a6aee5294145eb9c12ffd93a1b63431ca6631bd4` |
| Environment | `srv1943844` |
| Exit code | 0 for reported command groups |
| Result | PASS: paths and absence evidence recorded; backup contents not read |
| Evidence location | `docs/reports/M0_DISCOVERY_REPORT.md` |

### M0-E006: Repository and Architecture Inventory

| Field | Value |
|---|---|
| Command | Read-only listing/search/read of manifests, Compose, workflows, migrations, API routes, workers, frontend source, integrations, PRDs, decisions, tests, TODOs, placeholders, and `.gitignore` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `a6aee5294145eb9c12ffd93a1b63431ca6631bd4` |
| Environment | `/opt/new-logistic` |
| Exit code | 0 for successful inspection commands; `rg` attempt exited 127 because it is not installed |
| Result | PASS: repository inventory captured; no source or test execution |
| Evidence location | `docs/reports/M0_DISCOVERY_REPORT.md`, `docs/reports/RISK_REGISTER.md` |

### M0-E007: Secret-Safe Environment Metadata

| Field | Value |
|---|---|
| Command | Extract `.env` variable names only; list file metadata |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `a6aee5294145eb9c12ffd93a1b63431ca6631bd4` |
| Environment | `/opt/new-logistic` |
| Exit code | 0 |
| Result | PASS: names/presence and mode recorded; values not displayed |
| Evidence location | `docs/reports/M0_DISCOVERY_REPORT.md` |

### M0-E008: Database Presence Inspection

| Field | Value |
|---|---|
| Command | Read-only package/data-directory inspection; unauthenticated local `mysql -e "SHOW DATABASES;"` attempt |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `a6aee5294145eb9c12ffd93a1b63431ca6631bd4` |
| Environment | `srv1943844` |
| Exit code | 1 for MySQL query (access denied without credentials); 0 for filesystem/package inspection |
| Result | BLOCKED for MySQL logical database listing; confirmed no host PostgreSQL runtime evidence |
| Evidence location | `docs/reports/M0_DISCOVERY_REPORT.md` |
| Notes | No credential was requested, read, or exposed. |

## Historical Claims: Not Current Evidence

Every result below is classified **HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED**.

| Claimed suite/result | Repository source | Current classification | Fresh execution during M0 |
|---|---|---|---|
| M1 SQL verification: 11 passing | `docs/memory.md`, `MILESTONES.md` | HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED | NOT RUN |
| M2 SQL verification: 21 passing | `docs/memory.md`, `MILESTONES.md` | HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED | NOT RUN |
| M3 worker pytest: 11 passing | `docs/memory.md`, `MILESTONES.md` | HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED | NOT RUN |
| M3 SQL verification: 14 passing | `docs/memory.md`, `MILESTONES.md` | HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED | NOT RUN |
| M4 worker pytest: 8 passing | `docs/memory.md`, `MILESTONES.md` | HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED | NOT RUN |
| M4 Node webhook tests: 8 passing | `docs/memory.md`, `MILESTONES.md` | HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED | NOT RUN |
| M4 SQL verification: 12 passing | `docs/memory.md`, `MILESTONES.md` | HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED | NOT RUN |
| M5 worker pytest: 24 passing | `docs/memory.md`, `MILESTONES.md` | HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED | NOT RUN |
| M5 SQL verification: 11 passing | `docs/memory.md`, `MILESTONES.md` | HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED | NOT RUN |
| M6 worker pytest: 17 passing | `docs/memory.md`, `MILESTONES.md` | HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED | NOT RUN |
| M6 SQL verification: 12 passing | `docs/memory.md`, `MILESTONES.md` | HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED | NOT RUN |
| Aggregate 119 passing | `docs/memory.md` | HISTORICAL CLAIM — NOT CURRENTLY REPRODUCED | NOT RUN |
| `zippy-db` running with 25 tables | `docs/HEARTBEAT.md`, `docs/memory.md` | STALE HISTORICAL CLAIM — CONTRADICTED BY CURRENT RUNTIME INVENTORY | NOT RUN |

The historical table count of 25 is not an acceptance target. A future approved staging initialization must establish and explain a fresh schema inventory.

## Current Operational Evidence

| Capability | Result | Reason |
|---|---|---|
| Docker Compose application stack | NOT OPERATIONAL / NOT VERIFIED | No running or stopped containers |
| Zippy Operational DB | NOT OPERATIONAL / NOT VERIFIED | No deployed PostgreSQL database |
| Odoo DB/application | NOT OPERATIONAL / NOT VERIFIED | No deployed Odoo container/database |
| Paperclip DB/application | NOT OPERATIONAL / NOT VERIFIED | Source checkout only |
| Langfuse | NOT OPERATIONAL / NOT VERIFIED | No runtime found |
| Honcho | NOT OPERATIONAL / NOT VERIFIED | Repository placeholder only |
| FastAPI | NOT OPERATIONAL / NOT VERIFIED | No process/container found |
| Portal | NOT OPERATIONAL / NOT VERIFIED | No process/container found |
| Console | NOT OPERATIONAL / NOT VERIFIED | No process/container found |
| Workers | NOT OPERATIONAL / NOT VERIFIED | No process/container found |
| Backups/restoration | NOT VERIFIED | No application backup or restore evidence found |

## Future Evidence Placeholders

These entries are deliberately `NOT RUN` and require separate authorization.

### FUTURE-E001: Production Compose Validation

| Field | Value |
|---|---|
| Command | `docker compose -f docker-compose.production.yml config` |
| Timestamp | NOT RUN |
| Commit | NOT RUN |
| Environment | Isolated validation environment, TBD |
| Exit code | NOT RUN |
| Result | NOT RUN |
| Evidence location | TBD |

### FUTURE-E002: Reproducible Dependency Installation

| Field | Value |
|---|---|
| Command | Approved frozen-lockfile command, TBD |
| Timestamp | NOT RUN |
| Commit | NOT RUN |
| Environment | CI or isolated builder, TBD |
| Exit code | NOT RUN |
| Result | NOT RUN |
| Evidence location | TBD |

### FUTURE-E003: Staging Database Initialization

| Field | Value |
|---|---|
| Command | Approved canonical migration command, TBD |
| Timestamp | NOT RUN |
| Commit | NOT RUN |
| Environment | Isolated staging database, TBD |
| Exit code | NOT RUN |
| Result | NOT RUN |
| Evidence location | TBD |

### FUTURE-E004: SQL and RLS Verification

| Field | Value |
|---|---|
| Command | Approved verification manifest, TBD |
| Timestamp | NOT RUN |
| Commit | NOT RUN |
| Environment | Isolated staging database, TBD |
| Exit code | NOT RUN |
| Result | NOT RUN |
| Evidence location | TBD |

### FUTURE-E005: Application Unit and Contract Tests

| Field | Value |
|---|---|
| Command | Approved API, worker, portal, console, and OpenAPI commands, TBD |
| Timestamp | NOT RUN |
| Commit | NOT RUN |
| Environment | CI/staging, TBD |
| Exit code | NOT RUN |
| Result | NOT RUN |
| Evidence location | TBD |

### FUTURE-E006: Security Evidence

| Field | Value |
|---|---|
| Command | Approved secret, dependency, image, authorization, RLS, and public-route checks, TBD |
| Timestamp | NOT RUN |
| Commit | NOT RUN |
| Environment | CI/staging, TBD |
| Exit code | NOT RUN |
| Result | NOT RUN |
| Evidence location | TBD |

### FUTURE-E007: Backup and Restore Test

| Field | Value |
|---|---|
| Command | Approved backup and isolated restore procedure, TBD |
| Timestamp | NOT RUN |
| Commit | NOT RUN |
| Environment | Staging recovery environment, TBD |
| Exit code | NOT RUN |
| Result | NOT RUN |
| Evidence location | TBD |

## M0 Documentation Verification

The documentation task is validated only with:

- `git diff --check`
- `git status --short`
- `git diff --stat`

These commands validate the documentation diff and working-tree inventory. They are not application or production-readiness tests.

## M1 Production PRD Adoption Evidence

### M1-E001: Remote Repository Baseline

| Field | Value |
|---|---|
| Command | `pwd`; `hostname`; `git branch --show-current`; `git rev-parse HEAD`; `git status --short` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `cee3307861fc4d19c5a85c7bbce3ca1367c9a6a2` |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Exit code | 0 |
| Result | PASS: remote repository, `master`, expected commit, and clean tree verified |
| Evidence location | This record and `docs/EXECUTION_TRACKER.md` |

### M1-E002: Required Document Review

| Field | Value |
|---|---|
| Command | Complete reads of repository instructions, production PRD, tracker, evidence ledger, decisions, M0 discovery report, risk register, and M0-to-M1 plan |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `cee3307861fc4d19c5a85c7bbce3ca1367c9a6a2` |
| Environment | `/opt/new-logistic` |
| Exit code | 0 |
| Result | PASS: required sources read completely; `M1-PRD` confirmed as the sole active task |
| Evidence location | `docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md`, `docs/EXECUTION_TRACKER.md` |

### M1-E003: PRD Adoption Criteria Review

| Field | Value |
|---|---|
| Command | PRD grep for adoption status, pending approval, placeholder, precedence, owner, and version; `git show -s --format='%H%n%s' HEAD` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `cee3307861fc4d19c5a85c7bbce3ca1367c9a6a2` |
| Environment | `/opt/new-logistic` |
| Exit code | 0 |
| Result | PASS: version `1.0`, owner `Gopinathan`, precedence, owner approval, and baseline commit established; no unresolved PRD placeholder found |
| Evidence location | `docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md` |
| Notes | The only `placeholder` match described safe placeholders in `.env.example`; it is not unresolved PRD content. |

### M1-E004: PRD Adoption Final Validation

| Field | Value |
|---|---|
| Command | `git diff --check`; `git status --short`; PRD grep for version, owner, adoption status, and precedence; tracker-table `awk` count for `IN_PROGRESS` rows |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | Baseline `cee3307861fc4d19c5a85c7bbce3ca1367c9a6a2`; documentation changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Exit code | 0 for every command |
| Result | PASS: no whitespace errors; only the three authorized documents changed; PRD acceptance wording present; exactly one active tracker row (`M1-RECONCILE`) |
| Evidence location | `docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md`, `docs/EXECUTION_TRACKER.md`, this record |
| Notes | No application, infrastructure, database, service, configuration, or legacy-document change was made. |

## M1 PRD Reconciliation Evidence

### M1-E005: Required Legacy Corpus Review

| Field | Value |
|---|---|
| Command | Complete editor reads of the production PRD, repository instructions, `soul.md`, `memory.md`, `HEARTBEAT.md`, `MILESTONES.md`, `DECISIONS.md`, authority/API contracts, four component PRDs, and every file under `docs/PRD/` |
| Timestamp | 2026-09-08 UTC; exact read timestamps not captured |
| Commit | `501514c1c17e55d2b98557f1e0d40624212ea3bf` |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Preconditions | Clean `master`; local and `origin/master` at the recorded commit; `M1-RECONCILE` sole active task |
| Exit code | 0 for all file reads |
| Result | PASS: all 21 required files, totaling 2,617 lines, were read; no legacy file was edited |
| Evidence location | `docs/reports/M1_PRD_CONFLICT_MATRIX.md` |
| Redactions | None required; no secret-bearing files or values were read |
| Operator/automation | GitHub Copilot |
| Notes | Source comparison only; historical claims were not treated as current test evidence. |

### M1-E006: Conflict Matrix Structural Validation

| Field | Value |
|---|---|
| Command | `awk` validation of matrix IDs, allowed classification vocabulary, row count, and Markdown column count; trailing-whitespace `grep` across all three authorized documents |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | Baseline `501514c1c17e55d2b98557f1e0d40624212ea3bf`; documentation changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Preconditions | Matrix drafted from the complete required corpus |
| Exit code | 0 |
| Result | PASS: 28 matrix rows, zero invalid classifications, zero malformed rows, and no whitespace errors |
| Evidence location | `docs/reports/M1_PRD_CONFLICT_MATRIX.md` |
| Redactions | None |
| Operator/automation | GitHub Copilot |
| Notes | An initial validator expected the wrong awk field count because Markdown tables have leading/trailing delimiters; the corrected validator passed without changing matrix content. The explicit grep covered the untracked matrix, which ordinary `git diff --check` does not. |

### M1-E007: Tracker Handoff Validation

| Field | Value |
|---|---|
| Command | Tracker-table `awk` count and active-ID validation; `git diff --check -- docs/EXECUTION_TRACKER.md` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | Baseline `501514c1c17e55d2b98557f1e0d40624212ea3bf`; documentation changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Preconditions | Matrix structural validation passed |
| Exit code | 0 |
| Result | PASS: exactly one active tracker row, `M1-DECISIONS`; `M1-RECONCILE` marked `COMPLETE` |
| Evidence location | `docs/EXECUTION_TRACKER.md`, this record |
| Redactions | None |
| Operator/automation | GitHub Copilot |
| Notes | The active-row handoff does not begin `M1-DECISIONS` and authorizes no implementation. |

### M1-E008: Reconciliation Correction Pass

| Field | Value |
|---|---|
| Command | `git branch --show-current`; `git rev-parse HEAD`; `git status --short --untracked-files=all`; `git diff --check`; `sed -n '1,20l' docs/reports/M1_PRD_CONFLICT_MATRIX.md`; classification-count `awk` validation; fixed-policy `grep` checks; `git diff --check -- docs/reports/M1_PRD_CONFLICT_MATRIX.md` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | Baseline `501514c1c17e55d2b98557f1e0d40624212ea3bf`; documentation changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Preconditions | `master` at expected baseline; only the three authorized M1 documentation paths changed |
| Exit code | 0 for the final preflight and corrected validation commands |
| Result | PASS: matrix begins with normal Markdown `# M1 Production PRD Conflict Matrix` and has no escaped structural syntax; R04 fixes execution order while retaining only protocol details as unresolved; R05 records phase-one single operational tenant direction; R07 is `SUPERSEDED` and prohibits automatic refunds; 28 rows total with counts 6 compatible, 3 stale, 4 superseded, 7 requires decision, 5 missing implementation, and 3 missing evidence |
| Evidence location | `docs/reports/M1_PRD_CONFLICT_MATRIX.md`, `docs/EXECUTION_TRACKER.md`, this record |
| Redactions | None |
| Operator/automation | GitHub Copilot |
| Notes | The first classification awk attempt used reserved variable name `index` and failed before evaluating content; rerunning with `item` passed. `M1-RECONCILE` remains complete and `M1-DECISIONS` remains the sole active tracker task; no decision drafting or implementation began. |

## M1 Decisions Draft Evidence

### M1-E009: Controlled M1-DECISIONS Draft Pass

| Field | Value |
|---|---|
| Command | `cd /opt/new-logistic`; `pwd`; `git branch --show-current`; `git rev-parse HEAD`; `git status --short --untracked-files=all`; `git ls-remote origin refs/heads/master`; tracker-table `awk` active-task check; complete editor reads of repository instructions, production PRD, conflict matrix, decisions, tracker, evidence, operational completion schema, initial schema, functions/triggers, Paperclip governance schema, and Odoo ownership blueprint; draft-record `awk` validation; `git diff --check -- docs/DECISIONS.md` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `1394d10875e530c5e7c6364e4513604b90c0571b`; documentation changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Preconditions | Local and `origin/master` matched the recorded commit; working tree was clean; `M1-DECISIONS` was the sole active task |
| Exit code | 0 |
| Result | PASS: 13 D-11 through D-23 records appended as `PROPOSED — OWNER APPROVAL REQUIRED`; zero draft records marked approved; no implementation, schema, infrastructure, tracker, or legacy-document changes made |
| Evidence location | `docs/DECISIONS.md`, this record |
| Redactions | No secret values, credentials, or server usernames recorded |
| Operator/automation | GitHub Copilot |
| Notes | The records capture current owner MVP direction and distinguish it from seven unresolved technical recommendations requiring owner approval. `M1-DECISIONS` remains active and incomplete. |

### M1-E010: M1-DECISIONS Owner Approval and Handoff

| Field | Value |
|---|---|
| Command | `cd /opt/new-logistic`; `pwd`; `git branch --show-current`; `git rev-parse HEAD`; `git ls-remote origin refs/heads/master`; `git status --short --untracked-files=all`; `git diff --check`; tracker-table `awk` active-task check; M1 decision-record `awk` approval check; technical-direction `awk` check; required admin-control `grep` checks; `git diff --check -- docs/DECISIONS.md` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `1394d10875e530c5e7c6364e4513604b90c0571b`; documentation changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Preconditions | Local and `origin/master` matched the recorded commit; only `docs/DECISIONS.md` and `docs/TEST_EVIDENCE.md` contained the prior M1 draft changes; `M1-DECISIONS` was sole active task |
| Exit code | 0 |
| Result | PASS: owner approval recorded for D-11 through D-24 and all seven technical directions; 14 records have dated owner approval, zero draft statuses remain, admin account-control requirements are present, and no implementation occurred |
| Evidence location | `docs/DECISIONS.md`, `docs/EXECUTION_TRACKER.md`, this record |
| Redactions | No secret values, credentials, or server usernames recorded |
| Operator/automation | GitHub Copilot |
| Notes | `M1-DECISIONS` is complete. The next eligible ordered task is `M1-MIGRATIONS`, which is now sole active but not started; it remains documentation-only and may not execute or move migrations. |

## M1 Migration Inventory Evidence

### M1-E011: Static Migration Inventory and Manifest Review

| Field | Value |
|---|---|
| Command | `cd /opt/new-logistic`; `pwd`; `git branch --show-current`; `git rev-parse HEAD`; `git ls-remote origin refs/heads/master`; `git status --short --untracked-files=all`; tracker-table `awk` active-task check; static `find` of SQL/ownership artifacts; `sha256sum`; static SQL structural-marker inspection; complete source reads of numbered migrations, stubs, seeds, verification fixtures, operational completion schema, Paperclip schema, and Odoo ownership blueprint; `cmp -s` duplicate verification checks; inventory path/checksum/field `awk` checks; `git diff --check -- docs/reports/M1_MIGRATION_INVENTORY.md` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `5c7ce5281f4c85cb238fe6cc803d18d648889229`; documentation changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Preconditions | Local and `origin/master` matched the recorded commit; working tree was clean; `M1-MIGRATIONS` was sole active task |
| Exit code | 0 for final preflight, duplicate comparison, and corrected inventory validation commands |
| Result | PASS: 35 database-related repository artifacts inventoried with SHA-256 checksum, owner, static safety profile, conflict/assumption note, and MVP disposition; all six root verification scripts are byte-identical to their `infra/supabase` counterparts; no SQL, database, container, credential, or migration command was executed |
| Evidence location | `docs/reports/M1_MIGRATION_INVENTORY.md`, `docs/EXECUTION_TRACKER.md`, this record |
| Redactions | No secret values, database credentials, or server usernames recorded |
| Operator/automation | GitHub Copilot |
| Notes | Existing numbered and root-level artifacts are not an executable production chain: root operational completion uses incompatible table/key names and duplicate verification paths exist. The report proposes a non-executable logical MVP manifest only. `M1-MIGRATIONS` is complete; `M1-STAGING-ROUTE` is sole active and has not begun. |

### M1-E012: Expanded Migration Inventory Completeness Correction

| Field | Value |
|---|---|
| Command | Preflight `pwd`, Git branch/SHA/status/remote/diff checks; temporary tracker active-row `awk` check; attempted `rg --files` and targeted `rg` content search; static `find` and recursive `grep` fallback for migration, schema, initdb, seed, fixture, backup, restore, rollback, Odoo, Paperclip, and database-write terms; `file`/`ls` inspection of `supabase/migrations`; Odoo addon listing; `sha256sum`; targeted runtime writer reads; inventory coverage/checksum/reference-table `awk` validation; `git diff --check` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `5c7ce5281f4c85cb238fe6cc803d18d648889229`; documentation changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Preconditions | Owner-authorized temporary reopen of `M1-MIGRATIONS`; local and `origin/master` matched the recorded commit; only the three authorized documentation paths changed |
| Exit code | 0 for final fallback discovery and inventory validation commands; `rg` unavailable and not installed |
| Result | PASS: 152 repository files searched statically; revised inventory contains 37 executable/state-mutating artifacts and 12 migration-affecting references; no Alembic/Prisma/Drizzle/ORM auto-create/backup-restore/Odoo addon migration found; `supabase/migrations` is a regular text file despite Compose mounting it as initdb source; root `supabase/verify_m*.sql` files exactly duplicate `infra/supabase/verify_m*.sql` files |
| Evidence location | `docs/reports/M1_MIGRATION_INVENTORY.md`, `docs/EXECUTION_TRACKER.md`, this record |
| Redactions | No credentials or secret values read; environment variable names only where needed for configuration relevance |
| Operator/automation | GitHub Copilot |
| Notes | The correction resolves the inventory-completeness gap while preserving the conclusion that no existing SQL set is an approved or executable production migration chain. `M1-MIGRATIONS` is complete; `M1-STAGING-ROUTE` is sole active and has not begun. |

## M1 Staging Route Evidence

### M1-E013: Read-Only Staging Route Discovery and Plan

| Field | Value |
|---|---|
| Command | `cd /opt/new-logistic`; Git branch/SHA/status/remote checks; tracker-table `awk` active-task check; `hostname`; `uname -a`; `systemctl is-active apache2`; `apache2ctl -v`, `-S`, and `-M`; `ss -lntp`; `docker ps`; Apache enabled-site listing and sanitized vhost/config reads; `ps` process inspection; `certbot certificates`; staging-host config search; status-only `curl` probes for public root/API/health and local API/frontend ports; `supervisorctl status`; repository Compose/proxy/deploy configuration reads; plan structure/safety checks; `git diff --check` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `1af111cf78994f8c934d4d3229a54c40ece8a3db`; documentation changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Preconditions | Local and `origin/master` matched the recorded commit; working tree was clean; `M1-STAGING-ROUTE` was sole active task |
| Exit code | 0 for the completed read-only discovery and final plan validation commands |
| Result | PASS: Apache 2.4.58 owns public `80`/`443` with valid production TLS; current Zippy vhost is Basic-Auth PHP/FastCGI with no discovered `/api` proxy; no Zippy containers or API/frontend listeners exist; no staging host/site exists; plan separates verified facts from approval-gated staging/production routing and requires isolated staging data with sandbox/manual financial behavior |
| Evidence location | `docs/reports/M1_STAGING_ROUTE_PLAN.md`, `docs/EXECUTION_TRACKER.md`, this record |
| Redactions | ServerAvatar user paths, credential-bearing configuration values, and private identifiers omitted or redacted; endpoint probes recorded status only |
| Operator/automation | GitHub Copilot |
| Notes | No Apache, ServerAvatar, DNS, TLS, firewall, port, service, container, environment, database, or deployment change occurred. `M1-STAGING-ROUTE` is complete; `M1-LOCK-STRATEGY` is sole active and has not begun. |

## M1 Dependency Lock Strategy Evidence

### M1-E014: Static Dependency and Reproducibility Assessment

| Field | Value |
|---|---|
| Command | `cd /opt/new-logistic`; Git branch/SHA/status/remote checks; tracker-table `awk` active-task check; static `find` of manifests, lockfiles, Dockerfiles, Compose, workspace, and workflow files; `sha256sum`; static grep of runtime/image/action declarations; installed runtime version metadata commands only; complete reads of Node/Python manifests, Dockerfiles, Compose, and workflows; static source-import/declaration comparisons; missing-lock checks; report checksum/policy/redaction `awk` and grep validation; `git diff --check` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `0c19f4928cdd3296fa45d68310dd7d683be017ca`; documentation changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Preconditions | Local and `origin/master` matched the recorded commit; working tree was clean; `M1-LOCK-STRATEGY` was sole active task |
| Exit code | 0 for final static inventory and fail-fast report validation; an earlier TypeScript-import extractor had shell quoting error and was not used as evidence |
| Result | PASS: 19 dependency/runtime declaration artifacts inventoried with checksums and disposition; no Node, Python, or constraints lockfile exists; API imports `jwt` but API requirements omit PyJWT while CI installs it ad hoc; mutable Docker image tags and GitHub Action tags found; no dependency install, lock generation, update, removal, or online scan occurred |
| Evidence location | `docs/reports/M1_DEPENDENCY_LOCK_STRATEGY.md`, `docs/EXECUTION_TRACKER.md`, this record |
| Redactions | No `.env` values or credentials read; runtime metadata only; no server username recorded |
| Operator/automation | GitHub Copilot |
| Notes | `M1-LOCK-STRATEGY` is complete. `M1-DB-REQUIREMENTS` is the next eligible ordered task because M1 migration inventory and staging-route design are complete; it is sole active but has not begun. |

## M1 Database Requirements Evidence

### M1-E015: Static MVP Database Requirements Contract

| Field | Value |
|---|---|
| Command | `cd /opt/new-logistic`; Git branch/SHA/status/remote checks; tracker-table `awk` active-task check; complete reads of controlling documents and M1 reports; static reads of initial operational schema, operational-completion draft, legacy triggers, Paperclip governance schema, and Odoo ownership blueprint; 30-domain `awk` count; required ownership/security/realtime grep checks; sensitive-material and whitespace scan; `git diff --check` |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `8334f0a0550f60e53cdf9d64a8ff7a10dd795ced`; documentation changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Preconditions | Local and `origin/master` matched the recorded commit; working tree was clean; `M1-DB-REQUIREMENTS` was sole active task |
| Exit code | 0 |
| Result | PASS: requirements contract covers all 30 required logical domains; ownership boundaries, server-side RBAC, isolated staging, manual refunds, deterministic state/pricing, authorized SSE projections, Odoo API/ORM boundary, and deferred scope are explicit; no unresolved business-model ambiguity remained |
| Evidence location | `docs/reports/M1_MVP_DATABASE_REQUIREMENTS.md`, `docs/EXECUTION_TRACKER.md`, this record |
| Redactions | No database credentials, secret values, or ServerAvatar usernames read or recorded |
| Operator/automation | GitHub Copilot |
| Notes | No SQL, schema, migration, ORM model, configuration, database, service, or runtime action occurred. `M1-DB-REQUIREMENTS` is complete; `M1-BACKUPS` is sole active and has not begun. |

## M1 Backup and Restoration Evidence

### M1-E016: Read-Only Backup Capability and Restoration Assessment

| Field | Value |
|---|---|
| Command | `cd /opt/new-logistic`; repository branch/SHA/remote/status preflight; tracker active-task `awk`; complete reads of `.github/copilot-instructions.md`, production PRD, decisions, tracker, evidence ledger, migration inventory, staging route, and database requirements; status-only `systemctl is-active/is-enabled` for PostgreSQL, Odoo, Paperclip, Docker, Apache, and ServerAvatar; sanitized `docker ps`, `docker volume ls`, `df -hP`, `findmnt`; `command -v` checks for PostgreSQL dump/restore, encryption, archive, checksum, and backup utilities; `systemctl list-timers --all`; cron metadata listing; metadata-only backup-directory and ServerAvatar-path listing; repository backup/restore reference search; Compose volume/bind declaration inspection; non-secret service/storage metadata search |
| Timestamp | 2026-09-08 UTC; exact command timestamp not captured |
| Commit | `6980e4c0652cb2539ef7292bebaba2b90c58d7b6`; documentation changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`, Remote SSH |
| Preconditions | Local and `origin/master` matched the expected baseline; working tree was clean; `M1-BACKUPS` was the sole active task; no database or backup contents were accessed |
| Exit code | 0 for final preflight and bounded discovery command groups |
| Result | PASS: read-only assessment completed. No host PostgreSQL service, running PostgreSQL/Odoo/Paperclip container, Docker volume, PostgreSQL dump/restore utility, application backup schedule, application backup directory, off-server backup tool/configuration, or successful restore evidence was verified. Docker and Apache are present; ServerAvatar is active; `/var/backups` contains OS package metadata only. Root capacity was approximately 181 GB available at discovery time. |
| Evidence location | `docs/reports/M1_BACKUP_RESTORE_PLAN.md`, this record |
| Redactions | No database contents, backup contents, database names, usernames, connection strings, credentials, secret values, private keys, document contents, or customer data recorded |
| Operator/automation | GitHub Copilot |
| Notes | Repository Compose declares future PostgreSQL, Redis, and Odoo data volumes and Odoo addon/config binds, but no corresponding Docker volumes were present. Paperclip is a source checkout only. No backup, archive, upload, restore, delete, schedule, service, configuration, database, or runtime action occurred. `M1-BACKUPS` remains sole active and is not complete. |

### M1-E017: M1-BACKUPS Owner Approval and Handoff

| Field | Value |
|---|---|
| Command | Git branch, local/remote SHA, working-tree, and whitespace preflight; tracker active-row check; Minimal MVP approval and stronger-option deferral table checks; static custodian and boundary wording review |
| Timestamp | 2026-09-09 UTC; exact command timestamp not captured |
| Commit | `6980e4c0652cb2539ef7292bebaba2b90c58d7b6`; documentation changes uncommitted |
| Environment | Repository documentation workspace; no application, database, service, or backup runtime accessed |
| Preconditions | Local and `origin/master` matched the expected baseline; only the approved backup-plan and evidence-ledger documentation changes existed; `M1-BACKUPS` was the sole active task |
| Exit code | 0 for preflight and corrected Minimal MVP policy validation |
| Result | PASS: all 10 Minimal MVP values are marked `OWNER APPROVED — 2026-09-09 — Gopinathan`; all stronger post-volume values remain `PROPOSED — OWNER APPROVAL REQUIRED`; Gopinathan is recorded as the initial backup and encryption-key custodian; `M1-BACKUPS` is complete and `M1-EVIDENCE` is the sole active task, not begun |
| Evidence location | `docs/reports/M1_BACKUP_RESTORE_PLAN.md`, `docs/EXECUTION_TRACKER.md`, this record |
| Redactions | No credentials, key material, usernames, connection strings, or private filesystem paths recorded |
| Operator/automation | GitHub Copilot |
| Notes | No backup, restore, upload, deletion, installation, service, database, configuration, or runtime operation occurred. This evidence records policy approval and documentation validation only; it does not prove a backup or restore exists or has passed. |

## M1 Decision Correction Evidence

### M1-E018: Owner-Approved Bounded n8n Decision

| Field | Value |
|---|---|
| Command | `pwd`; Git branch/local SHA/remote SHA/status checks; tracker active-row `awk` check; D-14 and latest decision-heading inspection; complete controlling-document review from the interrupted M1-EVIDENCE task; D-25 boundary and changed-scope validation; `git diff --check` |
| Timestamp | 2026-09-09 UTC; exact command timestamp not captured |
| Commit | Baseline `5676fdce02d267b20ded86a7fc97a8c7c45be17c`; documentation changes uncommitted |
| Environment | Repository documentation workspace only |
| Preconditions | Local and `origin/master` matched the expected baseline; working tree was clean; `M1-EVIDENCE` was the sole active task; D-14 retained its approved WhatsApp isolation rule |
| Exit code | 0 for preflight and final validation commands |
| Result | PASS: owner-approved D-25 records a bounded future n8n Cloud integration-adapter role while preserving FastAPI, Zippy PostgreSQL, Odoo, Paperclip, and file/object-storage authority; Zippy PostgreSQL retains durable outbox/inbox/retry/dead-letter ownership; D-14 remains controlling for isolated WhatsApp use |
| Evidence location | `docs/DECISIONS.md`, this record |
| Redactions | No secrets, credentials, usernames, connection strings, private filesystem paths, or personal data recorded |
| Operator/automation | GitHub Copilot |
| Notes | M1-EVIDENCE previously stopped safely because D-14 did not authorize broader n8n integration. D-25 resolves that documentation conflict only for later narrowly controlled non-WhatsApp integration work. No n8n deployment/configuration, runtime, network, service, database, Odoo, Paperclip, backup, or integration action occurred. `M1-EVIDENCE` remains the sole active tracker task and was not resumed. |

## M1 Evidence Review Evidence

### M1-E019: Complete M1 Evidence Classification and Owner-Gate Handoff

| Field | Value |
|---|---|
| Command | `pwd`; Git branch/local SHA/remote SHA/status preflight; tracker active-row `awk`; complete editor reads of repository instructions, production PRD, tracker, evidence ledger, decisions, and all six M1 reports; report-reference extraction; 2,303-line corpus count; evidence-index row/type/result `awk` checks; required `NOT VERIFIED` finding checks; D-14/D-25 checks; authorized-path, tracker, redaction, whitespace, status, and diff-stat validation |
| Timestamp | 2026-09-09 UTC; exact command timestamp not captured |
| Commit | Baseline `dfdcaa81690ef235e2047c8e84d87f2be9603b83`; documentation changes uncommitted |
| Environment | Repository documentation workspace only; no runtime target accessed |
| Preconditions | Local and `origin/master` matched the expected baseline; working tree was clean; `M1-EVIDENCE` was the sole active task; D-14 and D-25 were owner approved and non-conflicting |
| Exit code | 0 for preflight, report-structure validation, and final validation commands |
| Result | PASS: all 10 M1 tracker tasks have evidence-review rows; results are 9 PASS, 0 FAIL, 0 NOT VERIFIED, and 1 NOT APPLICABLE for the unstarted owner gate; nine implementation-stage limitations remain explicitly NOT VERIFIED; the package is ready to present for owner review without asserting implementation or production readiness |
| Evidence location | `docs/reports/M1_EVIDENCE_REVIEW.md`, `docs/EXECUTION_TRACKER.md`, this record |
| Redactions | No sensitive values, credentials, usernames, connection strings, private keys, personal data, or private filesystem paths recorded |
| Operator/automation | GitHub Copilot |
| Notes | D-25 resolved the earlier review blocker while D-14 continues to isolate WhatsApp. No test suite, build, SQL, migration, database, runtime, network, service, backup, restore, deployment, configuration, integration, or infrastructure action occurred. `M1-EVIDENCE` is complete; `M1-OWNER-GATE` is the sole active task and has not begun or been approved. |

## M1 Owner Gate Evidence

### M1-E020: Owner Approval and Controlled M2 Handoff

| Field | Value |
|---|---|
| Command | `pwd`; Git branch/local SHA/remote SHA/status preflight; tracker status and active-row `awk` checks; evidence-review task/result and nine-gap checks; D-11--D-25 approval checks; readiness-disclaimer checks; exact approval-count, exclusion-count, obligation-count, authorized-path, tracker-transition, sensitive-pattern, whitespace, status, and diff-stat validation |
| Timestamp | 2026-09-09 UTC; exact command timestamp not captured |
| Commit | Approved baseline `12fc30c096279be83d54e72101ea80fbd4c50fd4`; documentation changes uncommitted |
| Environment | Repository documentation workspace only; no database or runtime target accessed |
| Preconditions | Local and `origin/master` matched the expected baseline; working tree was clean; `M1-EVIDENCE` was complete; `M1-OWNER-GATE` was the sole active task; the evidence review retained nine implementation-stage gaps |
| Exit code | 0 for preflight, gate-record validation, and final validation commands |
| Result | PASS: Gopinathan approved the M1 owner gate on 2026-09-09 at the recorded baseline; the approval is recorded once; all exclusions and nine NOT VERIFIED obligations remain explicit; `M1-OWNER-GATE` is complete and `M2-DATABASES` is the sole active task, not begun |
| Evidence location | `docs/reports/M1_OWNER_GATE_APPROVAL.md`, `docs/EXECUTION_TRACKER.md`, this record |
| Redactions | No sensitive values, credentials, usernames, connection strings, private keys, personal data, or private filesystem paths recorded |
| Operator/automation | GitHub Copilot |
| Notes | The gate approves controlled backend database implementation under the M1 controls; it is not deployment or production-readiness evidence. No code, SQL, migration, dependency, configuration, database, service, network, deployment, integration, infrastructure, or runtime action occurred. M2 requires a separate preflight before work begins. |

## M2 Database Implementation Evidence

### M2-E001: Exact Preflight, Authorization, and Isolation Boundary

| Field | Value |
|---|---|
| Command | `pwd`; Git branch/local SHA/remote SHA/status checks; tracker active-row check; production database environment-name presence check without reading values; Docker/container/port/service inventory; complete controlling-document and M1 database-report review; canonical-path absence check |
| Timestamp | 2026-09-09 UTC; exact preflight timestamp not captured |
| Commit | Approved M1 baseline `e2b0b5ecf0d0ee35ce3b82d896b265aca787697c`; M2 changes uncommitted |
| Environment | `srv1943844`, `/opt/new-logistic`; repository workspace plus a uniquely named disposable Docker environment |
| Preconditions | `M2-DATABASES` was the sole active task; controlled staging/development database implementation was owner-authorized; production database mutation, deployment and integration were excluded |
| Exit code | 0 for final preflight command groups |
| Result | PASS: expected baseline and scope verified; no existing PostgreSQL service/container/listener or production database target was used; no production database credential was requested or read |
| Evidence location | `docs/reports/M2_DATABASE_IMPLEMENTATION_REPORT.md`, this record |
| Redactions | Environment values and generated disposable password omitted; no secret was displayed or persisted |
| Operator/automation | GitHub Copilot |
| Notes | The test container used Docker network mode `none`, no published port, a read-only repository mount, a unique database/container/volume identity, and synthetic fixtures only. |

### M2-E002: Canonical Fresh Apply, Database Behavior, and Concurrency

| Field | Value |
|---|---|
| Command | `docker exec -e PGUSER=zippy_m2_runner -e PGDATABASE=zippy_m2_disposable_validation -e ZIPPY_ALLOW_DISPOSABLE_DB=YES zippy-m2-disposable-20260909 /workspace/db/zippy/scripts/migrate.sh up`; `docker exec zippy-m2-disposable-20260909 psql -X --set=ON_ERROR_STOP=1 -q -U zippy_m2_runner -d zippy_m2_disposable_validation --file=/workspace/db/zippy/tests/verify.sql`; `docker exec zippy-m2-disposable-20260909 pgbench -n -U zippy_m2_runner -d zippy_m2_disposable_validation -c 2 -j 2 -t 1 -f /workspace/db/zippy/tests/concurrent_claim.pgbench.sql`; corresponding `verify_concurrency.sql` and `verify_runner_rejection.sh` executions |
| Timestamp | 2026-09-09T08:34:43Z evidence captured after execution |
| Commit | Baseline `e2b0b5ecf0d0ee35ce3b82d896b265aca787697c`; canonical M2 implementation uncommitted |
| Environment | PostgreSQL `16.15 (Debian 16.15-1.pgdg13+2)` in isolated disposable Docker container; network `none`; no published ports |
| Preconditions | Healthy internal PostgreSQL endpoint; exact manifest order and SHA-256 values; ephemeral credential supplied only to container startup; repository mounted read-only |
| Exit code | 0 for final migration, SQL assertion, concurrency and runner-rejection commands |
| Result | PASS: four checksummed migrations applied in order; 48 Zippy tables, 45 RLS policies and exactly four ledger versions; only non-default extension `pgcrypto`; all behavioral assertions including expired-processing-lease recovery passed; two clients claimed distinct tasks; unexpected SQL was rejected |
| Evidence location | `db/zippy/migrations/manifest.tsv`, `db/zippy/tests/verify.sql`, `db/zippy/tests/verify_concurrency.sql`, `docs/reports/M2_DATABASE_IMPLEMENTATION_REPORT.md` |
| Redactions | Ephemeral generated password omitted; no secret, authorization header, personal data or production identifier recorded |
| Operator/automation | GitHub Copilot |
| Notes | Synthetic `.invalid` identities and synthetic operational/payment references only. One earlier `pgbench -q` invocation was invalid and made no claims; it was not accepted as evidence. The same test passed with the valid command shown above. PostgreSQL 15 was not separately run; 16.15 satisfies the approved PostgreSQL 15+ target. |

### M2-E003: Disposable Rollback, Reapply, and Cleanup

| Field | Value |
|---|---|
| Command | `docker exec -e PGUSER=zippy_m2_runner -e PGDATABASE=zippy_m2_disposable_validation -e ZIPPY_ALLOW_DISPOSABLE_DB=YES -e ZIPPY_CONFIRM_DISPOSABLE_DOWN=zippy_m2_disposable_validation zippy-m2-disposable-20260909 /workspace/db/zippy/scripts/migrate.sh down`; zero-schema/role `psql` assertions; repeated canonical `up` and `verify.sql`; `docker rm -f zippy-m2-disposable-20260909`; `docker volume rm zippy_m2_disposable_20260909_data`; container/volume/port absence checks |
| Timestamp | 2026-09-09T08:34:43Z evidence captured after execution |
| Commit | Baseline `e2b0b5ecf0d0ee35ce3b82d896b265aca787697c`; canonical M2 implementation uncommitted |
| Environment | Same isolated disposable PostgreSQL 16.15 environment as M2-E002 |
| Preconditions | Fresh apply, behavior, concurrency and manifest-rejection evidence passed; exact disposable database confirmation supplied |
| Exit code | 0 |
| Result | PASS: destructive down left zero `zippy` schemas and zero `zippy_migrator`, `zippy_app` or `zippy_readonly` roles; all four migrations reapplied; behavioral assertions passed again; only the named disposable container and volume were removed; no PostgreSQL listener remained |
| Evidence location | `db/zippy/scripts/migrate.sh`, `db/zippy/migrations/`, `docs/reports/M2_DATABASE_IMPLEMENTATION_REPORT.md`, this record |
| Redactions | Ephemeral generated password omitted |
| Operator/automation | GitHub Copilot |
| Notes | Down migrations are destructive and disposable-only. Production rollback remains forward-fix. No production database, Odoo, Paperclip, n8n, payment, deployment, DNS, firewall, Apache, system-service or legacy-migration change occurred. |

### M2-E004: Security Review Correction and Failed-Attempt Record

| Field | Value |
|---|---|
| Command | Security-focused review of role identity, ownership, RLS catalog state, ordinary down semantics, grants/default ACLs, function execution, sequence access, disposable guards and image identity; repeated executions of `db/zippy/scripts/run_isolated_proof.sh` after narrowly scoped corrections |
| Timestamp | 2026-09-09 UTC |
| Commit | Baseline `e2b0b5ecf0d0ee35ce3b82d896b265aca787697c`; corrected M2 implementation uncommitted |
| Environment | Fresh uniquely named PostgreSQL 16.15 containers/volumes/databases; Docker network `none`; no published ports; read-only repository mount; synthetic data only |
| Preconditions | M2 was reopened after review found that M2-E002 used the table-owning `zippy_m2_runner` session with `SET ROLE zippy_app`, and M2-E003 allowed ordinary rollback to delete cluster-global roles |
| Exit code | Non-zero for failed correction attempts; each failure remained M2-blocking until corrected and rerun from a new disposable environment |
| Result | RETAINED FAILURES: temporary-image-server readiness race; Unix-socket marker input missing because `docker exec` lacked `-i`; built-in `template1` false rejection; fixture tuple defect; RLS-before-FK test ordering; ambiguous sequence privilege overload; role-teardown inventory omitted `zippy_m2_runner`; and `pg_shdepend.deptype` internal `"char"` concatenation failed without `::text`. A separate local `grep -c` aggregation command failed before evaluating SQL and was corrected; it was not database-proof evidence. |
| Evidence location | `db/zippy/scripts/run_isolated_proof.sh`, `db/zippy/scripts/migrate.sh`, `db/zippy/scripts/roles.sh`, `db/zippy/tests/`, `docs/reports/M2_DATABASE_IMPLEMENTATION_REPORT.md`, this record |
| Redactions | Generated passwords and exact disposable secrets were neither printed nor recorded; external `/tmp` logs contain no credential values |
| Operator/automation | GitHub Copilot |
| Notes | M2-E002's owner-session RLS conclusion and M2-E003's ordinary-down role deletion are historical evidence, not accepted final security proof. Corrected design uses independent restricted LOGIN sessions, forced RLS, database-local ordinary rollback, and separately confirmed cluster-role teardown without `CASCADE`. No failed attempt is represented as passing. |

### M2-E005: Definitive Restricted-Identity Apply, Rollback/Reapply, and Teardown Proof

| Field | Value |
|---|---|
| Command | `db/zippy/scripts/run_isolated_proof.sh > /tmp/zippy-m2-security-proof-final-20260909.log 2>&1`; captured exact exit status; searched log for the first `ERROR`, `FATAL`, assertion failure, or traceback; extracted final result matrix and suite markers |
| Timestamp | Completed before evidence capture at `2026-09-09T09:37:29Z` |
| Commit | Baseline `e2b0b5ecf0d0ee35ce3b82d896b265aca787697c`; final M2 workspace state uncommitted |
| Environment | PostgreSQL `16.15 (Debian 16.15-1.pgdg13+2)` from already-local `postgres@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94`; image ID is the same SHA-256; unique disposable database/container/volume; Docker `--network none`; no ports; read-only repository mount |
| Preconditions | Exact manifest SHA-256 verification; independent database/container/volume/image markers; generated non-recorded credentials; guarded role bootstrap; migrations executed through restricted `zippy_m2_migration_login` under `zippy_migrator` |
| Exit code | 0; first matching error marker: none |
| Result | PASS: `fresh_up`, `restricted_app_rls_and_privileges`, `restricted_readonly`, `behavioral_assertions`, `concurrent_claim`, `stale_lease_recovery`, `runner_rejections`, `schema_down_roles_preserved`, `reapply_assertions`, `separate_role_teardown`, and `cleanup` all reported `PASS`. The catalog suite classified all 48 tables exactly once as 28 RLS required, 7 internal worker, 10 immutable audit, 1 migration metadata and 2 justified exempt; all 45 non-exempt operational tables had enabled and forced RLS. |
| Evidence location | External log `/tmp/zippy-m2-security-proof-final-20260909.log` with SHA-256 `7977b7695df56a63f11e166cc0fae75849a30c92f6d5b712167f555fe6ef9f2`; status file `/tmp/zippy-m2-security-proof-final-20260909.status`; canonical scripts/tests under `db/zippy/`; `docs/reports/M2_DATABASE_IMPLEMENTATION_REPORT.md`; this record |
| Redactions | No credentials, authorization values, production identifiers, personal data or real operational/payment data recorded |
| Operator/automation | GitHub Copilot |
| Notes | Application assertions ran as `zippy_m2_app_login`, read-only assertions as `zippy_m2_readonly_login`, and owner-force-RLS assertions as `zippy_migrator`. Ordinary down removed database-local objects and preserved roles; the independent guarded teardown removed exactly six managed roles while leaving the disposable superuser until container removal. PostgreSQL 15 was not separately run; PostgreSQL 16.15 is within the approved 15+ target. No production system was accessed. |

## M3 Deterministic Core Evidence

### M3-E001: Python Contracts and Static Analysis

| Field | Value |
|---|---|
| Command | `/tmp/zippy-m3-venv/bin/python -m pytest api/tests -q`; focused `ruff check`; `mypy --strict` over eight production modules; `python3 -m py_compile` |
| Timestamp | 2026-09-10 UTC |
| Commit | Baseline `a5b7048277a39336f0b7904702186736fc9f5ce9`; M3 changes uncommitted |
| Environment | Python 3.12.3; disposable virtual environment |
| Exit code | 0 |
| Result | PASS: 18 host tests passed and 2 database-only tests skipped by explicit environment guard; Ruff passed; strict mypy passed; production modules compiled |
| Evidence location | `api/tests/`, `docs/reports/M3_CORE_IMPLEMENTATION_REPORT.md` |
| Redactions | No tokens, database URLs or generated credentials recorded |
| Operator/automation | GitHub Copilot |
| Notes | Coverage includes validation, Decimal pricing, canonical fingerprints, signed-subject auth, fail-closed configuration, API errors, readiness and retry timing. |

### M3-E002: Restricted-Login End-to-End Proof

| Field | Value |
|---|---|
| Command | `db/zippy/scripts/run_m3_core_proof.sh` |
| Timestamp | 2026-09-10 UTC |
| Commit | Baseline `a5b7048277a39336f0b7904702186736fc9f5ce9`; M3 changes uncommitted |
| Environment | PostgreSQL 16.15; immutable image `postgres@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94`; Docker network `none`; no published port; private temporary Unix socket; restricted `zippy_m2_app_login` |
| Exit code | 0 |
| Result | PASS: all 20 tests passed; order intake, replay/conflict, authorization, transitions, task/outbox success and terminal failures passed; migration down, role teardown, network isolation and cleanup passed |
| Evidence location | `db/zippy/scripts/run_m3_core_proof.sh`, `db/zippy/tests/setup_m3.sql`, `api/tests/test_postgres_integration.py`, `docs/reports/M3_CORE_IMPLEMENTATION_REPORT.md` |
| Redactions | Random ephemeral passwords and Unix-socket database URL omitted |
| Operator/automation | GitHub Copilot |
| Notes | Synthetic `.invalid` identities only. Failed harness attempts retained diagnostically: custom socket bootstrap mismatch, bootstrap/final-server readiness race and API/worker pool-lifecycle test mismatch; each failed run cleaned its disposable artifacts and was not counted as passing evidence. |

### M3-E003: Dependency and Image Reproducibility

| Field | Value |
|---|---|
| Command | Fresh virtual-environment `pip install --require-hashes -r requirements-api.lock`; corresponding dev-lock install; direct import checks; `docker build -f Dockerfile.api -t zippy-api:m3-proof .` |
| Timestamp | 2026-09-10 UTC |
| Commit | Baseline `a5b7048277a39336f0b7904702186736fc9f5ce9`; M3 changes uncommitted |
| Environment | Fresh disposable Python 3.12 environments; local Docker builder |
| Exit code | 0 |
| Result | PASS: runtime and development lock graphs installed with SHA-256 enforcement and imported; API image built from pinned Python base and runtime lock |
| Evidence location | `requirements-api.txt`, `requirements-api.lock`, `requirements-api-dev.txt`, `requirements-api-dev.lock`, `Dockerfile.api` |
| Redactions | No package credentials or private index configuration used or recorded |
| Operator/automation | GitHub Copilot |
| Notes | Runtime lock SHA-256 `851d4200ac029aa7dbb104328a2208efec6cc5e2631a11b5e6c8efa8cad65b2d`; dev lock SHA-256 `7ffdeb9ba3219af6030933961445707f0e71dbcd8823b3d92e0d21c8f8bf133a`; pinned base digest `78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea`. Image was not pushed or deployed. |

### M3-E004: M2 Regression and Scope Boundary

| Field | Value |
|---|---|
| Command | `db/zippy/scripts/run_isolated_proof.sh`; Git diff/status/hygiene and host residue checks |
| Timestamp | 2026-09-10 UTC |
| Commit | Baseline `a5b7048277a39336f0b7904702186736fc9f5ce9`; M3 changes uncommitted |
| Environment | Same immutable PostgreSQL 16.15 image and network-isolated disposable controls as M2 |
| Exit code | 0 |
| Result | PASS: fresh up, restricted application/read-only controls, behavior, concurrency, stale lease, runner rejection, down/reapply, separate role teardown and cleanup passed with migration 0005 |
| Evidence location | `db/zippy/scripts/run_isolated_proof.sh`, `docs/reports/M3_CORE_IMPLEMENTATION_REPORT.md` |
| Redactions | Generated credentials omitted |
| Operator/automation | GitHub Copilot |
| Notes | No production/external system was accessed. M4 remains blocked and no task was activated. |

### M3-E005: Exit-Status Correction and Single Fresh Proof

| Field | Value |
|---|---|
| Command | `bash -n db/zippy/scripts/run_m3_core_proof_logged.sh`; wrapper `--self-test`; repeat harmless probe with exported `tail` returning `88`; exactly one `bash db/zippy/scripts/run_m3_core_proof_logged.sh`, observed through a read-only inotify monitor; exact Docker inventory membership and socket absence checks |
| Timestamp | Real proof: `2026-09-10T12:46:46.278618+00:00` through `2026-09-10T12:46:54.613978+00:00` |
| Commit | `a5b7048277a39336f0b7904702186736fc9f5ce9`, `master`; existing M3 changes preserved and correction uncommitted |
| Environment | Existing isolated M3 harness; network `none`, no published ports, original restricted-login/migration/cleanup controls unchanged |
| Preconditions | Owner authorized only wrapper, deployment prevention and evidence correction; baseline and complete Git status verified; existing proof interpreter present |
| Exit code | Harmless failure: expected/observed `37`; with tail failure `88`: wrapper still `37`; real harness `0`, observed wrapper `0` |
| Result | PASS: 20 passed, 2 warnings; nine harness PASS markers; exact cleanup checks passed. Warning details were not classified. No real-proof retry occurred. |
| Evidence location | `db/zippy/scripts/run_m3_core_proof_logged.sh`; `docs/reports/M3_CORE_IMPLEMENTATION_REPORT.md`; private temporary log `/tmp/zippy-m3-proof-log.O2xfnOs1/proof.log`, SHA-256 `3b7b209bd5460ef9b0e129e399e69f6b5ab1b41ee9e339eb8b133925d5fe183b` |
| Redactions | Only allowlisted status/count diagnostics displayed; no credential values or raw failure payloads published; log directory `700`, log `600`, tracing disabled |
| Operator/automation | GitHub Copilot |
| Notes | Container `zippy-m3-disposable-20260910124646-e9b43df5`, volume `zippy_m3_disposable_20260910124646_e9b43df5_data`, socket `/tmp/zippy-m3-socket-20260910124646_e9b43df5.vEe6rH` all absent after exit. Prior attempts and the earlier 19-versus-20 count discrepancy are retained; this record is fresh evidence. The initial strict summary filter missed the warnings-bearing summary, so safe count extraction was used without rerunning tests. Temporary logs are not durable archives. |

### M3-E006: Static Local Deployment Block

| Field | Value |
|---|---|
| Command | Parse `.github/workflows/deploy-hostinger.yml` with PyYAML; assert sole job `deploy` and unconditional `if: ${{ false }}` on every job; inspect all steps for local script/action invocation; editor diagnostics; `git diff --check` |
| Timestamp | 2026-09-10 UTC |
| Commit | `a5b7048277a39336f0b7904702186736fc9f5ce9`; local uncommitted correction |
| Exit code | 0 for YAML parse/gate assertions and whitespace validation |
| Result | PASS: deployment job cannot execute under the local workflow definition; YAML remains valid; existing deployment definition retained |
| Evidence location | `.github/workflows/deploy-hostinger.yml`; `docs/reports/M3_CORE_IMPLEMENTATION_REPORT.md` |
| Notes | No local deployment scripts/actions are invoked. Production Compose reference retained; no Compose file created or workflow commands executed. External GitHub environment protection/required reviewers remain NOT VERIFIED. This local change does not protect the remote branch until committed and pushed; neither was performed. No ServerAvatar call, secret change, deployment or tracker transition occurred. |

### M3-E007: Hardening Corrections (Non-Root Image, Socket, Cleanup Status, Redaction)

| Field | Value |
|---|---|
| Command | Host unit suite via `/tmp/zippy-m3-venv/bin/python -m pytest api/tests -q`; `docker build -f Dockerfile.api -t zippy-api:m3-hardening .`; isolated `docker run --rm --network none --entrypoint id zippy-api:m3-hardening`; `verify_m3_cleanup.sh --self-test`; wrapper `--self-test` including tail-failure variant; exactly one passing real proof via `bash db/zippy/scripts/run_m3_core_proof_logged.sh`; targeted disposable pg_hba probe on the pinned image/env; exact residue checks |
| Timestamp | 2026-09-10 UTC (passing proof resources timestamped `20260910132938`); evidence entry recorded 2026-09-11 after an interrupted session |
| Commit | `a5b7048277a39336f0b7904702186736fc9f5ce9`, `master`; hardening changes uncommitted; pre-existing M3 work preserved |
| Environment | Disposable PostgreSQL 16.15, pinned image, Docker network `none`, no published ports, hardened private Unix socket, synthetic `.invalid` identities only |
| Preconditions | Owner authorized the hardening scope; baseline/branch/status verified before edits; no host account, SSH user, or filesystem-ownership changes |
| Exit code | Host unit suite `0`; image build `0`; isolated identity check `0`; cleanup probe matrix `0` (all four combinations matched expected statuses); real proof `harness_exit_code=0`, `final_exit_code=0`, `cleanup-verification=PASS` |
| Result | PASS: 23 host tests passed with 2 isolated-DB skips, including 5 new output-redaction tests; API image configured and runs as `uid=10001(zippy) gid=10001(zippy)` in the isolated check; hardened proof passed with pytest `25 passed, 2 warnings` and `socket_hardening=PASS`; effective `socket_dir_mode=2700` (`rwx------` permission bits plus access-neutral setgid preserved by this filesystem), `socket_file_mode=777`, `password_encryption=scram-sha-256`, `pg_hba_local_auth=scram-sha-256`; `negative_local_user=PASS` (uid 65534 `nobody` via `setpriv`, no account changes); exact container `zippy-m3-disposable-20260910132938-1f21aa54`, volume `zippy_m3_disposable_20260910132938_1f21aa54_data`, and socket `/tmp/zippy-m3-socket-20260910132938_1f21aa54.cffp31` all absent after the run; zero `zippy` containers/volumes remain |
| Evidence location | `Dockerfile.api`; `db/zippy/scripts/run_m3_core_proof.sh`; `db/zippy/scripts/run_m3_core_proof_logged.sh`; `db/zippy/scripts/verify_m3_cleanup.sh`; `api/tests/test_output_redaction.py`; `api/tests/test_postgres_integration.py`; private log `/tmp/zippy-m3-proof-log.nMP56NHB/proof.log` (mode 600), SHA-256 `9217f3483147b40b95492d18fae604d055975b45cf7ab9469a0034140f344786`; `docs/reports/M3_CORE_IMPLEMENTATION_REPORT.md` |
| Redactions | Generated ephemeral passwords and full socket database URLs never printed or recorded; only allowlisted status/mode/auth lines surfaced from the private log |
| Operator/automation | GitHub Copilot |
| Notes | Retained failed attempts (not passing evidence, no blind retries): `mwACrOfD` failed on the trust-auth assertion, root-causing the image default `local ... trust` initdb behavior and leading to `POSTGRES_INITDB_ARGS=--auth-local=scram-sha-256` (authentication strengthened, never weakened; targeted probe confirmed effective `local all all scram-sha-256` despite stale initdb warning text); `UruMWWVE` failed on an over-strict new dead-letter assertion (`TypeError` from the deliberately mis-signed transport stub is expected); `mdEv5lw5` passed functionally but recorded entrypoint-broadened `socket_dir_mode=3775`, leading to post-readiness re-hardening with permission-bit-masked assertions. The 2 warnings are the known FastAPI/Starlette TestClient httpx shim and AnyIO `BlockingPortal` alias deprecations in locked test dependencies: classified deferred, not suppressed, locks unchanged. M2 regression not required: shared bootstrap/harness (`roles.sh`, `migrate.sh`, `run_isolated_proof.sh`) and migrations 0001–0004 untouched by this pass; the pre-existing `manifest.tsv` modification predates it. No logging was added as a test target; no production claim, deployment, tracker transition, or next-milestone work occurred. |

### M3-E009: Documentation Whitespace Correction

| Field | Value |
|---|---|
| Command | `git diff --check`; targeted edit of three Markdown hard-break lines; `git diff --cached --check` under `set -euo pipefail` |
| Timestamp | 2026-09-11 UTC |
| Commit | Preceded by acceptance commit `fa9dec6285590b8b3f4f5f00a70c79f727aaba43`; this note records the follow-up |
| Exit code | 0 |
| Result | PASS: the M3 acceptance commit proceeded after `git diff --cached --check` reported three documentation whitespace defects because the multi-command shell did not stop on the earlier failure. The defects were formatting-only (Markdown hard-break trailing spaces in the report metadata header). This follow-up removes them with normal Markdown paragraph breaks. No M3 executable behavior, test, migration, harness, dependency, Dockerfile, deployment workflow, tracker state, or proof result changed. |
| Evidence location | `docs/reports/M3_CORE_IMPLEMENTATION_REPORT.md`, this record |
| Redactions | None |
| Operator/automation | GitHub Copilot |
| Notes | Gate weakness recorded honestly: future staged checks must run under `set -euo pipefail` or as separately verified commands. M4 remains unbegun. |

### M4-E001: M4-OPERATIONS-FINANCE Owner Approval

| Field | Value |
|---|---|
| Command | Preflight baseline/remote/identity/worktree/tracker verification; complete reads of controlling documents, canonical migrations, and current API/worker code; verbatim approval recorded as D-26 |
| Timestamp | 2026-09-11 UTC |
| Commit | Baseline `2c5225b5edfcbac1739bb829c937e41bceee0eca`; approval documentation uncommitted |
| Environment | Repository workspace only |
| Preconditions | M3-CORE COMPLETE; M4-OPERATIONS-FINANCE sole IN_PROGRESS and not begun; local and `origin/master` matched the expected baseline; Git identity `Gopinathan <gopinathdisp@gmail.com>` |
| Exit code | 0 |
| Result | PASS: Gopinathan approved M4 implementation on 2026-09-11 as product, finance, and initial Odoo owner. D-26 records FastAPI as the Razorpay webhook ingress, sandbox-only payment scope, operational-projection-only payment updates, refund.processed as reconciliation-only against recorded manual approval, manual approval for every refund at every amount, manual settlement release, and a draft-only Odoo adapter with fake-server tests |
| Evidence location | `docs/DECISIONS.md` (D-26), this record |
| Redactions | No secrets or credentials recorded |
| Operator/automation | GitHub Copilot |
| Notes | The approval explicitly does not authorize live keys/payments, live Odoo credentials, autonomous posting/payment/reconciliation, direct Odoo database access, production deployment, automatic refunds or settlements, unrestricted n8n/Paperclip execution, or accounting-authority changes. M4 remains IN_PROGRESS; completion requires a separate acceptance audit. |

### M4-E002: Implementation Validation and Isolated Proofs

| Field | Value |
|---|---|
| Command | Host suite `/tmp/zippy-m3-venv/bin/python -m pytest api/tests api/tests_m4 -q`; focused `ruff check`; strict `mypy` over six new modules; manifest SHA-256 verification; exactly one passing `bash db/zippy/scripts/run_m4_finance_proof.sh` with private-log capture and original-status preservation; `bash db/zippy/scripts/run_isolated_proof.sh` for M2 regression plus 0006 up/down/reapply; exact residue checks |
| Timestamp | 2026-09-11 UTC |
| Commit | Baseline `2c5225b5edfcbac1739bb829c937e41bceee0eca`; M4 changes uncommitted |
| Environment | Disposable PostgreSQL 16.15 pinned image; Docker network `none`; no published ports; hardened private Unix socket; scram-sha-256 local auth; restricted logins; synthetic `.invalid` identities |
| Preconditions | D-26 owner approval recorded; preflight verified baseline, identity, clean worktree, tracker invariant |
| Exit code | Host suite `0`; focused ruff `0`; strict mypy `0`; M4 proof `0`; M2 regression `0` |
| Result | PASS: host suite 42 passed / 14 skipped / 2 known deferred dependency warnings; M4 proof 56 passed / 2 warnings with all harness markers PASS (webhook ingress, idempotency, authorization, POD settlement gate, manual refund, draft-only Odoo, reconciliation, M3 regression, network isolation, cleanup, socket hardening, negative local-user probe); M2 regression all 11 markers PASS including 0006 reapply and the PUBLIC-privilege catalog assertion |
| Evidence location | Private logs `/tmp/zippy-m4-proof-log.O5UuiYGu/proof.log` (SHA-256 `133c847f048f5f7fd3253301561cef377038cc9a6e2f857632bfc8458fe4c0e6`, mode 600) and `/tmp/zippy-m2-regression-log.TDszzz8i/proof.log`; `docs/reports/M4_OPERATIONS_FINANCE_IMPLEMENTATION_REPORT.md` |
| Redactions | No secrets, signatures, raw webhook bodies, or generated passwords printed or recorded |
| Operator/automation | GitHub Copilot |
| Notes | Retained failures (never counted as passing): M4 proof run 1 (`p4vCYNhy`) exposed four test defects (pool reopen after TestClient lifespan, refund-execution replay ordering, write helper misuse) — fixed and rerun once; M2 regression run 1 exposed the stale canonical-chain count (updated 5 to 6 per established milestone pattern); run 2 exposed default PUBLIC EXECUTE on the new 0006 function (REVOKE added, manifest checksum refreshed). The passing M4 proof predates the REVOKE; the delta is privilege-hardening only and is covered by the final M2 regression. Exact cleanup verified: M4 container `zippy-m4-disposable-20260911113226-99df5942`, volume `zippy_m4_disposable_20260911113226_99df5942_data`, socket `/tmp/zippy-m4-socket-20260911113226_99df5942.uoryZQ` all absent; zero zippy containers/volumes remain. |

### M4-E003: Scope Hygiene Correction During Implementation

| Field | Value |
|---|---|
| Command | `git status --short --untracked-files=all`; `git diff` of three legacy files; `git checkout --` limited to those files |
| Timestamp | 2026-09-11 UTC |
| Commit | Baseline `2c5225b5edfcbac1739bb829c937e41bceee0eca` |
| Exit code | 0 |
| Result | PASS: a directory-wide `ruff --fix` during lint remediation applied unintended pyupgrade-style edits to legacy `api/pod_lifecycle.py`, `api/services/hermes.py`, and `api/services/paperclip.py`; the diffs were verified to be mechanical import/type-annotation rewrites only and were reverted to HEAD. Final scope contains only intended M4 paths. |
| Evidence location | This record; final `git status` |
| Notes | Recorded honestly as a process defect: future lint fixes must run on explicit file lists, never directory-wide with `--fix`. No user work existed in those files; no behavior changed. |

### M4-E004: Payment-Contract and Amount-Semantics Correction

| Field | Value |
|---|---|
| Command | Read-only trace of the webhook→order linkage; design and implementation of an authoritative provider-reference mapping (`zippy.external_references` + new `zippy.payment_intents` in 0006) and explicit minor-unit amount validation; focused `ruff check` and strict `mypy` over the changed modules; new/updated regression tests |
| Timestamp | 2026-09-23 UTC |
| Commit | Baseline `2c5225b5edfcbac1739bb829c937e41bceee0eca`; correction uncommitted, preserving the pre-existing uncommitted M4 implementation |
| Environment | Repository workspace only (no database access for this step) |
| Preconditions | `git status`/`git rev-parse HEAD`/`origin/master` confirmed the expected baseline with the M4 in-progress worktree intact; `M4-OPERATIONS-FINANCE` confirmed sole `IN_PROGRESS` |
| Exit code | Focused ruff `0`; strict mypy `0` |
| Result | PASS: `notes.zippy_order_id` no longer participates in order resolution under any condition, including a valid signature; the webhook resolves the order only via `payload.payment.entity.order_id` through the tenant-scoped, provider+external-id-unique `zippy.external_references` mapping, extended with a new `zippy.payment_intents` table (0006) carrying the expected minor-unit amount/currency the existing schema could not express; the mapping is created only by `FinanceRepository.prepare_payment_intent` (the approved server-side payment-intent/order-preparation path) or its synthetic test fixture; amounts are validated as integer minor units (`_minor_units`, `MAX_AMOUNT_MINOR_UNITS = 999_999_999_999`), rejecting booleans, floats, strings, non-positive, and oversized values; minor↔major conversions use `Decimal` exact arithmetic only |
| Evidence location | `api/gateway.py`, `api/repositories_finance.py`, `db/zippy/migrations/0006_operations_finance.up.sql`/`.down.sql`, this record |
| Redactions | No secrets, signatures, or credentials involved (design/implementation step only) |
| Operator/automation | GitHub Copilot |
| Notes | No live Razorpay order creation or payment execution occurred or is authorized; `prepare_payment_intent` is invoked only by test fixtures in this change. |

### M4-E005: Regression Test Coverage for the Payment-Contract Correction

| Field | Value |
|---|---|
| Command | Host suite `PYTHONPATH="$PWD" /tmp/zippy-m3-venv/bin/python -m pytest api/tests api/tests_m4 -q` |
| Timestamp | 2026-09-23 UTC |
| Commit | Baseline `2c5225b5edfcbac1739bb829c937e41bceee0eca`; changes uncommitted |
| Environment | Recreated host Python venv (`/tmp/zippy-m3-venv`, ephemeral) from `requirements-api.txt`/`requirements-api-dev.txt`; DB-gated tests skip without `ZIPPY_M4_TEST_DATABASE_URL`/`ZIPPY_M3_TEST_DATABASE_URL` |
| Preconditions | M4-E004 changes present; focused ruff/mypy already PASS |
| Exit code | 0 |
| Result | PASS: **52 passed, 25 skipped**, 1 known deferred dependency warning. Focused new/changed test counts: 11 gateway unit tests (`api/tests/test_gateway.py`, including parametrized amount-validation cases) and 17 M4 integration tests (`api/tests_m4/test_finance_integration.py`, DB-gated, executed only inside the isolated M4 proof below). New/updated integration coverage proves: valid signature + authoritative mapping updates the compatible projection; valid signature + notes-only creates no order link; missing mapping creates no trusted projection; conflicting same-order-different-reference and different-order-already-bound-reference mappings are rejected (`ConflictError`); a mapping registered under a second synthetic platform is invisible to platform 1's resolution (cross-tenant); provider identifier / duplicate webhook replay stays idempotent (both payment and refund paths); amount and currency match succeeds; amount mismatch, currency mismatch, and unsafe amounts (bool/float/string/negative/zero/oversized, parametrized) never create a trusted projection; `refund.processed` without a manually approved matching execution remains evidence-only; a matching manually approved refund reconciles exactly once; a mismatched amount against an executed refund stays evidence-only; no automatic refund, settlement, or Odoo action occurs anywhere in the new tests |
| Evidence location | `api/tests/test_gateway.py`, `api/tests_m4/test_finance_integration.py`, `api/tests_m4/conftest.py` (`prepare_payment_intent` fixture, `ORDER_C`/`ORDER_D`/`CROSS_TENANT_*` fixtures), `db/zippy/tests/setup_m4.sql` (cross-tenant and dedicated conflict-fixture orders), this record |
| Redactions | No secrets; all identities remain synthetic/`.invalid` |
| Operator/automation | GitHub Copilot |
| Notes | Host run only proves collection/parsing and non-DB unit behavior; DB-gated M4 integration assertions are proven by the isolated proof in `M4-E006`. |

### M4-E006: Final M4 Disposable Proof and Subsequent M2 Regression

| Field | Value |
|---|---|
| Command | Exactly one `bash db/zippy/scripts/run_m4_finance_proof.sh` against the final application code, tests, 0006 up/down migration, and refreshed manifest checksum, captured via a private-log wrapper (`mktemp -d`, `umask 077`, output redirected, exit code appended, log `chmod 600`); followed by exactly one `bash db/zippy/scripts/run_isolated_proof.sh` (M2 regression, applies the full migration chain including 0006 and a down/up/down/reapply cycle) |
| Timestamp | 2026-09-23 UTC |
| Commit | Baseline `2c5225b5edfcbac1739bb829c937e41bceee0eca`; M4 correction uncommitted |
| Environment | Disposable PostgreSQL 16.15 pinned image (`postgres@sha256:f1c337…f6f94`); Docker network `none`; no published ports; hardened private Unix socket; scram-sha-256 local auth; restricted logins; synthetic `.invalid` identities |
| Preconditions | M4-E004/M4-E005 complete; baseline/branch/HEAD/origin verified unchanged; nothing staged |
| Exit code | Final M4 proof `0`; M2 regression `0` (both after retained, non-passing first attempts — see Notes) |
| Result | PASS: **final M4 proof — pytest `77 passed, 1 warning`**, all harness markers `PASS` (`m4_unit_contracts`, `m4_webhook_ingress`, `m4_idempotency`, `m4_authorization`, `m4_pod_settlement_gate`, `m4_manual_refund`, `m4_odoo_draft_only`, `m4_reconciliation`, `m3_regression`, `network_isolation`, `cleanup`, `socket_hardening`), `socket_dir_mode=2700`, `socket_file_mode=777`, `password_encryption=scram-sha-256`, `pg_hba_local_auth=scram-sha-256`, `negative_local_user=PASS`; **M2 regression — all 11 markers `PASS`** (`fresh_up`, `restricted_app_rls_and_privileges`, `restricted_readonly`, `behavioral_assertions`, `concurrent_claim`, `stale_lease_recovery`, `runner_rejections`, `schema_down_roles_preserved`, `reapply_assertions`, `separate_role_teardown`, `cleanup`), including the 0006 down/up/reapply and the PUBLIC-privilege catalog assertion |
| Evidence location | Private logs (mode 600, not committed): final M4 proof `/tmp/zippy-m4-proof-log.xVe8arOt/proof.log` (SHA-256 `fcac88de93c69f14ff93a759beb8d2bc590b680a74eb0acb52bff1edaaf6670f`); final M2 regression `/tmp/zippy-m2-regression-log.bogmnHKC/proof.log` (SHA-256 `43b85805bdbdeb8c1c15d0462c23d789515021406cbe79bfd7f7ebe0c7c35d5f`); `docs/reports/M4_OPERATIONS_FINANCE_IMPLEMENTATION_REPORT.md` |
| Redactions | No secrets, signatures, raw webhook bodies, or generated passwords printed or recorded |
| Operator/automation | GitHub Copilot |
| Notes | **Retained failures (never counted as passing):** (1) M4 proof attempt `2zIomoO3` (exit 1, `2 failed, 75 passed`, SHA-256 `cbcab9ffdccc5d12d8a394a64656acac72f69b84663e6d102fc797d6c9167498`) — `prepare_payment_intent`'s `INSERT ... ON CONFLICT` only arbitrated the `(external_system, external_model, external_id)` constraint, so a same-order rebind to a different provider reference raised an uncaught `psycopg.errors.UniqueViolation` instead of `ConflictError`; the same gap corrupted the shared `ORDER_B` fixture used by another test. Fixed with an explicit order-scoped pre-check plus dedicated `ORDER_C`/`ORDER_D` conflict fixtures; rerun once, passing. (2) M2 regression attempt `lyovExzs` (exit 3, SHA-256 `cc96555d315c1e5e5d3b58536b8bf9c3545457a5f4fbf2fcdec91feea28d4e51`) — `verify_security.sql`'s hardcoded table-classification catalog and its `RLS REQUIRED`/`platform_isolation`-policy counts (48/28/45) had not been updated for the new `zippy.payment_intents` table; fixed by adding the table to the catalog and bumping the counts to 49/29/46 (matching `verify.sql`'s already-updated 46); rerun once, passing. **Exact cleanup verified:** zero `zippy*` Docker containers or volumes remain after either proof; no leftover private socket directories under `/tmp`; port 5432 not listening on the host. **Confirms the correction notice in `docs/reports/M4_OPERATIONS_FINANCE_IMPLEMENTATION_REPORT.md`:** the 2026-09-11 M4 proof in `M4-E002` predated both the 0006 privilege (`REVOKE`) correction and this payment-contract correction and was never used as final acceptance evidence; this entry and `M4-E004`/`M4-E005` are the final-artifact proof for this update. `M4-OPERATIONS-FINANCE` remains `IN_PROGRESS` and is **not** marked `COMPLETE`. |

### M4-E007: Pre-Commit Acceptance Audit Finding Dispatch Incomplete (No Stage/Commit)

| Field | Value |
|---|---|
| Command | Full 13-step pre-commit acceptance audit (inventory, D-26 verification, Razorpay linkage/amount/refund/Odoo checks, migration/evidence/static-acceptance audits, and an exhaustive repo-wide `grep` for dispatch implementation across `api/`, `workers/`, `apps/`) |
| Timestamp | 2026-09-23 UTC |
| Commit | Baseline `2c5225b5edfcbac1739bb829c937e41bceee0eca`; all M4 work uncommitted throughout |
| Environment | Repository workspace only (read-only audit; disposable-proof re-verification for evidence-integrity checks) |
| Exit code | 0 (audit completed; no stage/commit occurred by design) |
| Result | 9 of 10 audit gates PASS. Gate 7 (operations coverage) **FAILED**: `zippy.dispatch_offers`/`zippy.trip_assignments` had database schema only (from M2) and zero application-layer implementation anywhere in the repository; POD was already fully implemented and evidenced. Per the audit's own decision rule, `M4-OPERATIONS-FINANCE` was left as sole `IN_PROGRESS`; nothing was staged, committed, or pushed |
| Evidence location | This record; conversation transcript of the audit |
| Redactions | No secrets involved (read-only audit) |
| Operator/automation | GitHub Copilot |
| Notes | This finding is the direct trigger for the dispatch implementation recorded in `M4-E008`/`M4-E009` below. An important architecture note surfaced during this audit: the API is single-tenant-per-process (`Settings.platform_id` comes from the `ZIPPY_PLATFORM_ID` environment variable at startup, never from request content), which is why the payment-webhook cross-tenant-mapping-ambiguity concern raised by the audit does not apply to the current deployment model. |

### M4-E008: Dispatch Implementation, Secret-Redaction Fix, and Payment-Intent Privilege Correction

| Field | Value |
|---|---|
| Command | Schema inspection (`zippy.dispatch_offers`, `trip_assignments`, `trips`, `vehicles`, `vehicle_models`, `vehicle_documents`, `driver_profiles`, `driver_associations`, `vendor_profiles`, `company_memberships`, `transaction_participants`, `order_transition_rules`, `transition_order`, `operational_events`, `event_outbox`); implementation of `api/repositories_dispatch.py`, `api/routes_dispatch.py`, `api/models/dispatch.py`; `Settings` `repr=False` secret-redaction fix (`api/config.py`); 0006 `payment_intents` grant correction (`SELECT, INSERT` only); focused `ruff`/strict `mypy` |
| Timestamp | 2026-09-23 UTC |
| Commit | Baseline `2c5225b5edfcbac1739bb829c937e41bceee0eca`; uncommitted, preserving all prior uncommitted M4 work |
| Environment | Repository workspace only for this step (no database access) |
| Preconditions | M4-E007 audit finding recorded; nothing staged; HEAD/origin/branch verified unchanged |
| Exit code | Focused ruff `0`; strict mypy `0` (`api/config.py`, `api/repositories_dispatch.py`, `api/models/dispatch.py`, `api/routes_dispatch.py`, `api/main.py`, plus the six modules from `M4-E004`) |
| Result | PASS: dispatch offer creation validates one caller-named vendor/vehicle/driver candidate (no automatic search/scoring/ranking) against order status, hazardous/ambiguous special-handling, vendor/vehicle/driver approval, driver-vendor association, vehicle capacity, verified+unexpired fitness/insurance documents, and vehicle/driver availability, using only existing canonical tables — **zero schema change was required for dispatch**; one schema blocker was identified and reported rather than worked around (vehicle/body-type compatibility has no canonical `zippy.orders` field). Atomic accept locks the order row first, uses the pre-existing `dispatch_one_accepted_offer_idx` partial unique index, and transitions the order only via the existing `zippy.transition_order` RPC. `Settings` now excludes `database_url`, `auth_jwt_secret`, and `razorpay_webhook_secret` from `repr()`/`str()` via `dataclasses.field(repr=False)`. `zippy.payment_intents` runtime grants corrected to `SELECT, INSERT` only (no `UPDATE`/`DELETE`) — a grant-only change; no table/RLS/FK/uniqueness definition changed |
| Evidence location | `api/repositories_dispatch.py`, `api/routes_dispatch.py`, `api/models/dispatch.py`, `api/config.py`, `db/zippy/migrations/0006_operations_finance.up.sql`, `docs/reports/M4_OPERATIONS_FINANCE_IMPLEMENTATION_REPORT.md`, this record |
| Redactions | No secrets involved (implementation step) |
| Operator/automation | GitHub Copilot |
| Notes | No live network code exists anywhere in the dispatch module (confirmed by inspection and by a later test that patches `socket.socket.connect`). Dispatch never broadcasts/contacts drivers, vendors, or transport companies, and invents no radius/timeout/ranking/escalation values. |

### M4-E009: Focused Tests, Final M4 Proof, and M2 Regression for the Dispatch/Redaction/Privilege Correction

| Field | Value |
|---|---|
| Command | (1) Focused unit tests `pytest api/tests/test_config_redaction.py -q`; (2) focused PostgreSQL integration development iteration via `bash db/zippy/scripts/run_m4_finance_proof.sh` (repeated locally until stable, defects fixed in-place — see Notes; intermediate logs not individually retained since these predate the final gated proof); (3) complete host suite `PYTHONPATH="$PWD" pytest api/tests api/tests_m4 -q` with direct, unmasked exit-code capture; (4) exactly one final `bash db/zippy/scripts/run_m4_finance_proof.sh`, captured via the private-log wrapper (`mktemp -d`, `umask 077`, output redirected, exit code appended, `chmod 600`); (5) exactly one `bash db/zippy/scripts/run_isolated_proof.sh` (M2 regression, required because 0006's grants changed), same private-log wrapper; (6) independent post-proof cleanup verification (`docker ps`, `docker volume ls`, socket-directory glob, `ss -lntH` for port 5432) |
| Timestamp | 2026-09-23 UTC |
| Commit | Baseline `2c5225b5edfcbac1739bb829c937e41bceee0eca`; all changes uncommitted |
| Environment | Recreated host Python venv (`/tmp/zippy-m3-venv`); disposable PostgreSQL 16.15 pinned image (`postgres@sha256:f1c337…f6f94`); Docker network `none`; hardened private Unix socket; scram-sha-256 local auth; synthetic `.invalid` identities |
| Preconditions | M4-E008 implementation complete; focused ruff/mypy already PASS |
| Exit code | Focused unit tests `0`; complete host suite `0`; final M4 proof `0`; M2 regression `0` |
| Result | PASS: focused unit tests **4 passed** (secret-redaction); complete host suite **56 passed, 51 skipped**, 1 known deferred dependency warning, exit `0` (captured directly, never piped through `tail`); final M4 proof **107 passed, 1 warning**, exit `0`, all harness markers `PASS` (`m4_unit_contracts`, `m4_webhook_ingress`, `m4_idempotency`, `m4_authorization`, `m4_pod_settlement_gate`, `m4_manual_refund`, `m4_odoo_draft_only`, `m4_reconciliation`, `m3_regression`, `network_isolation`, `cleanup`, `socket_hardening`), `socket_dir_mode=2700`, `socket_file_mode=777`, `password_encryption=scram-sha-256`, `pg_hba_local_auth=scram-sha-256`, `negative_local_user=PASS`; M2 regression all 11 markers `PASS` (`fresh_up`, `restricted_app_rls_and_privileges`, `restricted_readonly`, `behavioral_assertions`, `concurrent_claim`, `stale_lease_recovery`, `runner_rejections`, `schema_down_roles_preserved`, `reapply_assertions`, `separate_role_teardown`, `cleanup`); independent post-proof cleanup check: zero `zippy*` containers/volumes, no leftover socket directories, port 5432 not listening. The 107-passed total includes 20 new dispatch tests (`api/tests_m4/test_dispatch_integration.py`, covering eligible creation+accept, capacity/document/driver/availability/hazardous/ambiguous/cross-tenant/order-status manual-review and rejection paths, unauthorized/expired/declined/cancelled-offer denial, idempotent replay, concurrent competing acceptance with exactly one resulting assignment, transactional rollback on an injected order-status conflict, absence of raw network calls, and secret-free error text) and 4 new payment-intent privilege tests (`api/tests_m4/test_payment_intent_privileges.py`) |
| Evidence location | Private logs (mode 600, not committed): final M4 proof `/tmp/zippy-m4-final-proof.SBBPRUZW/proof.log` (SHA-256 `aaa151afe294ea8871b65a17bf683c56f146b042de749332215d0af295641604`); final M2 regression `/tmp/zippy-m2-final-regression.3DR4xnvV/proof.log` (SHA-256 `d83595da1624eb1c8c9160e6b66091b3eba75e4c605a0a0d0a7d5ccc70f9375c`); `docs/reports/M4_OPERATIONS_FINANCE_IMPLEMENTATION_REPORT.md` |
| Redactions | No secrets, signatures, raw webhook bodies, connection strings, or generated passwords printed or recorded in either log (independently grepped) |
| Operator/automation | GitHub Copilot |
| Notes | **Development-iteration defects found and fixed before the final gated proof (not retained as individual logs; see the implementation report for detail):** (1) an outbox idempotency-key collision between `transition_order`'s own outbox row and the dispatch-specific one (fixed by suffixing the key); (2) test fixture cross-contamination from reusing shared baseline vehicle/driver/order fixtures across multiple tests that perform a real, permanent accept (fixed with dedicated per-test fresh fixtures); (3) an attempt to persist an `'expired'` status transition inside the same transaction as the `ConflictError` that then rolled it back (fixed by extracting `expire_if_due` into its own committed transaction, called before the accept attempt). **The final M4 proof and M2 regression both passed on their first run after these fixes — no additional gated-attempt failures occurred for this update.** `M4-OPERATIONS-FINANCE` remains `IN_PROGRESS`; `docs/EXECUTION_TRACKER.md` was not modified; production remains blocked; `deploy-hostinger.yml` remains disabled (`if: ${{ false }}`, job-level). |

### M4-E010: ORD-INV-003 Body-Type Compatibility Correction (Trusted `dispatch_requirements`)

| Field | Value |
|---|---|
| Command | (1) Read-only recovery after a power-cut interruption: `git status`/`rev-parse`/`diff --check`, Docker/volume/socket/port inventories, and per-file consistency inspection of the interrupted edits; (2) py_compile + Ruff + strict mypy on `api/repositories_dispatch.py`, `api/repositories.py`, `api/tests_m4/test_dispatch_integration.py`; (3) host suite `PYTHONPATH="$PWD" pytest api/tests api/tests_m4 -q` with direct exit capture; (4) `bash db/zippy/scripts/run_m4_finance_proof.sh > log 2>&1` (exit 1 — retained); (5) after test-fixture fixes, exactly one fresh `run_m4_finance_proof.sh` and one `run_isolated_proof.sh` (M2 regression, required because 0006/manifest/grants/security SQL changed), each captured to a `install -m 600` log without piping through `tail`; (6) independent cleanup verification |
| Timestamp | 2026-09-24 UTC |
| Commit | Baseline `2c5225b5edfcbac1739bb829c937e41bceee0eca` (HEAD, origin/master, and remote all equal); all changes uncommitted; nothing staged |
| Environment | Recreated host Python venv (`/tmp/zippy-m3-venv`); disposable PostgreSQL 16.15 pinned image (`postgres@sha256:f1c337…f6f94`); Docker network `none`; hardened private Unix socket (mode 0700 dir, scram-sha-256 local auth); synthetic `.invalid` identities |
| Preconditions | Interrupted M4 pass recovered from filesystem; the `zippy.dispatch_requirements` schema (0006), gate logic, verify counts (47 policies / 50 tables / 30 RLS-required), RLS, and grants were found already present and internally consistent; only the focused body-type tests and evidence docs were unfinished |
| Exit code | py_compile `0`; Ruff `0`; mypy `0`; host suite `0` (**56 passed, 60 skipped**); first M4 proof **`1` (10 failed, 106 passed — retained, not counted)**; final M4 proof `0` (**116 passed, 1 warning**); M2 regression `0` (all 11 markers PASS) |
| Result | PASS. ORD-INV-003 trusted body-type compatibility is now enforced: matching body type permits eligibility; explicit known-vs-known mismatch rejects (`VEHICLE_BODY_TYPE_MISMATCH`, no offer created); missing requirement → `DISPATCH_BODY_TYPE_REQUIREMENT_MISSING`; unknown/unvocabularied requirement → `DISPATCH_BODY_TYPE_UNKNOWN`; hazardous/ambiguous special handling still fails closed; the offer-accept request has no body-type field and cannot override the stored requirement; cross-tenant requirement rows are RLS-denied on insert and invisible on read; the requirement row is immutable to the runtime role (`SELECT, INSERT` only — UPDATE/DELETE raise SQLSTATE 42501 before and after an offer/assignment exists); capacity and body compatibility must both pass; rejection creates no offer/assignment/order transition; idempotency and single-assignment concurrency behavior unchanged (all pre-existing dispatch tests still pass). Manifest: only 0006 up/down SHA-256 refreshed; 0001–0005 byte-identical to HEAD. |
| Evidence location | Private logs (mode 600, not committed): final M4 proof `/tmp/zippy-m4-proof-bodytype-r2.log` (SHA-256 `7e241b377196f6348312948d474fcf82325bd3a427aa6b23359f7626658dd986`); final M2 regression `/tmp/zippy-m2-regression-bodytype.log` (SHA-256 `34361b04ab0627b7d337bbaa4753a0029c5c463764cfaeec8e6aad73c9a92f4b`); **retained failed attempt (not counted)** `/tmp/zippy-m4-proof-bodytype.log` (SHA-256 `2b35d1d6d2ee4198a0d5606e9086c1be7e1ed6ab2552515409bd824c8ad45399`); `docs/reports/M4_OPERATIONS_FINANCE_IMPLEMENTATION_REPORT.md` |
| Redactions | No secrets, connection strings, or generated passwords recorded in any log (independently grepped); the redacted `postgres@sha256:f1c337…f6f94` digest abbreviation is the image identity, not a secret |
| Operator/automation | GitHub Copilot |
| Notes | **Root cause of the retained failed proof (classified B/C — test-fixture / incorrect-expectation defects, not a production or migration defect):** (1) the new immutability test performed a real accept against the *shared* `VEHICLE_1`/`DRIVER_PROFILE_1` fixtures, permanently consuming them and cascading `VEHICLE_UNAVAILABLE`→`manual_review`→`dispatch_offer_id=None` into 7 later lifecycle tests — fixed with dedicated fresh vehicle/driver (the file's own documented anti-pattern); (2) the mismatch/override/no-assignment tests used a requirement (`closed-box`) absent from `vehicle_models`, so the gate's `body_type_known` check correctly returned `DISPATCH_BODY_TYPE_UNKNOWN` instead of `VEHICLE_BODY_TYPE_MISMATCH` — fixed by cataloguing a `closed` model (`_catalogue_closed_model()`); (3) the cross-tenant test attempted an app-role INSERT of a platform-2 row, which forced-RLS `WITH CHECK` correctly rejected — fixed to assert the RLS denial and the missing-requirement fallback. **No production code or migration was changed by the fix; only test fixtures/expectations.** No canonical body-type taxonomy exists anywhere (PRD/DECISIONS/schema all leave `vehicle_models.body_type` free text); this correction deliberately does not invent one and treats the platform's own `vehicle_models` set as the recognized vocabulary, failing closed otherwise. `M4-OPERATIONS-FINANCE` remains `IN_PROGRESS`; `docs/EXECUTION_TRACKER.md` was not modified; production remains blocked; `deploy-hostinger.yml` remains disabled. |

### M4-E011: Final Acceptance Audit (M4 → COMPLETE)

| Field | Value |
|---|---|
| Command | Full read-only acceptance audit: baseline/branch/HEAD/origin equality; complete worktree inventory with per-path M4 classification; immutability checks (0001–0005, lockfiles, `docker-compose.yml`, production config, `deploy-hostinger.yml`, legacy paths); D-26 single-occurrence/2026-09-11 Gopinathan approval verification; static gates (`git diff --check`, Ruff, `py_compile`, strict mypy, Bash `-n`, workflow YAML parse, manifest full-SHA-256 validation, focused secret scan, prohibited-authority scan); code/test security audit (webhook HMAC, refund reconcile-only, POD gate, Odoo draft-only allowlist, redaction, dispatch network-free); evidence-log validation (existence, mode 600, secret-clean, expected totals) and artifact-drift check; independent cleanup verification |
| Timestamp | 2026-09-24 UTC |
| Commit | Baseline `2c5225b5edfcbac1739bb829c937e41bceee0eca` (HEAD = origin/master = remote master); acceptance edits then committed as the single reviewed M4 commit |
| Environment | Repository workspace + read-only validation; no test/container/database/service execution during the audit (proofs reused, not rerun — see Notes) |
| Preconditions | All M4 implementation, body-type correction, proofs, and regression complete; nothing staged |
| Exit code | `0` for every audit gate |
| Result | PASS on all gates. Strict mypy claim re-verified by real execution: `mypy --strict` exit `0` over 12 modules. Static gates all PASS. Security invariants confirmed from code/tests. Evidence logs valid and artifacts un-drifted, so the expensive full proofs were not rerun. Retained failed body-type proof exit `1` (`10 failed, 106 passed`, SHA-256 `2b35d1d6d2ee4198a0d5606e9086c1be7e1ed6ab2552515409bd824c8ad45399`); final M4 proof exit `0` (`116 passed, 1 warning`, all markers PASS, SHA-256 `7e241b377196f6348312948d474fcf82325bd3a427aa6b23359f7626658dd986`); final M2 regression exit `0` (11 markers PASS, SHA-256 `34361b04ab0627b7d337bbaa4753a0029c5c463764cfaeec8e6aad73c9a92f4b`); host suite exit `0` (`56 passed, 60 skipped`). Cleanup independently confirmed: zero `zippy*` containers/volumes, no socket directories, port 5432 free. |
| Evidence location | `docs/reports/M4_OPERATIONS_FINANCE_IMPLEMENTATION_REPORT.md`, this record, and the three private mode-600 logs above (not committed) |
| Redactions | No credentials, signatures, authorization headers, private keys, or connection strings read or recorded |
| Operator/automation | GitHub Copilot |
| Notes | **Outcome: `M4-OPERATIONS-FINANCE` transitioned to COMPLETE; `M5-PAPERCLIP` transitioned to the sole IN_PROGRESS task and is explicitly not begun — it has no implementation authority until its own separate governance/owner approval.** Production remains BLOCKED; `deploy-hostinger.yml` remains disabled at job level (`if: ${{ false }}`); the absent `docker-compose.production.yml` reference was not invoked or created. No deployment, live payment, live Odoo call, production database operation, or M5/Paperclip implementation occurred. `/opt/paperclip` was not modified. Remaining NOT VERIFIED external behavior (unchanged): live Razorpay sandbox/production payload compatibility, live Odoo 18 API behavior and custom-field availability, live regulatory-registry validation of driver/vehicle documents, canonical hazardous-cargo enum, production ingress/credentials. |

### M3-E008: Pre-Commit Acceptance Audit and M4 Handoff

| Field | Value |
|---|---|
| Command | Complete reads of controlling documents; full Git status/diff inventory; symlink, legacy-tree, migration-immutability and manifest checksum checks; static security assertions (auth claim scope, server-side role resolution, fail-closed idempotency, non-root image, network isolation, socket mode, scram-sha-256, negative probe, deployment gate); lock pin/hash verification; added-content sensitive-material scans; proof-log checksum and marker validation; executable-file drift check against the passing proof; `git diff --check`; Bash/Python/YAML static checks; disposable residue checks |
| Timestamp | 2026-09-11 UTC |
| Commit | Baseline `a5b7048277a39336f0b7904702186736fc9f5ce9`; this entry is included in the acceptance commit |
| Environment | Repository workspace only; no test, container, database, or service execution during the audit |
| Preconditions | Owner authorized the acceptance audit and, only if all gates pass, staging, one normal commit, and a normal push to `origin/master` |
| Exit code | 0 for all audit gates |
| Result | PASS: every changed path accounted for by M3 purpose; legacy Supabase/Paperclip/migration trees untouched; migrations 0001–0004 byte-identical to HEAD; manifest 0005 checksums match file SHA-256 values; no symlinks, artifacts, logs, caches, or credentials in scope; no drift after the passing proof (no rerun required); `user_metadata.role` cannot influence authorization; JWT requires `sub`/`aud`/`exp` with `zippy-api` audience; deployment job carries job-level `if: ${{ false }}`; missing production Compose reference unchanged; tracker invariant satisfied |
| Evidence location | `docs/reports/M3_CORE_IMPLEMENTATION_REPORT.md`, `docs/EXECUTION_TRACKER.md`, this record; private log checksum `9217f3483147b40b95492d18fae604d055975b45cf7ab9469a0034140f344786` revalidated |
| Redactions | No credentials or secret values read or printed |
| Operator/automation | GitHub Copilot |
| Notes | Tracker handoff follows the established convention: `M4-OPERATIONS-FINANCE` is the sole `IN_PROGRESS` task and is explicitly not begun; its authorized scope remains empty and product, finance, and Odoo owner approvals remain required. No task implementation began; no production readiness is claimed. |

## M5 Paperclip Governance Evidence

### M5-E001: Read-Only Discovery and Owner-Approved Minimal MVP Boundary

| Field | Value |
|---|---|
| Command | Read-only baseline, tracker, workflow-gate, and `/opt/paperclip` inventory verification; complete governance-document/source review; documentation-only owner-boundary recording and validation |
| Timestamp | 2026-09-25 UTC |
| Commit | Baseline `588c46a44aa9d18b144eef0313dc0f44ff7b56c6`; documentation approval changes uncommitted at evidence capture |
| Environment | `/opt/new-logistic` documentation workspace and read-only `/opt/paperclip` inspection |
| Preconditions | `master`; local, `origin/master`, and remote `master` at the baseline; empty index; M4 complete; M5 sole `IN_PROGRESS`; deployment job disabled |
| Exit code | 0 for completed read-only validation groups |
| Result | PASS: read-only discovery completed. `/opt/paperclip` remains reference-only with inventory SHA-256 `dc3d4355e502d4fc678b6b3b43a4e70deb86b09109fd4c0aeccd29a055fdad4`; it is not Git-backed, so its commit/origin provenance is unavailable. D-27 records the owner-approved Minimal MVP boundary. |
| Evidence location | `docs/reports/M5_PAPERCLIP_DISCOVERY_REVIEW.md`, `docs/DECISIONS.md` (D-27), `docs/EXECUTION_TRACKER.md`, this record |
| Redactions | No secret values, credentials, connection strings, tokens, keys, cookies, certificates, or environment values recorded |
| Operator/automation | GitHub Copilot |
| Notes | Exact documentation scope is these four paths only: `docs/DECISIONS.md`, `docs/EXECUTION_TRACKER.md`, `docs/TEST_EVIDENCE.md`, and `docs/reports/M5_PAPERCLIP_DISCOVERY_REVIEW.md`. M5 remains the sole `IN_PROGRESS` task and implementation has not begun. D-27 authorizes only isolated schema/migration, least-privilege/RLS, governance service, and disposable synthetic security/concurrency/rollback proof work after a separate exact preflight. No database, container, service, migration, deployment, network integration, external API, dependency, application-code, or `/opt/paperclip` operation occurred; production remains prohibited. |

### M5-E002: Owner Approval of Privileged Function Boundary

| Field | Value |
|---|---|
| Command | Read-only baseline, D-27/D-28 sequence, tracker, deployment-gate, and `/opt/paperclip` inventory verification; documentation-only D-28 recording and validation |
| Timestamp | 2026-09-25 UTC |
| Commit | Baseline `d2ba98cca5eefe48cc6c31b0e84d57449031bed2`; documentation approval changes uncommitted at evidence capture |
| Environment | `/opt/new-logistic` documentation workspace only |
| Preconditions | Clean `master`; D-27 present; D-28 absent; M5 sole `IN_PROGRESS`; deployment job disabled; preserved-source inventory unchanged |
| Result | PASS: D-28 authorizes a fixed allowlist of M5 governance transitions through narrowly scoped PostgreSQL `SECURITY DEFINER` functions because direct application-role table mutation is prohibited. |
| Controls | Dedicated `NOLOGIN`, `NOSUPERUSER`, `NOBYPASSRLS` function owner; fixed safe `search_path`; schema-qualified objects; no dynamic SQL; `PUBLIC` execution denied; only explicit application-role execute grants; forced RLS, tenant validation, direct-write denial, shadowing resistance, atomic single-use grant consumption, and complete governance evidence required. |
| Evidence location | `docs/DECISIONS.md` (D-28), this record |
| Redactions | No secret values, credentials, connection strings, tokens, keys, cookies, certificates, or environment values recorded |
| Operator/automation | GitHub Copilot |
| Notes | No implementation, migration, database, container, service, network, external API, credential, or `/opt/paperclip` operation occurred. Production and external integrations remain prohibited. |
