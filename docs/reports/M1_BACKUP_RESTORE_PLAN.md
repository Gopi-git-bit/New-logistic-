# M1 Backup and Restore Plan

## Status and Scope

**Task:** `M1-BACKUPS`
**Baseline:** `6980e4c0652cb2539ef7292bebaba2b90c58d7b6`
**Mode:** Read-only capability assessment and proposed backup/restore design.

No backup, archive, database, schedule, service, configuration, upload, restore, or deletion action was performed. No database contents, backup contents, credentials, connection strings, or secret values were read.

This plan is not an execution authorization. The Minimal-Cost MVP values approved below are policy decisions only; the stronger post-volume values remain proposals requiring separate owner and data-custodian approval.

## Current Discovery Evidence

Discovery was performed on the approved repository/VPS baseline on 2026-09-08 UTC using status-only or metadata-only commands. Exact command timestamps were not captured. Results are current discovery evidence, not proof of backup success.

| Area | Observed result | Interpretation |
|---|---|---|
| Repository | `/opt/new-logistic`, `master`, local and remote at `6980e4c0652cb2539ef7292bebaba2b90c58d7b6`, clean before this report | Documentation baseline is clean and synchronized |
| Host PostgreSQL | `postgresql` and `postgresql@16-main` inactive/not found as enabled units | No host PostgreSQL runtime was verified |
| Containers | Docker service active; no running containers reported; Docker volume count `0` | No containerized PostgreSQL, Odoo, Paperclip, or application runtime was verified |
| Odoo | No active Odoo unit or running Odoo container | Odoo database and filestore are not currently verified on this host |
| Paperclip | `/opt/paperclip` checkout exists; no active Paperclip unit or running Paperclip container | Source exists, but runtime database, persistence, and backup scope are deferred until activation |
| ServerAvatar/Apache | ServerAvatar unit active; Apache active and owns public web service | Apache/ServerAvatar configuration and routing are recoverable deployment assets, but no backup workflow was found |
| Repository volume declarations | Compose declares future PostgreSQL data, Redis data, and Odoo data named volumes; Odoo also declares read-only addon/config bind mounts; migration bind source is a repository path | These are declarations only; no corresponding active Docker volumes were present |
| Object/document storage | No current object-storage bucket, mount, or application document store was verified; code contains document/POD URL and metadata concepts | Future binary storage path and provider must be selected and backed up with metadata relationships |
| Dump utilities | `pg_dump`, `pg_restore`, and `psql` not found | Logical PostgreSQL backup/restore cannot currently be executed on this host |
| Encryption/archive utilities | OpenSSL, GPG, tar, zstd, gzip, zip, unzip, and sha256sum present; age, restic, and borg not found | Generic primitives exist, but no approved backup packaging/key procedure is installed |
| Schedules | System timers include OS package database backup, log rotation, updates, certificates, and filesystem maintenance; no Zippy/Odoo/Paperclip backup timer found | OS package metadata backup is not application backup coverage |
| Cron | No Zippy/Odoo/Paperclip backup job found in inspected cron directories | No application schedule or latest-success record is available |
| Backup locations | `/var/backups` contains OS package metadata only; `/backup`, `/backups`, `/srv/backups`, and `/opt/backups` absent | No application backup set, retention tier, or local restore source was verified |
| Capacity | Root filesystem showed approximately 181 GB available at discovery time; mounted filesystems were inventoried | Capacity is not an approved backup destination or retention decision |
| Off-server destination | No rclone/restic/borg/S3/remote-backup configuration filename or tool was found in inspected paths | No off-server copy is currently evidenced |
| Restore evidence | Existing evidence ledger and discovery reports record no successful isolated restore | Recovery is unproven and must remain unclaimed |

## Expected Recovery Scope and Ownership

The following is the required future scope. A path is an ownership target, not evidence that the asset currently exists.

