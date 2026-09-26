# M5 Paperclip Database Implementation Report

## Status

M5-A is complete. The latest disposable proof attempt exited `0`; all D-28 security, concurrency, rollback, and reapply markers passed; exact cleanup verified; passing evidence recorded as `M5-E008` in `docs/TEST_EVIDENCE.md`. Baseline commit `f7c8d9019cea7a68191552ea35d3ab7fa3b73c15`; M5-A changes uncommitted.

## Retained Diagnostic Attempts

### M5-A-F001

The first disposable PostgreSQL attempt exited before SQL execution. The harness required SCRAM but omitted `POSTGRES_PASSWORD`, omitted an explicit disposable `POSTGRES_USER`, created the socket directory as root rather than the PostgreSQL runtime identity, and kept polling `pg_isready` after the container had exited. The operator stopped the harness. Exact cleanup then verified zero `paperclip-m5-*` containers, zero `paperclip_m5_*` volumes, and zero `paperclip-m5.*` socket directories. No SQL proof result exists.

The correction derives the pinned image's PostgreSQL identity (`999:999`) with a disposable `id` invocation; creates a `0700` socket directory owned by that identity; supplies a generated unrecorded synthetic SCRAM password, explicit synthetic database/user, and `listen_addresses=''`; captures mode-0600 diagnostics; checks container liveness on every readiness iteration; and bounds readiness to 30 seconds.

### M5-A-F002

The single corrected second attempt exited `125` before PostgreSQL startup and before SQL execution. Docker interpreted `-c listen_addresses=` as a Docker option because it was placed before the image. Neither PostgreSQL nor SQL was reached. Cleanup passed: zero `paperclip-m5-*` containers, volumes, and socket directories. Private log `/tmp/m5-a-second-proof.tm5Tcm` (mode `0600`).

Correction: the invocation is a Bash array in `docker create [DOCKER OPTIONS] IMAGE postgres -c listen_addresses= -c unix_socket_directories=/var/run/postgresql` order, with credentials in a mode-0600 `--env-file` deleted by the cleanup trap. A static check asserts `postgres` immediately follows the pinned image, every `-c` follows `postgres`, and no port publication or host network exists; an unstarted `docker create` confirmed Docker parsed it (`Args` = `postgres -c listen_addresses= -c unix_socket_directories=/var/run/postgresql`, network `none`, `PortBindings` `{}`) and left no residue.

### M5-A-F003 through M5-A-F014

Each was a distinct root cause, corrected once; no root cause recurred.

| ID | Failure | Correction |
|---|---|---|
| F003 | `manifest.tsv` final row lacked a trailing newline, so `migrate.sh up` applied zero migrations yet exited `0` | Runner reads an unterminated final row, rejects non-`disposable_only` rows, and fails if no migration was processed |
| F004 | Migrator could not transfer function ownership (`must be able to SET ROLE`); `public` REVOKE was a no-op for a non-owner | `SET`-only (no `INHERIT`) membership in the function owner; transient schema `CREATE` for the transfer, revoked immediately; `public` hardening moved to the superuser bootstrap |
| F005 | `GRANT/REVOKE EXECUTE` ran after ownership transfer and silently did nothing, leaving default `PUBLIC` execute on definer functions | Execute privileges set while the migrator still owns the functions |
| F006 | Fixtures inserted without tenant context; forced RLS correctly failed closed | Fixtures set per-tenant context; RLS unchanged |
| F007 | Function owner lacked `paperclip` schema `USAGE` | Minimal `USAGE` plus `EXECUTE` on `current_tenant()` only |
| F008 | TTL assertion ran as the app role, which correctly has no `SELECT` | Denial asserted explicitly; TTL inspected by the table owner under RLS |
| F009 | Search-path assertion matched rendered function text | Exact `proconfig` equality; invalid SQL in the prior check replaced |
| F010 | Malformed payload hash `'abc'` accepted because `char(64)` pads | `CHECK (payload_hash ~ '^[0-9a-f]{64}$')` on proposals and grants |
| F011 | Approval, grant issuance, and consumption emitted no governance evidence | Activity-log rows for all three and a `grant.issued` outbox row; identifiers only |
| F012 | `create_proposal` and `evaluate_loop_guard` omitted `action_taken` in `INSERT INTO paperclip.loop_guard_events`, violating table NOT NULL constraint during loop-guard trigger on the 3rd equivalent proposal | Supply `action_taken = 'BLOCK'` in the column and select list |
| F013 | `verify_security.sql` invoked `acquire_decision_lock` under `SET ROLE paperclip_migrator`, failing with permission denied because execute privilege is restricted to `paperclip_app` | Execute governance functions as `paperclip_app`; added negative assertion that `paperclip_migrator` execution is denied |
| F014 | `verify_security.sql` interpolated composite variable `(:acquire_lock).*` into a `DO $$` block causing SQL syntax error at colon | Query function result directly via `SELECT allowed, reason_code FROM ...` or assign scalar field to session setting before `DO $$` |
| F015 | Flattened scalar boolean returned by `\gset` was interpolated unquoted into a plain `SELECT`, so PostgreSQL parsed the values `t`/`f` as column references | Quote the scalar variable and cast explicitly: `:'acquire_lock_allowed'::boolean` and `:'revoke_allowed'::boolean` |
| F016 | `verify_security.sql` expects `consume_grant(..., 'abc')` to raise because of the table `CHECK` constraint on `payload_hash`, but `consume_grant` only compares the input hash against existing rows and returns a graceful `GRANT_CONSUMPTION_DENIED` denial; the `UNEXPECTED_SUCCESS` branch is therefore reached | Either validate the hash format explicitly inside `consume_grant` (and other hash-taking functions) and raise on mismatch, or change the malformed-hash assertion to expect a graceful `allowed=false` result instead of an exception |
| F017 | `verify_security.sql` durable-state assertion expected zero tenant-two proposals after cross-tenant attempts, but `verify.sql` intentionally creates one tenant-two loop fixture (`idempotency_key = 'loop-1'`) after proving cross-tenant loop isolation; the check therefore raised `tenant two can see or received proposals` | Replace the zero-proposal assertion with a fixture-aware check: exactly one tenant-two proposal owned by tenant-two agent `22222222-2222-2222-2222-222222222223` and policy `22222222-2222-2222-2222-222222222224` with idempotency key `loop-1`, and zero tenant-two approvals or grants |

