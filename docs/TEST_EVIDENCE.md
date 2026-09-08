# Zippy Test and Discovery Evidence

## Evidence Policy

- Current verdict: **BLOCKED FOR PRODUCTION — SAFE TO PLAN M1**.
- This file distinguishes read-only discovery evidence from executable test evidence.
- Historical repository counts are not current results.
- No application, SQL, integration, build, lint, security, container, or database test was executed during M0 discovery.
- No container or database is marked operational.
- Secret values, credentials, authorization headers, private keys, database URLs, and sensitive SSH endpoint details must never be recorded here.

## Production PRD Precedence

`docs/ZIPPY_PRODUCTION_EXECUTION_PRD.md` was imported after M0 discovery and is the production execution source of truth pending final owner approval and commit. It was not present during discovery and is not discovery-time evidence. Conflicting legacy documents are historical until reconciled. Their business rules must not be silently rewritten or discarded. Architecture deviations require a proposed `docs/DECISIONS.md` entry and owner approval. No legacy document was edited during this correction task.

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