| Asset | Authority and backup scope | Consistency requirement |
|---|---|---|
| Zippy operational PostgreSQL | Operational identities, roles, orders, trips, offers, locations, POD metadata, payment evidence, idempotency, webhooks, outbox, audit, and exceptions | Logical dump must be transaction-consistent and paired with migration/dependency provenance |
| Odoo PostgreSQL | Odoo accounting and ERP database, through an approved Odoo-owned backup procedure | Database backup must be coordinated with the Odoo filestore and recorded as one recovery point |
| Odoo filestore | Odoo attachments and generated files in the Odoo filestore volume or approved equivalent | Capture must correspond to the Odoo database backup; database-only recovery is incomplete |
| Vehicle/POD binaries | Object/file storage for vehicle documents and POD binaries | Backup binary bytes, content checksum, object key/reference, metadata, authorization relationship, and verification result together |
| Apache/ServerAvatar | Apache virtual-host/routing/TLS metadata and ServerAvatar application/release configuration, excluding secret values and private keys from Git | Preserve a versioned redacted configuration record and separately protected secret/key recovery procedure |
| Application deployment configuration | Compose/proxy/process definitions, image/source revision, migration manifest/checksums, dependency lock provenance, and non-secret environment variable names | Never copy secret values into the repository or evidence ledger |
| Paperclip database/configuration | Deferred until Paperclip runtime activation; isolated governance database and its approved configuration | Must never share Zippy or Odoo backup identity, database, volume, or restore target |
| Encryption keys and secrets | Separate recovery procedure owned by security/operations; keys are not stored in Git or ordinary backup reports | Test key escrow/retrieval and rotation without recording secret values |
| Audit/evidence records | Zippy audit events, Paperclip governance logs after activation, backup job results, checksums, restore reports, and approval records | Keep append-only or tamper-evident evidence separate from application data where practical |

A VPS snapshot alone is not a sufficient database backup. Snapshots do not replace transaction-consistent logical backups, Odoo database/filestore coordination, integrity checks, migration provenance, or an isolated restore test.

## Proposed Backup Architecture

All items in this section are **PROPOSED — OWNER APPROVAL REQUIRED** unless explicitly identified as current discovery.

### Logical PostgreSQL Backups

- Use a least-privilege backup identity for each database authority. It may read required schemas and large objects but must not administer users, alter application data, or use application credentials.
- Produce transaction-consistent logical PostgreSQL archives for Zippy operational PostgreSQL and Odoo PostgreSQL. Use a format that supports selective restore and post-restore verification once the approved host toolchain exists.
- Record archive size, creation time, source environment class, schema/migration revision, tool version, checksum, encryption status, and result without recording database names, usernames, URLs, or data.
- Do not treat a dump command exit code alone as success. A backup is successful only after isolated restore and acceptance tests pass.
- Paperclip logical backup remains deferred until runtime activation, with an isolated identity and destination.

### Physical and Snapshot Role

- A physical PostgreSQL base backup or VPS/provider snapshot may reduce recovery time and support later point-in-time recovery, but it is a secondary recovery layer.
- Snapshots must not be used as the only database protection. They may be crash-consistent rather than application-consistent, can capture unwanted secrets or stale state, and do not prove logical portability.
- Any approved physical method must document consistency guarantees, encryption, retention, deletion protection, provider custody, restore location, and how it aligns with WAL/archive retention if PITR is selected.

### Point-in-Time Recovery

- PITR is a later option for live order/payment volume. It requires a tested base backup, continuous WAL/archive handling, a separate destination, clock/retention policy, monitoring, and a documented recovery target procedure.
- PITR must never be inferred from the existence of a snapshot. WAL availability, replay continuity, and restore-to-target evidence are required.
- MVP may defer PITR if the owner accepts the resulting recovery-point gap and uses more frequent logical backups plus a tested restore path.

### Odoo Database and Filestore Consistency

- Capture the Odoo database and filestore as one coordinated recovery point using an approved Odoo-compatible procedure.
- Do not back up only the database or only the filestore. Verify that attachment references, generated documents, and database records agree after restore.
- Odoo backups must preserve Odoo accounting authority without creating a Zippy ledger mirror. Odoo API/ORM boundaries remain unchanged.