Every failed attempt's cleanup was verified. No assertion was weakened.

## Disposable Proof Attempt (M5-A-F014 Run)

`bash db/paperclip/scripts/run_m5_proof.sh`, stdout/stderr captured in mode-0600 log `/tmp/m5-proof-run.zmfIeH` (SHA-256 `6b68a3ae771de63122ef4d329e0e84d4fe7cc28fb30cecce90319609f4e6771f`), harness exit status `3`.

Passing markers established before the failure:
- `socket_isolation` (socket_dir_mode=2700, owner=999:999, non-root user denied)
- `migrate_up` (migrations=1)
- `lifecycle` (PASS)
- `budget_fail_closed` (PASS)
- `loop_guard` (PASS)
- `policy_checksum_fail_closed` (PASS)
- `heartbeat` (PASS)
- `verify` (PASS)
- `catalog_security` (PASS)
- `unauthorized_role_denied` (PASS)
- `tenant_context_fail_closed` (PASS)
- `direct_write_and_ddl_denied` (PASS)

Failure site: `db/paperclip/tests/verify_security.sql:197` on `DO $$ BEGIN IF (SELECT allowed FROM (SELECT (:acquire_lock).*) s) IS DISTINCT FROM true THEN ...`. Error: `syntax error at or near ":"`.

Per D-28 and recovery instructions, execution stopped immediately on this failure without automatic retry.

Independent cleanup verified:
- Zero `paperclip-m5-*` containers
- Zero `paperclip_m5_*` volumes
- Zero `/tmp/paperclip-m5.*` socket directories
- Zero `/tmp/paperclip-m5-env.*` files
- No host port 5432 listener
- Mode-0600 log contains no secrets or credential values

Migration checksums at execution:
- `0001_governance.up.sql`: `6088f93a4db878f59da217a22430bd1c85772adf4cb801251d1ddcf2ed89878c`
- `0001_governance.down.sql`: `de439a6efb128ad27e89616cd8945eaba689faa0b6f3ec9963130761e2dfe961`

## Disposable Proof Attempt (M5-A-F015 Run)

`bash db/paperclip/scripts/run_m5_proof.sh proof`, stdout/stderr captured in mode-0600 log `/tmp/m5-proof-run.28df9629a943` (SHA-256 `d261b680dbb98c85706306ebc6012752a940c3b2386135f1d6819f0bc8dc4f5a`), harness exit status `3`.

Passing markers established before the failure:
- `socket_isolation`
- `migrate_up`
- `lifecycle`
- `budget_fail_closed`
- `loop_guard`
- `policy_checksum_fail_closed`
- `heartbeat`
- `verify`
- `catalog_security`
- `unauthorized_role_denied`
- `tenant_context_fail_closed`
- `direct_write_and_ddl_denied`
- silent negative `paperclip_migrator` execution denial (no explicit marker echo in the test file)

