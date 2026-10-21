# Xano prototype execution handoff

Updated 21 October 2026. Scope: `Gopi-git-bit/New-logistic-`, PR #32.

## Evidence and current boundary

The owner supplied a Windows Codex inspection reporting authenticated HTTP 200
from `https://xynd-fnea-khtp.n7e.xano.io`, workspace 1,
`Zippy Synthetic Prototype`, branch `v1` (live, branch detail ID 0).
That report distinguishes 2 live tables and zero live unit tests from 51 sandbox
tables and 41 sandbox unit-test definitions. Listed definitions were not run.
These are owner-supplied observations, not independently reproduced here.
The report does not establish sandbox data-source isolation or working dispatch.
Workspace IDs are instance-local; do not reuse the older workspace 169944.

This session's newest available Composio connection returned `Invalid token`
on a read-only workspace list. That does not contradict the working direct
Windows Codex route. No credential rotation is needed for the direct route on
the strength of this failure. No tokens belong in Git, chat or evidence.

## Execution sequence for the connected development environment

1. Read the current repository guardrails and PR #32. Use the existing direct
   connection, read its current instance/workspace/branch context, and export
   only relevant metadata/code. Explicitly bind workspace 1 and the intended
   sandbox; never rely on an unset profile branch. Verify its data source is
   synthetic-only and separate from business data before any mutation.
2. Read official MCP `start`, applicable object topics and `fs-syntax` before
   authoring XanoScript. Record installed package version/integrity and platform
   capabilities. Commit sanitized baseline definitions and hashes in this
   repository so changes can be reviewed against actual source.
3. Inspect and correct the reported authentication findings in sandbox code:
   log an allowlisted event payload rather than a password-bearing user object;
   build the reset link with explicit encoded parameters and a verified route;
   require authenticated authorization for welcome-email requests. Test without
   sending email: use a local/synthetic sink with no configured delivery secret.
   Treat the findings as reported source observations until inspected directly.
4. Implement only namespaced synthetic order creation, eligibility, assignment,
   immutable audit/idempotency and transactional outbox. Require unique active
   order and vehicle constraints and one transaction for every assignment
   effect. Do not port schemas blindly or publish sandbox objects to `v1`.
5. Exercise simultaneous authenticated HTTP calls: two orders/one vehicle,
   two vehicles/one order, identical retries and conflicting payload retries.
   Assert winner counts plus persisted audit/outbox/idempotency/state consistency;
   a losing request must leave no partial effects. Verify cross-tenant and
   unassigned-vendor denials and reject forged body authority fields.
6. Inject interruption before commit and after commit before delivery. Reclaim
   an expired lease using the SAME worker identity and reject its older
   generation. Fence acknowledgements by job, worker, generation and expiry.
   A generation protects local acknowledgement only: any eventual receiver
   must enforce its own idempotency/fencing before external side effects.
7. Retain sanitized source/platform/run hashes and explicit executed versus
   not-run results. Clean up only resources owned by this synthetic run; retain
   baseline objects. Unknown cleanup outcomes block acceptance.

## Repository change in this continuation

The SQLite reference now persists a monotonically increasing outbox generation
and returns `(job, generation)` claims. Acknowledgement rejects obsolete claims
even if a restarted worker reuses its name. Regressions cover that race, expiry
at its exact boundary and duplicate completion. This is local reference evidence,
not Xano code or a production database migration. Existing disposable oracle
files should be recreated; no schema upgrade is supplied for them.

## Still outstanding

- Actual Xano source corrections, platform syntax validation and HTTP acceptance.
- Synthetic payment/webhook, manual refund and agent-limit platform proofs.
- Full source-to-Xano mapping of all 72 PostgreSQL cases; none is closed here.
- Production adoption, migration, image publication, live M7 and Qwen remain
  disabled. No provider calls, workflow dispatch or VPS change is included.

See [prototype contract](XANO_ISOLATED_PROTOTYPE.md). A tool name, table count,
agent instruction or passing SQLite test is never Xano behavioral evidence.