### Document and Metadata Consistency

- Store or copy document binaries with immutable object references and SHA-256 checksums.
- Back up the metadata relationship linking object reference, business entity, document type, uploader, verification outcome, and integrity reference.
- Acceptance must prove that restored metadata points to the restored binary and that the checksum matches, without exposing document contents in evidence.
- A missing binary, changed checksum, or orphaned metadata record is a restore failure even if the database starts.

### Encryption and Access

- Encrypt data in transit to the backup destination and at rest at the source, transfer layer, and destination.
- Use separate backup identities and key scope from application identities. Keys must be held in an approved secret/key-management or escrow process, never in Git.
- Record key identifier/version and rotation state, not key material. Define a key-loss procedure that includes escrow access, emergency rotation, and the effect on historical archives.
- GPG/OpenSSL availability is current host capability only; it does not establish an approved production key custody design.

### Off-Server Copy and Retention

- Maintain an encrypted off-server copy in a separately controlled destination. The destination class must be approved for residency, access, cost, deletion protection, and incident response.
- Use immutable or deletion-protected retention for at least the agreed critical tiers. Application operators should not be able to silently delete the only recovery copy.
- Keep migration manifests, dependency-lock provenance, release revision, and backup evidence with each recovery point so a restore can reproduce the application contract.

### Integrity, Monitoring, and Alerts

- Generate a cryptographic checksum for each archive and verify it after transfer and before restore.
- Monitor job start, completion, duration, archive size anomalies, checksum mismatch, destination capacity, age of newest successful backup, and failed/partial uploads.
- Alert on a failed job, missing expected job, stale latest-success record, destination authentication failure, insufficient space, checksum failure, or backup age beyond the approved threshold.
- Do not use application logs as the only backup evidence; retain an append-only or protected backup result ledger.

## Proposed Cost-Sensitive Options

### Option A: Minimal-Cost MVP Protection

**OWNER APPROVED — 2026-09-09 — Gopinathan**

- Separate logical backups for Zippy operational PostgreSQL and Odoo PostgreSQL at least daily, with Odoo filestore captured in the same recovery window.
- One encrypted off-server destination class with deletion protection where available; no VPS-only reliance.
- Keep a short local staging buffer only if capacity is approved; local copies are not the recovery guarantee.
- Use a simple scheduled worker or approved host scheduler, a least-privilege backup identity, checksum verification, failure notification, and a documented manual restore runbook.
- Defer PITR and Paperclip backup until live financial/order volume or Paperclip activation justifies the additional cost.
- Tradeoff: lowest recurring cost and modest operational effort, but recovery point loss may approach the backup interval and recovery is slower than PITR.

### Option B: Stronger Protection After Live Payment/Order Volume Increases

**PROPOSED — OWNER APPROVAL REQUIRED**

- Daily logical backups plus more frequent base/WAL archival for operational PostgreSQL and a coordinated Odoo database/filestore process.
- Encrypted off-server copies in a separate account or provider boundary with immutability/deletion protection and separate backup administration.
- Automated age, checksum, destination-capacity, and restore-readiness alerts; regular isolated restore drills with evidence.
- Add PITR only after base-backup, WAL retention, key custody, and replay tests are operationally proven.
- Activate an isolated Paperclip backup policy when Paperclip runtime is approved; include application/configuration provenance for every stateful system.
- Tradeoff: higher storage, transfer, monitoring, key-management, and drill effort, with lower data-loss exposure and faster recovery.

## Proposed Owner Decisions and Initial Values

Every stronger post-volume value below is **PROPOSED — OWNER APPROVAL REQUIRED**. The Minimal-Cost MVP values are **OWNER APPROVED — 2026-09-09 — Gopinathan**; none is active or implemented.