Failure site: `db/paperclip/tests/verify_security.sql:198` on `SELECT CASE WHEN :acquire_lock_allowed IS NOT TRUE THEN (1/0)::int END;`. Error: `column "t" does not exist` because the `\gset` boolean value (`t`/`f`) was interpolated unquoted and parsed as a column reference.

Correction applied: quote and cast the scalar variables: `:'acquire_lock_allowed'::boolean` and `:'revoke_allowed'::boolean`. No further disposable proof was run per the stop-on-failure rule.

Independent cleanup verified:
- Zero `paperclip-m5-*` containers
- Zero `paperclip_m5_*` volumes
- Zero `/tmp/paperclip-m5.*` socket directories
- Zero `/tmp/paperclip-m5-env.*` files
- No host port 5432 listener
- Mode-0600 log contains no secrets or credential values

Migration checksums at execution:
- `0001_governance.up.sql`: `6088f93a4db878f59da217a22430bd1c85772adf4cb801251d1ddcf2ed89878c`
- `0001_governance.down.sql`: `de439a6efb128ad27e89616cd8945eaba689faa0b6f3ec9963130761e2dfe961`

## Disposable Proof Attempt (M5-A-F016 Run)

`bash db/paperclip/scripts/run_m5_proof.sh proof`, stdout/stderr captured in mode-0600 log `/tmp/m5-proof-run.7ede80b111f1` (SHA-256 `0faf53138749b7aadf1271f4274e20820c27227e54125c2fec081629863dd1f3`), harness exit status `3`.

Passing markers established before the failure:
- `socket_isolation`
- `migrate_up`
- `lifecycle`
- `budget_fail_closed`
- `loop_guard`
- `policy_checksum_fail_closed`
- `heartbeat`
- `verify`
- `catalog_security`
- `unauthorized_role_denied`
- `tenant_context_fail_closed`
- `direct_write_and_ddl_denied`
- `governance_denials_issue_no_grant`
- `grant_binding_revocation_expiry_replay`

Failure site: `db/paperclip/tests/verify_security.sql:276` on `PERFORM paperclip.consume_grant(gen_random_uuid(), '11111111-1111-1111-1111-111111111112', 'REFUND', 'ZIPPY', 'order', 'x', 'abc');`. Error: `UNEXPECTED_SUCCESS malformed payload hash` because `consume_grant` returned a graceful denial instead of raising an exception for the `'abc'` hash.

No code change was applied after this run per the stop-on-failure rule.

Independent cleanup verified:
- Zero `paperclip-m5-*` containers
- Zero `paperclip_m5_*` volumes
- Zero `/tmp/paperclip-m5.*` socket directories
- Zero `/tmp/paperclip-m5-env.*` files
- No host port 5432 listener
- Mode-0600 log contains no secrets or credential values

Migration checksums at execution:
- `0001_governance.up.sql`: `6088f93a4db878f59da217a22430bd1c85772adf4cb801251d1ddcf2ed89878c`
- `0001_governance.down.sql`: `de439a6efb128ad27e89616cd8945eaba689faa0b6f3ec9963130761e2dfe961`

## Disposable Proof Attempt (M5-A-F017 Run)

`bash db/paperclip/scripts/run_m5_proof.sh proof`, stdout/stderr captured in mode-0600 log `/tmp/m5-proof-run.9adfbd769760` (SHA-256 `5d445cf1f3091466f0691edcf34610f6abf2fc4af3855e1c92af67bd57f5fcf0`), harness exit status `3`.

Passing markers established before the failure:
- `socket_isolation`
- `migrate_up`
- `lifecycle`
- `budget_fail_closed`
- `loop_guard`
- `policy_checksum_fail_closed`
- `heartbeat`
- `verify`
- `catalog_security`
- `unauthorized_role_denied`
- `tenant_context_fail_closed`
- `direct_write_and_ddl_denied`
- `governance_denials_issue_no_grant`
- `grant_binding_revocation_expiry_replay`
- `malformed_arguments_denied`
- `shadowing_resisted`
- `cross_tenant_arguments_denied`
- `append_only_evidence`

Failure site: `db/paperclip/tests/verify_security.sql:386` on the tenant-two visibility assertion `IF EXISTS (SELECT 1 FROM paperclip.action_proposals WHERE tenant_id = current_setting('paperclip.tenant_id', true)::uuid) THEN RAISE EXCEPTION 'tenant two can see or received proposals'; ...`. Error: `tenant two can see or received proposals` because `verify.sql` legitimately creates one tenant-two loop fixture (`idempotency_key = 'loop-1'`) after proving cross-tenant loop isolation, and `verify_security.sql` expected zero tenant-two proposals.

