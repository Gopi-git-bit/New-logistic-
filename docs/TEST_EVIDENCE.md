# Zippy Test and Discovery Evidence

## Evidence Policy

- Current verdict: **BLOCKED FOR PRODUCTION — SAFE TO PLAN M1**.
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