| Decision | Minimal-cost MVP proposal | Stronger post-volume proposal | Owner decision required |
|---|---|---|---|
| Zippy operational database RPO | **OWNER APPROVED — 2026-09-09 — Gopinathan:** 24 hours | **PROPOSED — OWNER APPROVAL REQUIRED:** 1 hour or tighter with WAL/PITR | Select acceptable order/location/payment-evidence loss window |
| Zippy operational service RTO | **OWNER APPROVED — 2026-09-09 — Gopinathan:** 8 hours | **PROPOSED — OWNER APPROVAL REQUIRED:** 2 hours or tighter | Select recovery staffing and service restoration target |
| Odoo RPO | **OWNER APPROVED — 2026-09-09 — Gopinathan:** 24 hours with coordinated database/filestore copy | **PROPOSED — OWNER APPROVAL REQUIRED:** 1 hour or tighter if Odoo volume warrants | Finance owner must approve accounting recovery point |
| Odoo RTO | **OWNER APPROVED — 2026-09-09 — Gopinathan:** 12 hours | **PROPOSED — OWNER APPROVAL REQUIRED:** 4 hours or tighter | Finance/operations owner must approve ERP recovery target |
| Logical backup frequency | **OWNER APPROVED — 2026-09-09 — Gopinathan:** daily | **PROPOSED — OWNER APPROVAL REQUIRED:** hourly operational capture plus daily full logical backup | Choose schedule and capacity budget |
| Retention | **OWNER APPROVED — 2026-09-09 — Gopinathan:** 7 daily copies, 4 weekly copies, 3 monthly copies | **PROPOSED — OWNER APPROVAL REQUIRED:** 35 daily copies, 12 weekly copies, 12 monthly copies plus immutable tier | Approve legal/finance retention and deletion policy |
| Off-server destination class | **OWNER APPROVED — 2026-09-09 — Gopinathan:** encrypted object storage in a separate account/provider boundary | **PROPOSED — OWNER APPROVAL REQUIRED:** separate-account immutable object storage with deletion protection | Select provider, residency, custody, and monthly budget |
| Restore-test frequency | **OWNER APPROVED — 2026-09-09 — Gopinathan:** quarterly isolated restore | **PROPOSED — OWNER APPROVAL REQUIRED:** monthly isolated restore plus annual disaster-recovery exercise | Assign restore owner and test environment |
| Maximum acceptable backup age | **OWNER APPROVED — 2026-09-09 — Gopinathan:** 26 hours for daily MVP protection | **PROPOSED — OWNER APPROVAL REQUIRED:** 2 hours for hourly/PITR protection | Define alert threshold and escalation |
| Failed/stale alert threshold | **OWNER APPROVED — 2026-09-09 — Gopinathan:** alert after one failed job or age over 26 hours | **PROPOSED — OWNER APPROVAL REQUIRED:** page after one failed job or age over 2 hours | Approve channel, escalation, and response time |

These proposals do not set statutory retention, accounting retention, privacy deletion, or legal hold periods. Those must be separately approved and reconciled with Odoo and document-retention obligations.

## Approved Custody and Architecture Boundaries

Gopinathan is the initial backup and encryption-key custodian. The custodian must keep backup credentials and decryption/recovery material outside the application repository and outside the backed-up VPS. Recovery material must have a separately protected recovery copy so loss of one device or account does not make backups unusable.

n8n Cloud may later orchestrate backup-failure notifications. It must not possess the sole decryption key; its execution history is not backup evidence, and it is not the authoritative backup ledger or restore controller.

## Restore Runbook Design

The following runbook is proposed and must be executed only after separate authorization:

1. Declare the incident and assign the operations recovery owner, database owner, finance/Odoo owner, and security/key custodian.
2. Freeze or isolate the affected environment without deleting evidence. Preserve redacted job results, checksums, release revision, migration revision, and incident correlation IDs.
3. Select the approved recovery point and verify checksum, encryption/key availability, archive completeness, and source environment classification.
4. Provision an isolated disposable restore environment. Routine restore tests must never target production.
5. Restore the database using the approved logical or physical procedure; restore Odoo database and filestore as a coordinated pair.
6. Restore document binaries and metadata references, then verify checksums and orphan/reference counts without exposing customer data.
7. Apply only the migration/release state approved for that recovery point. Do not improvise schema changes during recovery.
8. Run the acceptance tests below and record pass/fail evidence in the protected ledger.
9. Validate application health, authorization, queue/outbox behavior, and read-only Odoo boundary behavior against the isolated restore.
10. Obtain owner, operations, security, and finance sign-off before any production recovery. Production recovery is a separately authorized incident action, not a routine restore test.
11. Record gaps, data-loss window, elapsed recovery time, key/credential rotation actions, and follow-up corrections.