Correction applied: the durable-state assertion was replaced with a fixture-aware check that expects exactly one tenant-two proposal owned by the tenant-two agent (`22222222-2222-2222-2222-222222222223`) and policy (`22222222-2222-2222-2222-222222222224`) with idempotency key `loop-1`, and zero tenant-two approvals or grants. This preserves the cross-tenant leakage invariant without weakening the security boundary.

Independent cleanup verified:
- Zero `paperclip-m5-*` containers
- Zero `paperclip_m5_*` volumes
- Zero `/tmp/paperclip-m5.*` socket directories
- Zero `/tmp/paperclip-m5-env.*` files
- No host port 5432 listener
- Mode-0600 log contains no secrets or credential values

Migration checksums at execution:
- `0001_governance.up.sql`: `6088f93a4db878f59da217a22430bd1c85772adf4cb801251d1ddcf2ed89878c`
- `0001_governance.down.sql`: `de439a6efb128ad27e89616cd8945eaba689faa0b6f3ec9963130761e2dfe961`

## Disposable Proof Attempt (M5-A Passing Run)

`bash db/paperclip/scripts/run_m5_proof.sh proof`, stdout/stderr captured in mode-0600 log `/tmp/m5-proof-run.f86cb61a7d90` (SHA-256 `9a7e25059e261de6093f196b862079329932f2ad6031b07690d941f6bcc009d9`), harness exit status `0`.

All D-28 markers passed:
- `socket_isolation` (socket_dir_mode=2700, owner=999:999)
- `migrate_up` (migrations=1)
- `lifecycle`
- `budget_fail_closed`
- `loop_guard`
- `policy_checksum_fail_closed`
- `heartbeat`
- `verify`
- `catalog_security`
- `unauthorized_role_denied`
- `tenant_context_fail_closed`
- `direct_write_and_ddl_denied`
- `governance_denials_issue_no_grant`
- `grant_binding_revocation_expiry_replay`
- `malformed_arguments_denied`
- `shadowing_resisted`
- `cross_tenant_arguments_denied`
- `append_only_evidence`
- `durable_state_and_evidence`
- `security`
- `concurrency` (successes=1, attempts=1)
- `fresh_up_and_verify`
- `rollback`
- `reapply`

Independent cleanup verified:
- Zero `paperclip-m5-*` containers
- Zero `paperclip_m5_*` volumes
- Zero `/tmp/paperclip-m5.*` socket directories
- Zero `/tmp/paperclip-m5-env.*` files
- No host port 5432 listener
- Mode-0600 log contains no secrets or credential values

Migration checksums at execution:
- `0001_governance.up.sql`: `6088f93a4db878f59da217a22430bd1c85772adf4cb801251d1ddcf2ed89878c`
- `0001_governance.down.sql`: `de439a6efb128ad27e89616cd8945eaba689faa0b6f3ec9963130761e2dfe961`

## Inventory

`db/paperclip/` contains the versioned migration and rollback, checksum manifest, restricted roles, migration runner, disposable harness, and SQL verification suite. The schema owns governance-only data: tenants, agents, policies, initiatives, tasks, proposals, invariants, locks, approvals, grants, attempts, heartbeats, cost/loop records, immutable activity, and outbox records.

## Security Model

The intended roles are migration owner, dedicated NOLOGIN function owner, and restricted application role. Privileged functions use the D-28 fixed search path and are intended to replace direct application mutation. Production, external integrations, live credentials, business-data ownership, and `/opt/paperclip` changes remain prohibited.

## Remaining Work

M5-A is complete. The D-28 governance database boundary has been proven in a disposable, network-isolated PostgreSQL container with all required security, concurrency, rollback, and reapply markers. M5-B (authenticated service contract and narrow executor integration) remains unstarted. Production, live services, and `/opt/paperclip` remain untouched.

## Checksum Correction Note

`docs/TEST_EVIDENCE.md` M5-E001 previously recorded the `/opt/paperclip` inventory SHA-256 with a 63-character transcription defect (`...fdad4`). The canonical 64-character SHA-256 of the excluded file tree is `dc3d4355e502d4fc678b6b3b43a4e70deb86b09109fd4c0aeccd29a055fdad44`. The committed historical record in `docs/reports/M5_PAPERCLIP_DISCOVERY_REVIEW.md` at commit `d2ba98cca5eefe48cc6c31b0e84d57449031bed2` retains the defective value unchanged; this note and the corrected `docs/TEST_EVIDENCE.md` entry supersede it for M5-A evidence purposes.