## Restore Acceptance Tests

A restore is successful only when all applicable tests pass and evidence is recorded without customer data or secrets:

- **Schema/migration:** restored schema revision, migration ledger, extension capability, and release/dependency-lock provenance match the selected recovery point.
- **Structural sanity:** table/object counts, non-sensitive row-count ranges, foreign-key/reference checks, and orphan checks pass without printing customer records.
- **Order/trip integrity:** order and trip state histories remain valid; no direct status rewrite, impossible transition, duplicate assignment, or lost milestone is detected.
- **Admin-block audit:** account block/suspend/unblock history retains actor, reason, old/new status, correlation, and active-trip exception evidence.
- **Payment/Odoo references:** verified payment/webhook evidence and immutable Odoo external references remain linked; operational projections are not mistaken for posted/reconciled accounting truth.
- **Refund evidence:** every restored refund request has manual approval evidence, requester/approver separation, amount/target binding, decision time, and execution evidence; no automatic-refund path is introduced.
- **Document integrity:** restored vehicle/POD metadata, object references, authorization decisions, verification outcomes, and SHA-256 checksums agree.
- **Idempotency/webhooks:** idempotency records and webhook receipts preserve request hashes, provider event identity, duplicate handling, and retry state.
- **SSE recovery continuity:** persisted event history and authorized cursors allow reconnect/replay of missed trip/payment projection events; SSE remains a projection, not independent truth.
- **Role isolation:** customer, vendor/driver, transport-company, and admin authorization tests cannot cross-read or mutate unauthorized orders, trips, locations, documents, payment projections, or account controls.
- **Application health:** the application starts against the restored database, liveness/readiness behavior is sanitized, protected routes enforce RBAC, and no live payment, Odoo posting, settlement, reconciliation, or refund action is triggered.
- **Odoo filestore pairing:** restored Odoo attachments and database references agree; accounting records remain Odoo-authoritative.

## Key Loss, Rotation, and Incident Recovery

- Secret values, private keys, database credentials, encryption keys, and connection strings must never be stored in Git or this report.
- Maintain a separately controlled recovery procedure for key escrow, authorized retrieval, rotation, revocation, and archive re-encryption. Record only key identifiers, versions, custody status, and incident references.
- If a key is lost, stop treating affected archives as recoverable until escrow/recovery is verified; do not weaken encryption or copy secrets into chat/logs.
- If a credential is exposed, revoke/rotate it, assess backup and application access, preserve evidence, and record the recovery decision. Backup identities must not be reused as application identities.
- Incident recovery ownership must be explicit: operations coordinates service recovery; database owner handles Zippy restore; finance/Odoo owner validates ERP recovery; security/key custodian validates cryptographic access; owner approves production restoration.

## Evidence Ledger Requirements

Each future backup or restore evidence record must include: immutable evidence ID, redacted command/procedure, UTC timestamp, commit/release revision, environment class, preconditions, authorization reference, exit/result, backup or restore point identifier, archive checksum, size and age metadata, tool/version, destination class, redactions, operator, acceptance-test results, and limitations.

Do not record database names, usernames, URLs, credentials, document contents, customer rows, payment payloads, private keys, or secret values. A `latest-success` record is not sufficient without a successful isolated restore record.

## Completion Assessment

The Minimal-Cost MVP backup-policy values and initial custody assignment are owner approved. The stronger post-volume option remains deferred and unapproved. Current discovery found no application backup capability or successful restore evidence. No backup, database, archive, upload, restore, deletion, schedule, service, or configuration action occurred.
